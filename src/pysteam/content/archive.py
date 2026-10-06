"""Portable raw Steam depot archives and bounded asynchronous downloads."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

import httpx
import msgspec
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from filelock import FileLock

from pysteam.accounts.profiles import ensure_private_directory
from pysteam.content.cdn import (
    DepotChunk,
    DepotFile,
    DepotManifest,
    _file_checksum_matches,
    parse_manifest,
    process_chunk,
)
from pysteam.errors import CDNError, CDNHTTPError, CredentialStoreError, TransportError

if TYPE_CHECKING:
    from pysteam.client import SteamClient
    from pysteam.content.workshop import WorkshopItem

_ARCHIVE_MAGIC = b"PYSTEAM-ARCHIVE-1\0"
_KEY_MAGIC = b"PYSTEAM-ARCHIVE-KEYS-1\0"
_MAX_KEY_FILE = 1024 * 1024
_MAX_MANIFEST_FILE = 64 * 1024 * 1024
_MAX_CATALOG = 16 * 1024
_DEFAULT_MEMORY = 256 * 1024 * 1024
_MAX_ARCHIVE_REGISTRY = 64 * 1024
_MAX_APPINFO = 32 * 1024 * 1024


class ArchiveRegistry:
    """Non-secret list of portable archives tied to this CLI vault."""

    def __init__(self, vault_directory: Path) -> None:
        self.path = vault_directory / "archives.json"

    def list(self) -> tuple[Path, ...]:
        if self.path.is_symlink():
            raise CredentialStoreError("archive registry path must not be a symlink")
        try:
            with self.path.open("rb") as source:
                raw = source.read(_MAX_ARCHIVE_REGISTRY + 1)
        except FileNotFoundError:
            return ()
        if len(raw) > _MAX_ARCHIVE_REGISTRY:
            raise CredentialStoreError("archive registry exceeds size limit")
        try:
            data = json.loads(raw)
            if (
                not isinstance(data, dict)
                or data.get("version") != 1
                or not isinstance(data.get("archives"), list)
                or len(data["archives"]) > 1024
                or any(
                    not isinstance(item, str) or not Path(item).is_absolute()
                    for item in data["archives"]
                )
            ):
                raise ValueError
            return tuple(Path(item) for item in data["archives"])
        except (ValueError, UnicodeError):
            raise CredentialStoreError("archive registry is invalid") from None

    def add(self, root: Path) -> None:
        root = root.resolve()
        ensure_private_directory(self.path.parent)
        with FileLock(str(self.path) + ".lock", timeout=10):
            existing = self.list()
            if root not in existing:
                raw = msgspec.json.encode(
                    {"version": 1, "archives": [str(item) for item in (*existing, root)]}
                )
                if len(raw) > _MAX_ARCHIVE_REGISTRY:
                    raise CredentialStoreError("archive registry exceeds size limit")
                _atomic_write(self.path, raw)


class ArchiveRecord(msgspec.Struct, forbid_unknown_fields=True):
    app_id: int
    depot_id: int
    manifest_id: int
    branch: str
    complete: bool
    manifest_sha256: str
    chunks: int
    bytes_downloaded: int


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    app_id: int
    depot_id: int
    manifest_id: int
    chunks_downloaded: int
    chunks_reused: int
    bytes_downloaded: int


@dataclass(frozen=True, slots=True)
class WorkshopArchiveResult:
    published_file_id: int
    source: str
    bytes_downloaded: int
    depot: ArchiveResult | None = None


@dataclass(frozen=True, slots=True)
class ManifestDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]


class _MemoryBudget:
    """Reserve a whole chunk's byte budget atomically among workers."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.available = capacity
        self.condition = asyncio.Condition()

    async def acquire(self, units: int) -> None:
        if units > self.capacity:
            raise CDNError("manifest chunk exceeds archive memory limit")
        async with self.condition:
            await self.condition.wait_for(lambda: self.available >= units)
            self.available -= units

    async def release(self, units: int) -> None:
        async with self.condition:
            self.available += units
            self.condition.notify_all()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_bounded(path: Path, limit: int, description: str) -> bytes:
    try:
        with path.open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise CDNError(f"{description} is not a regular file")
            if info.st_size > limit:
                raise CDNError(f"{description} exceeds size limit")
            raw = source.read(info.st_size)
            if source.read(1):
                raise CDNError(f"{description} changed while reading")
    except OSError:
        raise CDNError(f"{description} is missing or unreadable") from None
    if len(raw) > limit:
        raise CDNError(f"{description} exceeds size limit")
    return raw


def _extraction_parts(name: str) -> tuple[str, ...]:
    parts = tuple(name.split("/"))
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    if any(
        not part
        or part[-1] in (" ", ".")
        or part.split(".", 1)[0].casefold() in reserved
        or any(ord(char) < 32 or char in '<>:"|?*\\' for char in part)
        for part in parts
    ):
        raise CDNError("manifest contains a non-portable extraction path")
    return parts


def _key_encryption_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(passphrase.encode("utf-8"))


class ArchiveStore:
    """Offline archive whose manifest and encrypted chunks remain portable."""

    def __init__(self, root: str | Path, passphrase: str) -> None:
        if not passphrase:
            raise ValueError("archive vault password is required")
        self.root = Path(root)
        self._passphrase = passphrase

    @property
    def key_path(self) -> Path:
        return self.root / "keys.bin"

    def initialize(self) -> None:
        ensure_private_directory(self.root)
        header = self.root / "archive.bin"
        if header.exists():
            if _read_bounded(header, len(_ARCHIVE_MAGIC), "archive header") != _ARCHIVE_MAGIC:
                raise CDNError("unsupported archive format")
        else:
            _atomic_write(header, _ARCHIVE_MAGIC)

    def save_appinfo(self, app_id: int, raw: bytes) -> tuple[str, bool]:
        """Preserve original PICS bytes and point latest at their content hash."""
        if not 0 < app_id <= 0xFFFFFFFF or not raw or len(raw) > _MAX_APPINFO:
            raise CDNError("app metadata ID or size is invalid")
        self.initialize()
        digest = hashlib.sha256(raw).hexdigest()
        folder = self.root / "appinfo" / str(app_id)
        target = folder / f"{digest}.bin"
        if target.exists():
            if _read_bounded(target, _MAX_APPINFO, "app metadata snapshot") != raw:
                raise CDNError("app metadata hash collision")
            changed = False
        else:
            _atomic_write(target, raw)
            changed = True
        _atomic_write(folder / "latest", digest.encode("ascii"))
        return digest, changed

    def appinfo_ids(self) -> tuple[int, ...]:
        folder = self.root / "appinfo"
        if not folder.exists():
            return ()
        return tuple(
            sorted(
                int(item.name)
                for item in folder.iterdir()
                if item.is_dir() and item.name.isdecimal()
            )
        )

    def appinfo(self, app_id: int, *, digest: str | None = None) -> bytes:
        folder = self.root / "appinfo" / str(app_id)
        if digest is None:
            try:
                digest = (folder / "latest").read_text(encoding="ascii")
            except OSError:
                raise CDNError("app metadata snapshot is missing") from None
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise CDNError("app metadata digest is invalid")
        try:
            with (folder / f"{digest}.bin").open("rb") as source:
                raw = source.read(_MAX_APPINFO + 1)
        except OSError:
            raise CDNError("app metadata snapshot is missing") from None
        if len(raw) > _MAX_APPINFO or hashlib.sha256(raw).hexdigest() != digest:
            raise CDNError("app metadata snapshot is corrupt")
        return raw

    def save_workshop_metadata(self, item: WorkshopItem) -> None:
        self.initialize()
        data = msgspec.json.encode(
            {
                "version": 1,
                "published_file_id": item.published_file_id,
                "app_id": item.app_id,
                "manifest_id": item.manifest_id,
                "title": item.title,
                "file_size": item.file_size,
            }
        )
        _atomic_write(self.root / "workshop" / str(item.published_file_id) / "metadata.json", data)

    def _read_keys(self) -> dict[str, str]:
        if self.key_path.is_symlink():
            raise CredentialStoreError("archive key vault path must not be a symlink")
        try:
            with self.key_path.open("rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise CredentialStoreError("archive key vault is not a regular file")
                if os.name != "nt" and info.st_mode & 0o077:
                    raise CredentialStoreError("archive key vault permissions are too open")
                raw = source.read(_MAX_KEY_FILE + 1)
        except FileNotFoundError:
            return {}
        if len(raw) > _MAX_KEY_FILE or len(raw) < len(_KEY_MAGIC) + 16 + 12 + 16:
            raise CredentialStoreError("archive key vault is invalid")
        if not raw.startswith(_KEY_MAGIC):
            raise CredentialStoreError("unsupported archive key vault format")
        start = len(_KEY_MAGIC)
        salt, nonce, ciphertext = (
            raw[start : start + 16],
            raw[start + 16 : start + 28],
            raw[start + 28 :],
        )
        try:
            plaintext = AESGCM(_key_encryption_key(self._passphrase, salt)).decrypt(
                nonce, ciphertext, _KEY_MAGIC + salt
            )
            keys = msgspec.json.decode(plaintext, type=dict[str, str])
        except (InvalidTag, msgspec.DecodeError, msgspec.ValidationError):
            raise CredentialStoreError("wrong archive password or corrupt key vault") from None
        return keys

    def _write_keys(self, keys: dict[str, str]) -> None:
        salt, nonce = os.urandom(16), os.urandom(12)
        data = (
            _KEY_MAGIC
            + salt
            + nonce
            + AESGCM(_key_encryption_key(self._passphrase, salt)).encrypt(
                nonce, msgspec.json.encode(keys), _KEY_MAGIC + salt
            )
        )
        if len(data) > _MAX_KEY_FILE:
            raise CredentialStoreError("archive key vault exceeds size limit")
        _atomic_write(self.key_path, data)

    def save_key(self, depot_id: int, key: bytes) -> None:
        if depot_id <= 0 or len(key) != 32:
            raise ValueError("invalid depot ID or key")
        self.initialize()
        with FileLock(str(self.key_path) + ".lock", timeout=10):
            keys = self._read_keys()
            current = keys.get(str(depot_id))
            if current is not None and current != key.hex():
                raise CredentialStoreError("archive has a different key for this depot")
            keys[str(depot_id)] = key.hex()
            self._write_keys(keys)

    def get_key(self, depot_id: int) -> bytes:
        value = self._read_keys().get(str(depot_id))
        if value is None:
            raise CredentialStoreError("archive has no key for this depot")
        try:
            key = bytes.fromhex(value)
        except ValueError:
            raise CredentialStoreError("archive key vault is invalid") from None
        if len(key) != 32:
            raise CredentialStoreError("archive key vault is invalid")
        return key

    def rekey(self, new_passphrase: str) -> None:
        if len(new_passphrase) < 12:
            raise CredentialStoreError("new vault password must have at least 12 characters")
        if not self.key_path.is_file():
            raise CredentialStoreError("archive has no key capsule to rewrap")
        with FileLock(str(self.key_path) + ".lock", timeout=10):
            keys = self._read_keys()
            ArchiveStore(self.root, new_passphrase)._write_keys(keys)
        self._passphrase = new_passphrase

    def _manifest_path(self, depot_id: int, manifest_id: int) -> Path:
        if depot_id <= 0 or manifest_id <= 0:
            raise ValueError("invalid depot or manifest ID")
        return self.root / "manifests" / str(depot_id) / f"{manifest_id}.manifest"

    def _record_path(self, depot_id: int, manifest_id: int) -> Path:
        return self._manifest_path(depot_id, manifest_id).with_suffix(".json")

    def save_manifest(self, manifest: DepotManifest, *, app_id: int, branch: str) -> None:
        if not manifest.raw:
            raise CDNError("archive requires the original manifest bytes")
        original = parse_manifest(manifest.raw)
        if (original.depot_id, original.manifest_id) != (manifest.depot_id, manifest.manifest_id):
            raise CDNError("archive manifest identity mismatch")
        self.initialize()
        path = self._manifest_path(manifest.depot_id, manifest.manifest_id)
        if (
            path.exists()
            and _read_bounded(path, _MAX_MANIFEST_FILE, "archive manifest") != manifest.raw
        ):
            raise CDNError("archive manifest ID already contains different bytes")
        _atomic_write(path, manifest.raw)
        record = ArchiveRecord(
            app_id,
            manifest.depot_id,
            manifest.manifest_id,
            branch,
            False,
            hashlib.sha256(manifest.raw).hexdigest(),
            0,
            0,
        )
        _atomic_write(
            self._record_path(manifest.depot_id, manifest.manifest_id), msgspec.json.encode(record)
        )

    def mark_complete(self, record: ArchiveRecord) -> None:
        record.complete = True
        _atomic_write(
            self._record_path(record.depot_id, record.manifest_id), msgspec.json.encode(record)
        )

    def list(self) -> tuple[ArchiveRecord, ...]:
        if not self.root.exists():
            return ()
        result: list[ArchiveRecord] = []
        for path in (self.root / "manifests").glob("*/*.json"):
            try:
                result.append(
                    msgspec.json.decode(
                        _read_bounded(path, _MAX_CATALOG, "archive catalog"), type=ArchiveRecord
                    )
                )
            except (CDNError, msgspec.DecodeError, msgspec.ValidationError):
                raise CDNError("archive catalog is invalid") from None
        return tuple(
            sorted(result, key=lambda item: (item.app_id, item.depot_id, item.manifest_id))
        )

    def manifest(self, depot_id: int, manifest_id: int) -> DepotManifest:
        path = self._manifest_path(depot_id, manifest_id)
        raw = _read_bounded(path, _MAX_MANIFEST_FILE, "archive manifest")
        manifest = parse_manifest(raw, depot_key=self.get_key(depot_id))
        if (manifest.depot_id, manifest.manifest_id) != (depot_id, manifest_id):
            raise CDNError("archive manifest identity mismatch")
        return manifest

    def _chunk_path(self, depot_id: int, chunk: DepotChunk) -> Path:
        if depot_id <= 0 or len(chunk.sha) != 20:
            raise ValueError("invalid depot or chunk ID")
        name = chunk.sha.hex()
        return self.root / "objects" / str(depot_id) / name[:2] / name

    def has_chunk(self, depot_id: int, chunk: DepotChunk, key: bytes) -> bool:
        path = self._chunk_path(depot_id, chunk)
        try:
            if path.is_symlink() or path.stat().st_size != chunk.compressed_size:
                return False
            process_chunk(path.read_bytes(), key, chunk)
        except FileNotFoundError:
            return False
        except CDNError:
            return False
        return True

    def save_chunk(
        self,
        depot_id: int,
        chunk: DepotChunk,
        encrypted: bytes,
        key: bytes,
        *,
        verified: bool = False,
    ) -> None:
        if not verified:
            process_chunk(encrypted, key, chunk)
        path = self._chunk_path(depot_id, chunk)
        ensure_private_directory(path.parent)
        with FileLock(str(path) + ".lock", timeout=10):
            if verified or not self.has_chunk(depot_id, chunk, key):
                _atomic_write(path, encrypted)

    def verify(self, depot_id: int, manifest_id: int) -> tuple[int, int]:
        manifest = self.manifest(depot_id, manifest_id)
        key = self.get_key(depot_id)
        checked = 0
        missing = 0
        for file in manifest.files:
            if file.link_target or file.flags & (64 | 512):
                continue
            digest = hashlib.sha1()
            length = 0
            for chunk in sorted(file.chunks, key=lambda item: item.offset):
                checked += 1
                if chunk.offset != length:
                    missing += 1
                    continue
                path = self._chunk_path(depot_id, chunk)
                try:
                    if path.is_symlink() or path.stat().st_size != chunk.compressed_size:
                        missing += 1
                        continue
                    clear = process_chunk(path.read_bytes(), key, chunk)
                except (FileNotFoundError, CDNError):
                    missing += 1
                    continue
                digest.update(clear)
                length += len(clear)
            if length != file.size or not _file_checksum_matches(file, digest.digest()):
                missing += 1
        return checked, missing

    def extract(
        self,
        depot_id: int,
        manifest_id: int,
        destination: Path,
        *,
        files: Iterable[str] | None = None,
        overwrite: bool = False,
    ) -> tuple[Path, ...]:
        manifest = self.manifest(depot_id, manifest_id)
        key = self.get_key(depot_id)
        wanted = set(files) if files is not None else None
        selected: list[tuple[DepotFile, Path]] = []
        root = destination.resolve()
        seen_files: set[tuple[str, ...]] = set()
        seen_dirs: set[tuple[str, ...]] = set()
        for file in manifest.files:
            if file.link_target or file.flags & (64 | 512):
                continue
            if wanted is not None and file.name not in wanted:
                continue
            parts = _extraction_parts(file.name)
            target = root.joinpath(*parts)
            if not target.resolve().is_relative_to(root):
                raise CDNError("manifest path escapes extraction directory")
            folded = tuple(part.casefold() for part in parts)
            if (
                folded in seen_files
                or folded in seen_dirs
                or any(folded[:index] in seen_files for index in range(1, len(folded)))
            ):
                raise CDNError("manifest has case-colliding file paths")
            seen_files.add(folded)
            seen_dirs.update(folded[:index] for index in range(1, len(folded)))
            if target.is_symlink():
                raise CDNError("extraction destination must not be a symlink")
            if target.exists() and not overwrite:
                raise CDNError("extraction destination exists; use --overwrite")
            selected.append((file, target))
        if wanted is not None and wanted != {file.name for file, _ in selected}:
            raise CDNError("requested file is not in the archive")
        written: list[Path] = []
        for file, target in selected:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-", dir=target.parent)
            try:
                digest = hashlib.sha1()
                position = 0
                with os.fdopen(descriptor, "wb") as output:
                    for chunk in sorted(file.chunks, key=lambda item: item.offset):
                        if chunk.offset != position:
                            raise CDNError("manifest file has a gap or overlap")
                        clear = process_chunk(
                            self._chunk_path(depot_id, chunk).read_bytes(), key, chunk
                        )
                        output.write(clear)
                        digest.update(clear)
                        position += len(clear)
                    output.flush()
                    os.fsync(output.fileno())
                if position != file.size or not _file_checksum_matches(file, digest.digest()):
                    raise CDNError("archive file checksum mismatch")
                os.replace(temporary, target)
                written.append(target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return tuple(written)

    def diff(self, depot_id: int, old: int, new: int) -> ManifestDiff:
        before = {file.name: file for file in self.manifest(depot_id, old).files}
        after = {file.name: file for file in self.manifest(depot_id, new).files}
        return ManifestDiff(
            tuple(sorted(after.keys() - before.keys())),
            tuple(sorted(before.keys() - after.keys())),
            tuple(
                sorted(
                    name
                    for name in before.keys() & after.keys()
                    if before[name].sha != after[name].sha
                )
            ),
        )

    def import_legacy(
        self,
        source: Path,
        *,
        app_id: int,
        depot_id: int,
        manifest_id: int,
        key: bytes,
        branch: str = "public",
    ) -> ArchiveRecord:
        """Import a steamarchiver depots/<id>/<gid>.zip and SHA-named chunks."""
        if self.root.resolve().is_relative_to(source.resolve()):
            raise CDNError("archive destination must be outside the legacy source")
        directory = source / "depots" / str(depot_id)
        if not directory.is_dir():
            directory = source / str(depot_id)
        if not directory.is_dir():
            directory = source
        manifest_file = directory / f"{manifest_id}.zip"
        if not manifest_file.is_file() or manifest_file.is_symlink():
            raise CDNError("legacy manifest ZIP is missing")
        try:
            with zipfile.ZipFile(manifest_file) as archive:
                entries = archive.infolist()
                if len(entries) != 1 or entries[0].file_size > 64 * 1024 * 1024:
                    raise CDNError("legacy manifest ZIP is invalid or too large")
                with archive.open(entries[0]) as entry:
                    raw = entry.read(64 * 1024 * 1024 + 1)
        except (OSError, zipfile.BadZipFile):
            raise CDNError("legacy manifest ZIP is invalid") from None
        manifest = parse_manifest(raw, depot_key=key)
        if (manifest.depot_id, manifest.manifest_id) != (depot_id, manifest_id):
            raise CDNError("legacy manifest identity mismatch")
        self.save_key(depot_id, key)
        self.save_manifest(manifest, app_id=app_id, branch=branch)
        chunks = {chunk.sha: chunk for file in manifest.files for chunk in file.chunks}
        imported = 0
        for sha, chunk in chunks.items():
            path = directory / sha.hex()
            if not path.exists():
                continue
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
                raise CDNError("legacy chunk is invalid or too large")
            self.save_chunk(depot_id, chunk, path.read_bytes(), key)
            imported += 1
        checked, missing = self.verify(depot_id, manifest_id)
        record = ArchiveRecord(
            app_id,
            depot_id,
            manifest_id,
            branch,
            missing == 0,
            hashlib.sha256(raw).hexdigest(),
            checked,
            imported,
        )
        if record.complete:
            self.mark_complete(record)
        return record


class ContentArchiver:
    """Download a depot into an ArchiveStore using a bounded worker queue."""

    def __init__(
        self,
        client: SteamClient,
        store: ArchiveStore,
        *,
        max_downloads: int = 8,
        max_inflight_bytes: int = _DEFAULT_MEMORY,
        cpu_workers: int = 0,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        if not 1 <= max_downloads <= 64 or max_inflight_bytes < 64 * 1024 * 1024:
            raise ValueError("invalid archive concurrency or memory limit")
        if not 0 <= cpu_workers <= 32:
            raise ValueError("invalid CPU worker count")
        self.client = client
        self.store = store
        self.max_downloads = max_downloads
        self.max_inflight_bytes = max_inflight_bytes
        self.cpu_workers = cpu_workers
        self.progress = progress

    async def archive_depot(
        self, app_id: int, depot_id: int, *, manifest_id: int | None = None, branch: str = "public"
    ) -> ArchiveResult:
        client = self.client
        if manifest_id is None:
            manifest_id = (await client.get_app_manifest_ids(app_id, branch=branch)).get(depot_id)
            if manifest_id is None:
                raise CDNError("PICS has no manifest for this depot and branch")
        key = await client.cdn.get_depot_key(app_id, depot_id)
        servers = (await client.cdn.servers())[:8]
        if not servers:
            raise CDNError("Steam returned no CDN servers")
        tokens: dict[str, str] = {}
        manifest: DepotManifest | None = None
        for server in servers:
            try:
                manifest = await client.cdn.get_manifest(
                    server=server,
                    app_id=app_id,
                    depot_id=depot_id,
                    manifest_id=manifest_id,
                    depot_key=key,
                    branch=branch,
                )
                break
            except CDNHTTPError as exc:
                if exc.status_code not in (401, 403):
                    continue
                host = urlsplit(server).hostname
                if host is None:
                    continue
                tokens[server] = await client.cdn.get_auth_token(app_id, depot_id, host)
                try:
                    manifest = await client.cdn.get_manifest(
                        server=server,
                        app_id=app_id,
                        depot_id=depot_id,
                        manifest_id=manifest_id,
                        depot_key=key,
                        branch=branch,
                        auth_token=tokens[server],
                    )
                    break
                except (CDNHTTPError, TransportError):
                    continue
            except (TransportError, CDNError):
                continue
        if manifest is None:
            raise CDNError("CDN manifest could not be fetched")
        self.store.save_key(depot_id, key)
        self.store.save_manifest(manifest, app_id=app_id, branch=branch)
        unique = {chunk.sha: chunk for file in manifest.files for chunk in file.chunks}
        pending = [
            chunk for chunk in unique.values() if not self.store.has_chunk(depot_id, chunk, key)
        ]
        queue: asyncio.Queue[DepotChunk | None] = asyncio.Queue(maxsize=self.max_downloads * 2)
        downloaded = 0
        size = 0
        memory = _MemoryBudget(max(1, self.max_inflight_bytes // (1024 * 1024)))
        pool = ProcessPoolExecutor(max_workers=self.cpu_workers) if self.cpu_workers else None

        async def producer() -> None:
            for chunk in pending:
                await queue.put(chunk)
            for _ in range(self.max_downloads):
                await queue.put(None)

        async def worker(index: int) -> None:
            nonlocal downloaded, size
            offset = index % len(servers)
            preferred_servers = servers[offset:] + servers[:offset]
            while (chunk := await queue.get()) is not None:
                units = max(1, (chunk.original_size + chunk.compressed_size + 1048575) // 1048576)
                await memory.acquire(units)
                try:
                    last_error: Exception | None = None
                    saved = False
                    for server in preferred_servers:
                        for attempt in range(3):
                            try:
                                raw = await client.cdn.get_chunk(
                                    server=server,
                                    depot_id=depot_id,
                                    chunk=chunk,
                                    auth_token=tokens.get(server, ""),
                                )
                                if pool is None:
                                    await asyncio.to_thread(process_chunk, raw, key, chunk)
                                else:
                                    loop = asyncio.get_running_loop()
                                    await loop.run_in_executor(pool, process_chunk, raw, key, chunk)
                                await asyncio.to_thread(
                                    self.store.save_chunk,
                                    depot_id,
                                    chunk,
                                    raw,
                                    key,
                                    verified=True,
                                )
                                downloaded += 1
                                size += len(raw)
                                saved = True
                                if self.progress is not None:
                                    self.progress(downloaded, len(pending))
                                break
                            except CDNHTTPError as exc:
                                last_error = exc
                                if exc.status_code in (401, 403) and not tokens.get(server):
                                    host = urlsplit(server).hostname
                                    if host is not None:
                                        tokens[server] = await client.cdn.get_auth_token(
                                            app_id, depot_id, host
                                        )
                                        continue
                                if exc.status_code not in (429, 500, 502, 503, 504):
                                    break
                            except (TransportError, CDNError) as exc:
                                last_error = exc
                            await asyncio.sleep(min(2**attempt, 4))
                        if saved:
                            break
                    if not saved and not self.store.has_chunk(depot_id, chunk, key):
                        raise CDNError("CDN chunk could not be downloaded") from last_error
                finally:
                    await memory.release(units)

        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(producer())
                for index in range(self.max_downloads):
                    group.create_task(worker(index))
        except* CDNError as group:
            error = group.exceptions[0]
            raise error from error.__cause__
        finally:
            if pool is not None:
                pool.shutdown(wait=True, cancel_futures=True)
        checked, missing = await asyncio.to_thread(self.store.verify, depot_id, manifest_id)
        if missing or checked < len(unique):
            raise CDNError("archive verification failed; manifest remains incomplete")
        record = ArchiveRecord(
            app_id,
            depot_id,
            manifest_id,
            branch,
            True,
            hashlib.sha256(manifest.raw).hexdigest(),
            len(unique),
            size,
        )
        self.store.mark_complete(record)
        return ArchiveResult(
            app_id, depot_id, manifest_id, downloaded, len(unique) - downloaded, size
        )

    async def archive_workshop(self, published_file_id: int) -> WorkshopArchiveResult:
        item = await self.client.workshop.get_details(published_file_id)
        self.store.save_workshop_metadata(item)
        if item.manifest_id and not item.file_url:
            result = await self.archive_depot(
                item.app_id, item.app_id, manifest_id=item.manifest_id
            )
            return WorkshopArchiveResult(
                published_file_id, "steampipe", result.bytes_downloaded, result
            )
        if not item.file_url:
            raise CDNError("Workshop item has no SteamPipe manifest or file URL")
        parsed = urlsplit(item.file_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise CDNError("Workshop file URL must be HTTPS")
        folder = self.store.root / "workshop" / str(published_file_id)
        ensure_private_directory(folder)
        descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-workshop-", dir=folder)
        digest = hashlib.sha256()
        length = 0
        try:
            with os.fdopen(descriptor, "wb") as output:
                async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
                    url = item.file_url
                    for _ in range(6):
                        async with http.stream("GET", url) as response:
                            if response.status_code in (301, 302, 303, 307, 308):
                                location = response.headers.get("location")
                                if not location:
                                    raise CDNError("Workshop redirect has no destination")
                                url = urljoin(str(response.url), location)
                                parsed = urlsplit(url)
                                if (
                                    parsed.scheme != "https"
                                    or not parsed.hostname
                                    or parsed.username
                                    or parsed.password
                                ):
                                    raise CDNError("Workshop redirect must remain HTTPS")
                                continue
                            response.raise_for_status()
                            async for piece in response.aiter_bytes(1024 * 1024):
                                length += len(piece)
                                if length > 4 * 1024 * 1024 * 1024:
                                    raise CDNError("Workshop file exceeds size limit")
                                digest.update(piece)
                                output.write(piece)
                            break
                    else:
                        raise CDNError("Workshop file redirected too many times")
                output.flush()
                os.fsync(output.fileno())
            if item.file_size and length != item.file_size:
                raise CDNError("Workshop file size mismatch")
            target = folder / f"{digest.hexdigest()}.bin"
            os.replace(temporary, target)
            _atomic_write(folder / "latest", digest.hexdigest().encode("ascii"))
        except httpx.HTTPError:
            raise CDNError("Workshop file could not be downloaded") from None
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return WorkshopArchiveResult(published_file_id, "external", length)
