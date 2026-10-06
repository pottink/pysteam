"""One-time move from the old user config directory to local account data."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path

from pysteam.errors import ProfileError
from pysteam.profiles import (
    ProfileRegistry,
    SavedProfile,
    _restrict_windows_acl,
    default_profile_dir,
    legacy_profile_dir,
)


def _digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def migrate_legacy_data() -> tuple[Path, bool]:
    """Copy, verify, and move old account data into the selected local directory.

    Returns the new directory and whether the old directory was fully removed.
    The old directory is kept if any verification step fails.
    """
    old = legacy_profile_dir()
    target = default_profile_dir().resolve()
    if old.is_symlink() or not old.is_dir():
        raise ProfileError("old account data directory is missing or is a symlink")
    old = old.resolve(strict=True)
    if old.name.casefold() != "pysteam" or old.parent != legacy_profile_dir().parent.resolve():
        raise ProfileError("old account data directory is invalid")
    if target == old or target.is_relative_to(old) or old.is_relative_to(target):
        raise ProfileError("old and new account data directories overlap")
    if target.exists() or target.is_symlink():
        raise ProfileError("new account data directory already exists")

    try:
        default, profiles = ProfileRegistry(old)._read()
        files: list[Path] = []
        for path in old.rglob("*"):
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                files.append(path.relative_to(old))
            elif not stat.S_ISDIR(info.st_mode):
                raise ProfileError("old account data contains an unsupported file type")
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".pysteam-migrate-", dir=target.parent))
        try:
            if os.name == "nt":
                _restrict_windows_acl(stage)
            shutil.copytree(old, stage, dirs_exist_ok=True)
            for relative in files:
                if _digest(old / relative) != _digest(stage / relative):
                    raise ProfileError("account data changed during migration")
            staged = ProfileRegistry(stage)
            updated: list[SavedProfile] = []
            for profile in profiles:
                mafile = profile.mafile_path
                if mafile is not None and mafile.is_relative_to(old):
                    mafile = target / mafile.relative_to(old)
                    if not (stage / mafile.relative_to(target)).is_file():
                        raise ProfileError("maFile backup is missing from account data")
                if not staged.store_path(profile.steam_id).is_file():
                    raise ProfileError("encrypted credential store is missing from account data")
                updated.append(
                    SavedProfile(
                        profile.account_name,
                        profile.steam_id,
                        staged.store_path(profile.steam_id),
                        mafile,
                    )
                )
            staged._write(default, updated)
            if os.name != "nt":
                for path in stage.rglob("*"):
                    path.chmod(0o700 if path.is_dir() else 0o600)
                stage.chmod(0o700)
            if target.exists():
                raise ProfileError("new account data directory already exists")
            os.replace(stage, target)
        finally:
            if stage.exists() and stage.resolve().parent == target.parent:
                shutil.rmtree(stage)
        migrated = ProfileRegistry(target).list()
        if len(migrated) != len(profiles):
            raise ProfileError("migrated account registry could not be verified")
        for profile in migrated:
            if not profile.store_path.is_file():
                raise ProfileError("migrated credential store could not be verified")
            if profile.mafile_path is not None and profile.mafile_path.is_relative_to(target):
                if not profile.mafile_path.is_file():
                    raise ProfileError("migrated maFile backup could not be verified")
        # Source removal is deliberately last. A failed cleanup leaves a working copy.
        try:
            if old.is_symlink() or old.resolve() != legacy_profile_dir().resolve():
                return target, False
            shutil.rmtree(old)
        except OSError:
            return target, False
        return target, True
    except (OSError, shutil.Error) as exc:
        raise ProfileError("account data could not be migrated") from exc
