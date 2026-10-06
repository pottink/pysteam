"""Bounded readers and writers for SteamPipe SIS and CSD/CSM backups."""

from __future__ import annotations

import hashlib
import os
import struct
import tempfile
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from pysteam.content.pics import _tokens
from pysteam.errors import CDNError

if TYPE_CHECKING:
    from pysteam.content.archive import ArchiveStore

_CSM_HEADER = struct.Struct("<4sIIII")
_CSM_ENTRY = struct.Struct("<20sQII")
_MAX_CSM = 64 * 1024 * 1024
_MAX_CHUNKS = 1_000_000
_MAX_SIS = 16 * 1024 * 1024
_MAX_CHUNK = 32 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ChunkEntry:
    sha: bytes
    offset: int
    length: int


@dataclass(frozen=True, slots=True)
class ChunkContainer:
    depot_id: int
    encrypted: bool
    csd_path: Path
    entries: tuple[ChunkEntry, ...]

    def read_chunk(self, entry: ChunkEntry) -> bytes:
        with self.csd_path.open("rb") as source:
            source.seek(entry.offset)
            raw = source.read(entry.length + 1)
        if len(raw) != entry.length:
            raise CDNError("CSD chunk is truncated")
        return raw


def inspect_csm(path: Path) -> ChunkContainer:
    """Read an encrypted legacy CSM index without loading its CSD payload."""
    if path.suffix.lower() != ".csm" or path.is_symlink():
        raise CDNError("expected a regular CSM index")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_CSM:
            raise CDNError("CSM index is missing or too large")
        raw = path.read_bytes()
        csd = path.with_suffix(".csd")
        size = csd.stat().st_size
        if csd.is_symlink() or not csd.is_file():
            raise CDNError("CSD payload must be a regular file")
    except OSError:
        raise CDNError("CSD/CSM backup could not be read") from None
    if len(raw) < _CSM_HEADER.size:
        raise CDNError("CSM header is truncated")
    magic, header_size, version, depot_id, count = _CSM_HEADER.unpack_from(raw)
    if (
        magic != b"SCFS"
        or header_size != _CSM_HEADER.size
        or version not in (2, 3)
        or depot_id <= 0
        or count > _MAX_CHUNKS
        or len(raw) != header_size + count * _CSM_ENTRY.size
    ):
        raise CDNError("CSM header or entry count is invalid")
    seen: set[bytes] = set()
    entries: list[ChunkEntry] = []
    intervals: list[tuple[int, int]] = []
    for offset in range(header_size, len(raw), _CSM_ENTRY.size):
        sha, location, reserved, length = _CSM_ENTRY.unpack_from(raw, offset)
        if (
            len(sha) != 20
            or sha in seen
            or reserved != 0
            or not 0 < length <= _MAX_CHUNK
            or location + length > size
        ):
            raise CDNError("CSM chunk index is invalid")
        seen.add(sha)
        entries.append(ChunkEntry(sha, location, length))
        intervals.append((location, location + length))
    intervals.sort()
    if any(a[1] > b[0] for a, b in pairwise(intervals)):
        raise CDNError("CSM chunk offsets overlap")
    return ChunkContainer(depot_id, version == 3, csd, tuple(entries))


def write_csm_csd(
    target: Path,
    depot_id: int,
    chunks: tuple[tuple[bytes, bytes], ...],
    *,
    overwrite: bool = False,
    encrypted: bool = True,
) -> ChunkContainer:
    """Write a verified encrypted chunk sequence to a new CSD/CSM pair."""
    if depot_id <= 0 or not chunks or len(chunks) > _MAX_CHUNKS:
        raise CDNError("invalid depot or empty chunk sequence")
    csd, csm = target.with_suffix(".csd"), target.with_suffix(".csm")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and (csd.exists() or csm.exists()):
        raise CDNError("SIS output exists; use --overwrite")
    seen: set[bytes] = set()
    entries: list[ChunkEntry] = []
    descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-csd-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            for sha, raw in chunks:
                if len(sha) != 20 or sha in seen or not 0 < len(raw) <= _MAX_CHUNK:
                    raise CDNError("invalid or duplicate SIS chunk")
                seen.add(sha)
                offset = output.tell()
                output.write(raw)
                entries.append(ChunkEntry(sha, offset, len(raw)))
            output.flush()
            os.fsync(output.fileno())
        version = 3 if encrypted else 2
        index = bytearray(
            _CSM_HEADER.pack(b"SCFS", _CSM_HEADER.size, version, depot_id, len(entries))
        )
        for item in entries:
            index.extend(_CSM_ENTRY.pack(item.sha, item.offset, 0, item.length))
        if len(index) > _MAX_CSM:
            raise CDNError("CSM index exceeds size limit")
        fd, temporary_index = tempfile.mkstemp(prefix=".pysteam-csm-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(index)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, csd)
            os.replace(temporary_index, csm)
        finally:
            if os.path.exists(temporary_index):
                os.unlink(temporary_index)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return inspect_csm(csm)


@dataclass(frozen=True, slots=True)
class SISBackup:
    path: Path
    app_id: int
    manifests: dict[int, int]
    containers: tuple[ChunkContainer, ...]


def _parse_sis(raw: bytes) -> dict[str, object]:
    if not raw or len(raw) > _MAX_SIS:
        raise CDNError("SIS metadata size is invalid")
    tokens = _tokens(raw)
    if len(tokens) < 3 or tokens[0].casefold() != "sku" or tokens[1] != "{":
        raise CDNError("SIS metadata has no sku root")
    position = 2

    def obj(depth: int) -> dict[str, object]:
        nonlocal position
        if depth > 16:
            raise CDNError("SIS metadata nesting exceeds limit")
        result: dict[str, object] = {}
        while position < len(tokens):
            key = tokens[position]
            position += 1
            if key == "}":
                return result
            if key == "{" or position >= len(tokens) or key in result:
                raise CDNError("SIS metadata is malformed")
            value = tokens[position]
            position += 1
            if value == "{":
                result[key] = obj(depth + 1)
            elif value == "}":
                raise CDNError("SIS metadata is malformed")
            else:
                result[key] = value
        raise CDNError("SIS metadata is truncated")

    result = obj(1)
    if position != len(tokens):
        raise CDNError("SIS metadata has trailing tokens")
    return result


def inspect_sis(path: Path) -> SISBackup:
    if path.suffix.lower() != ".sis" or path.is_symlink() or not path.is_file():
        raise CDNError("expected a regular sku.sis file")
    try:
        if path.stat().st_size > _MAX_SIS:
            raise CDNError("SIS metadata exceeds size limit")
        data = _parse_sis(path.read_bytes())
        apps, manifests, chunkstores = data["apps"], data["manifests"], data["chunkstores"]
        if (
            not isinstance(apps, dict)
            or not isinstance(manifests, dict)
            or not isinstance(chunkstores, dict)
        ):
            raise ValueError
        app_id = int(apps["0"])
        mapped: dict[int, int] = {}
        containers: list[ChunkContainer] = []
        for depot_text, manifest_text in manifests.items():
            depot_id, manifest_id = int(depot_text), int(manifest_text)
            if depot_id <= 0 or manifest_id <= 0:
                raise ValueError
            mapped[depot_id] = manifest_id
            slots = chunkstores[depot_text]
            if not isinstance(slots, dict):
                raise ValueError
            for disk_text in slots:
                disk = int(disk_text)
                if not 1 <= disk <= 1000:
                    raise ValueError
                name = f"{depot_id}_depotcache_{disk}.csm"
                candidate = path.parent / name
                if not candidate.exists():
                    candidate = path.parent / f"Disk_{disk}" / name
                container = inspect_csm(candidate)
                if container.depot_id != depot_id:
                    raise CDNError("SIS container depot ID mismatch")
                containers.append(container)
        if app_id <= 0 or not mapped or not containers:
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError):
        raise CDNError("SIS metadata is invalid or incomplete") from None
    return SISBackup(path, app_id, mapped, tuple(containers))


def write_sis(
    path: Path,
    app_id: int,
    manifests: dict[int, int],
    *,
    overwrite: bool = False,
    slots: dict[int, tuple[int, ...]] | None = None,
) -> None:
    if app_id <= 0 or not manifests or (path.exists() and not overwrite):
        raise CDNError("SIS output exists or metadata is invalid")
    lines = [
        '"sku"',
        "{",
        '  "name" "pysteam archive"',
        '  "disks" "1"',
        '  "disk" "1"',
        '  "backup" "0"',
        '  "contenttype" "3"',
        '  "apps" { "0" "' + str(app_id) + '" }',
        '  "manifests"',
        "  {",
    ]
    for depot_id, manifest_id in sorted(manifests.items()):
        lines.append(f'    "{depot_id}" "{manifest_id}"')
    lines += ["  }", '  "chunkstores"', "  {"]
    for depot_id in sorted(manifests):
        numbers = (slots or {}).get(depot_id, (1,))
        items = " ".join(f'"{number}" "1"' for number in numbers)
        lines.append(f'    "{depot_id}" {{ {items} }}')
    lines += ["  }", "}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-sis-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_sis(
    store: ArchiveStore,
    app_id: int,
    output: Path,
    *,
    overwrite: bool = False,
) -> SISBackup:
    """Export complete archive manifests and encrypted chunks as one SIS backup."""
    records = [item for item in store.list() if item.app_id == app_id and item.complete]
    if not records:
        raise CDNError("no complete archived depots for this app")
    latest = {item.depot_id: item for item in records}
    if (output / "sku.sis").exists() and not overwrite:
        raise CDNError("SIS output exists; use --overwrite")
    prepared: list[tuple[int, int, tuple[tuple[bytes, bytes], ...]]] = []
    for depot_id, record in sorted(latest.items()):
        _, missing = store.verify(depot_id, record.manifest_id)
        if missing:
            raise CDNError("archive is incomplete or corrupt; export refused")
        manifest = store.manifest(depot_id, record.manifest_id)
        chunk_map = {chunk.sha: chunk for file in manifest.files for chunk in file.chunks}
        prepared.append(
            (
                depot_id,
                record.manifest_id,
                tuple(
                    (sha, store._chunk_path(depot_id, chunk).read_bytes())
                    for sha, chunk in sorted(chunk_map.items())
                ),
            )
        )
    output.mkdir(parents=True, exist_ok=True)
    for depot_id, manifest_id, chunks in prepared:
        write_csm_csd(output / f"{depot_id}_depotcache_1", depot_id, chunks, overwrite=overwrite)
        manifest_output = output / "manifests" / str(depot_id) / f"{manifest_id}.manifest"
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        if manifest_output.exists() and not overwrite:
            raise CDNError("SIS manifest sidecar exists; use --overwrite")
        manifest_output.write_bytes(store.manifest(depot_id, manifest_id).raw)
    write_sis(
        output / "sku.sis",
        app_id,
        {depot_id: manifest_id for depot_id, manifest_id, _ in prepared},
        overwrite=overwrite,
    )
    return inspect_sis(output / "sku.sis")


def _encrypt_decrypted_chunk(raw: bytes, key: bytes) -> bytes:
    iv = os.urandom(16)
    padder = PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()
    iv_cipher = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return iv_cipher.update(iv) + iv_cipher.finalize() + cipher.update(padded) + cipher.finalize()


def import_sis(store: ArchiveStore, backup: SISBackup) -> dict[int, bool]:
    """Import chunks only when a matching original manifest and depot key exist."""
    from pysteam.content.archive import ArchiveRecord

    results: dict[int, bool] = {}
    for depot_id, manifest_id in backup.manifests.items():
        manifest = store.manifest(depot_id, manifest_id)
        key = store.get_key(depot_id)
        chunks = {chunk.sha: chunk for file in manifest.files for chunk in file.chunks}
        store.save_manifest(manifest, app_id=backup.app_id, branch="public")
        for container in backup.containers:
            if container.depot_id != depot_id:
                continue
            for entry in container.entries:
                chunk = chunks.get(entry.sha)
                if chunk is None:
                    continue
                raw = container.read_chunk(entry)
                if not container.encrypted:
                    raw = _encrypt_decrypted_chunk(raw, key)
                store.save_chunk(depot_id, chunk, raw, key)
        checked, missing = store.verify(depot_id, manifest_id)
        complete = missing == 0
        if complete:
            store.mark_complete(
                ArchiveRecord(
                    backup.app_id,
                    depot_id,
                    manifest_id,
                    "public",
                    True,
                    hashlib.sha256(manifest.raw).hexdigest(),
                    checked,
                    0,
                )
            )
        results[depot_id] = complete
    return results


def repack_sis(backup: SISBackup, output: Path, *, overwrite: bool = False) -> SISBackup:
    """Normalize an encrypted legacy backup without modifying its source files."""
    if output.resolve().is_relative_to(backup.path.parent.resolve()):
        raise CDNError("repacked output must be outside the source directory")
    if any(not item.encrypted for item in backup.containers):
        raise CDNError("repacking decrypted SIS containers requires import with depot keys")
    if (output / "sku.sis").exists() and not overwrite:
        raise CDNError("SIS output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    slots: dict[int, list[int]] = {}
    for container in backup.containers:
        disk = len(slots.setdefault(container.depot_id, [])) + 1
        slots[container.depot_id].append(disk)
        target = output / f"{container.depot_id}_depotcache_{disk}"
        write_csm_csd(
            target,
            container.depot_id,
            tuple((entry.sha, container.read_chunk(entry)) for entry in container.entries),
            overwrite=overwrite,
        )
    write_sis(
        output / "sku.sis",
        backup.app_id,
        backup.manifests,
        overwrite=overwrite,
        slots={depot: tuple(disks) for depot, disks in slots.items()},
    )
    return inspect_sis(output / "sku.sis")
