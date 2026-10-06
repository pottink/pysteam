"""Secret-free account registry for explicitly saved Steam login profiles."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
from csv import reader as csv_reader
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from pysteam.errors import ProfileError

_MAX_REGISTRY_BYTES = 64 * 1024


def default_profile_dir() -> Path:
    """Keep account data in the current working directory unless overridden."""
    override = os.environ.get("PYSTEAM_HOME")
    if override:
        return Path(override).expanduser()
    return Path.cwd() / ".pysteam"


def legacy_profile_dir() -> Path:
    """Location used before the project-local default was introduced."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "pysteam"


def _restrict_windows_acl(path: Path) -> None:
    """Give a newly created account-data directory a private Windows DACL."""
    try:
        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = list(csv_reader(identity.stdout.splitlines()))
        sid = rows[0][-1].strip()
        if not sid.startswith("S-1-"):
            raise ValueError
        grants = [
            f"*{sid}:(OI)(CI)F",
            "*S-1-5-18:(OI)(CI)F",
            "*S-1-5-32-544:(OI)(CI)F",
        ]
        subprocess.run(
            ["icacls", str(path), "/grant:r", *grants],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["icacls", str(path), "/inheritance:r"],
            capture_output=True,
            check=True,
        )
    except (OSError, ValueError, IndexError, subprocess.CalledProcessError):
        raise ProfileError("account data directory permissions could not be secured") from None


def ensure_private_directory(path: Path) -> None:
    """Create an account-data root with restricted permissions."""
    if path.is_symlink():
        raise ProfileError("account data directory must not be a symlink")
    existed = path.exists()
    try:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not path.is_dir():
            raise ProfileError("account data path is not a directory")
        if not existed:
            if os.name == "nt":
                _restrict_windows_acl(path)
            else:
                path.chmod(0o700)
    except OSError:
        raise ProfileError("account data directory could not be created") from None


@dataclass(frozen=True, slots=True)
class SavedProfile:
    account_name: str
    steam_id: int
    store_path: Path
    mafile_path: Path | None = None


class ProfileRegistry:
    """Manage several accounts without storing credentials in profile metadata."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else default_profile_dir()
        self.path = self.directory / "profiles.json"

    @staticmethod
    def _account_name(name: str) -> None:
        if not name or len(name) > 256 or name != name.strip() or not name.isprintable():
            raise ProfileError("invalid account name")

    def store_path(self, steam_id: int) -> Path:
        if not 0 < steam_id <= 0xFFFFFFFFFFFFFFFF:
            raise ProfileError("invalid profile SteamID")
        folder = "vault/accounts" if (self.directory / "vault.bin").is_file() else "profiles"
        return self.directory / folder / f"{steam_id}.bin"

    def _read(self) -> tuple[str | None, list[SavedProfile]]:
        if self.path.is_symlink():
            raise ProfileError("profile registry path must not be a symlink")
        try:
            with self.path.open("rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ProfileError("profile registry is not a regular file")
                raw = source.read(_MAX_REGISTRY_BYTES + 1)
        except FileNotFoundError:
            return None, []
        except OSError:
            raise ProfileError("profile registry could not be read") from None
        if len(raw) > _MAX_REGISTRY_BYTES:
            raise ProfileError("profile registry exceeds size limit")
        try:
            data: Any = json.loads(raw)
            if not isinstance(data, dict) or data.get("version") not in (1, 2):
                raise ValueError
            default = data.get("default")
            records = data.get("profiles")
            if default is not None and not isinstance(default, str):
                raise ValueError
            if not isinstance(records, list) or len(records) > 256:
                raise ValueError
            profiles: list[SavedProfile] = []
            seen_names: set[str] = set()
            seen_ids: set[int] = set()
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError
                name = record["account_name"]
                steam_id = record["steam_id"]
                store_path = record["store_path"]
                mafile = record.get("mafile_path")
                if (
                    not isinstance(name, str)
                    or type(steam_id) is not int
                    or not isinstance(store_path, str)
                ):
                    raise ValueError
                self._account_name(name)
                if store_path not in (
                    f"profiles/{steam_id}.bin",
                    f"vault/accounts/{steam_id}.bin",
                ):
                    raise ValueError
                if mafile is not None and (
                    not isinstance(mafile, str) or not Path(mafile).is_absolute()
                ):
                    raise ValueError
                key = name.casefold()
                if key in seen_names or steam_id in seen_ids:
                    raise ValueError
                seen_names.add(key)
                seen_ids.add(steam_id)
                profiles.append(
                    SavedProfile(
                        name,
                        steam_id,
                        self.directory / store_path,
                        Path(mafile) if mafile is not None else None,
                    )
                )
            if default is not None and default.casefold() not in seen_names:
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise ProfileError("profile registry is corrupt or unsupported") from None
        return default, profiles

    def _write(self, default: str | None, profiles: list[SavedProfile]) -> None:
        data = {
            "version": 2,
            "default": default,
            "profiles": [
                {
                    "account_name": profile.account_name,
                    "steam_id": profile.steam_id,
                    "store_path": profile.store_path.relative_to(self.directory).as_posix(),
                    "mafile_path": str(profile.mafile_path) if profile.mafile_path else None,
                }
                for profile in profiles
            ],
        }
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(raw) > _MAX_REGISTRY_BYTES:
            raise ProfileError("profile registry exceeds size limit")
        try:
            ensure_private_directory(self.directory)
            descriptor, temporary = tempfile.mkstemp(prefix=".profiles-", dir=self.directory)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
                if os.name != "nt":
                    self.path.chmod(0o600)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError:
            raise ProfileError("profile registry could not be updated") from None

    def list(self) -> tuple[SavedProfile, ...]:
        return tuple(self._read()[1])

    def default(self) -> SavedProfile | None:
        name, profiles = self._read()
        if name is None:
            return None
        return next(
            profile for profile in profiles if profile.account_name.casefold() == name.casefold()
        )

    def get(self, account_name: str) -> SavedProfile | None:
        self._account_name(account_name)
        return next(
            (p for p in self._read()[1] if p.account_name.casefold() == account_name.casefold()),
            None,
        )

    def select(self, account_name: str | None = None) -> SavedProfile:
        profile = self.get(account_name) if account_name is not None else self.default()
        if profile is None:
            raise ProfileError("saved account not found; run 'pysteam account add' first")
        return profile

    def add(self, profile: SavedProfile) -> None:
        self._account_name(profile.account_name)
        if profile.store_path != self.store_path(profile.steam_id):
            raise ProfileError("profile store path is invalid")
        ensure_private_directory(self.directory)
        try:
            with FileLock(str(self.path) + ".lock", timeout=10):
                default, profiles = self._read()
                if any(
                    p.account_name.casefold() == profile.account_name.casefold()
                    or p.steam_id == profile.steam_id
                    for p in profiles
                ):
                    raise ProfileError("account profile already exists")
                profiles.append(profile)
                self._write(default or profile.account_name, profiles)
        except FileLockTimeout:
            raise ProfileError("profile registry is locked") from None

    def migrate_stores(self, replacements: dict[int, Path]) -> None:
        """Atomically switch profiles after their new stores have been verified."""
        try:
            with FileLock(str(self.path) + ".lock", timeout=10):
                default, profiles = self._read()
                if {item.steam_id for item in profiles} != set(replacements):
                    raise ProfileError("account profiles changed during vault migration")
                updated: list[SavedProfile] = []
                for item in profiles:
                    target = replacements[item.steam_id]
                    if target != self.directory / "vault" / "accounts" / f"{item.steam_id}.bin":
                        raise ProfileError("vault migration target is invalid")
                    if not target.is_file():
                        raise ProfileError("vault migration store is missing")
                    updated.append(
                        SavedProfile(item.account_name, item.steam_id, target, item.mafile_path)
                    )
                self._write(default, updated)
        except FileLockTimeout:
            raise ProfileError("profile registry is locked") from None

    def use(self, account_name: str) -> SavedProfile:
        self._account_name(account_name)
        if not self.path.exists():
            raise ProfileError("saved account not found")
        try:
            with FileLock(str(self.path) + ".lock", timeout=10):
                _, profiles = self._read()
                profile = next(
                    (p for p in profiles if p.account_name.casefold() == account_name.casefold()),
                    None,
                )
                if profile is None:
                    raise ProfileError("saved account not found")
                self._write(profile.account_name, profiles)
                return profile
        except FileLockTimeout:
            raise ProfileError("profile registry is locked") from None

    def remove(self, account_name: str) -> SavedProfile:
        """Remove a profile and its managed store, preserving its maFile backup."""
        profile = self.select(account_name)
        try:
            profile.store_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            # Credential writes acquire the store lock before the registry lock.
            with FileLock(str(profile.store_path) + ".lock", timeout=10):
                with FileLock(str(self.path) + ".lock", timeout=10):
                    default, profiles = self._read()
                    current = next(
                        (
                            item
                            for item in profiles
                            if item.account_name.casefold() == account_name.casefold()
                        ),
                        None,
                    )
                    if current != profile:
                        raise ProfileError("account profile changed; retry removal")
                    try:
                        info = profile.store_path.lstat()
                    except FileNotFoundError:
                        pass
                    else:
                        if not stat.S_ISREG(info.st_mode):
                            raise ProfileError("credential store path is not a regular file")
                        profile.store_path.unlink()
                    remaining = [item for item in profiles if item != profile]
                    if (
                        default is not None
                        and default.casefold() == profile.account_name.casefold()
                    ):
                        default = remaining[0].account_name if remaining else None
                    self._write(default, remaining)
                    return profile
        except FileLockTimeout:
            raise ProfileError("account profile is locked") from None
        except OSError:
            raise ProfileError("account profile could not be removed") from None
