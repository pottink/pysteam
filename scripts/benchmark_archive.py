"""Offline scheduler benchmark for 1, 8, and 16 concurrent chunk downloads.

The fake CDN adds 25 ms latency per request; this measures the archive
pipeline, not real Steam throughput. No account or network connection is used.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import struct
import tempfile
import time
import tracemalloc
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from pysteam import ArchiveStore, ContentArchiver, DepotManifest, parse_manifest
from pysteam.proto.content_manifest_pb2 import (
    ContentManifestMetadata,
    ContentManifestPayload,
    ContentManifestSignature,
)

KEY = bytes(range(32))
PASSWORD = "benchmark-password"


def _encrypt(clear: bytes) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("chunk", clear)
    padder = PKCS7(128).padder()
    padded = padder.update(archive.getvalue()) + padder.finalize()
    iv = bytes(range(16))
    ecb = Cipher(algorithms.AES(KEY), modes.ECB()).encryptor()
    cbc = Cipher(algorithms.AES(KEY), modes.CBC(iv)).encryptor()
    return ecb.update(iv) + ecb.finalize() + cbc.update(padded) + cbc.finalize()


def _adler(clear: bytes) -> int:
    a = b = 0
    for value in clear:
        a = (a + value) % 65521
        b = (b + a) % 65521
    return b << 16 | a


def _fixture(count: int = 64) -> tuple[DepotManifest, dict[bytes, bytes]]:
    payload = ContentManifestPayload()
    chunks: dict[bytes, bytes] = {}
    for index in range(count):
        clear = hashlib.shake_256(str(index).encode()).digest(64 * 1024)
        sha = hashlib.sha1(clear).digest()
        encrypted = _encrypt(clear)
        entry = payload.mappings.add()
        entry.filename = f"file-{index:03}.bin"
        entry.size = len(clear)
        entry.sha_content = sha
        chunk = entry.chunks.add()
        chunk.sha = sha
        chunk.crc = _adler(clear)
        chunk.offset = 0
        chunk.cb_original = len(clear)
        chunk.cb_compressed = len(encrypted)
        chunks[sha] = encrypted
    sections = (
        (0x71F617D0, payload),
        (0x1F4812BE, ContentManifestMetadata(depot_id=123, gid_manifest=456)),
        (0x1B81B817, ContentManifestSignature(signature=b"benchmark")),
    )
    raw = b"".join(
        struct.pack("<II", marker, len(message.SerializeToString())) + message.SerializeToString()
        for marker, message in sections
    ) + struct.pack("<I", 0x32C415AB)
    return parse_manifest(raw), chunks


class FakeCDN:
    def __init__(self, manifest: DepotManifest, chunks: dict[bytes, bytes]) -> None:
        self.manifest = manifest
        self.chunks = chunks

    async def get_depot_key(self, _app_id: int, _depot_id: int) -> bytes:
        return KEY

    async def servers(self) -> tuple[str, ...]:
        return ("https://fixture.invalid",)

    async def get_manifest(self, **_kwargs: object) -> DepotManifest:
        return self.manifest

    async def get_chunk(self, **kwargs: object) -> bytes:
        await asyncio.sleep(0.025)
        chunk = kwargs["chunk"]
        return self.chunks[chunk.sha]  # type: ignore[attr-defined]


class FakeSteam:
    def __init__(self, cdn: FakeCDN) -> None:
        self.cdn = cdn


async def main() -> None:
    manifest, chunks = _fixture()
    rows: list[dict[str, float | int]] = []
    for workers in (1, 8, 16):
        with tempfile.TemporaryDirectory(prefix="pysteam-benchmark-") as temporary:
            client = FakeSteam(FakeCDN(manifest, chunks))
            store = ArchiveStore(Path(temporary) / "archive", PASSWORD)
            tracemalloc.start()
            cpu_start = time.process_time()
            wall_start = time.perf_counter()
            result = await ContentArchiver(
                client,
                store,
                max_downloads=workers,  # type: ignore[arg-type]
            ).archive_depot(220, 123, manifest_id=456)
            wall = time.perf_counter() - wall_start
            cpu = time.process_time() - cpu_start
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            rows.append(
                {
                    "workers": workers,
                    "seconds": round(wall, 3),
                    "mib_per_second": round(result.bytes_downloaded / wall / 1048576, 2),
                    "cpu_seconds": round(cpu, 3),
                    "peak_python_mib": round(peak / 1048576, 2),
                }
            )
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
