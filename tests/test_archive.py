"""Offline archive and downloader contract tests with synthetic Steam packets."""

from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from typer.testing import CliRunner

import pysteam.cli as cli
from pysteam import (
    ArchiveStore,
    CDNError,
    ContentArchiver,
    DepotManifest,
    WorkshopItem,
    parse_manifest,
)
from pysteam.accounts.vault import Vault
from pysteam.proto.content_manifest_pb2 import (
    ContentManifestMetadata,
    ContentManifestPayload,
    ContentManifestSignature,
)

KEY = bytes(range(32))
PASSWORD = "a-strong-vault-password"
CONTENT = b"an archived Steam file\n"


def _encrypted_chunk(clear: bytes) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("content", clear)
    padder = PKCS7(128).padder()
    padded = padder.update(archive.getvalue()) + padder.finalize()
    iv = bytes(range(16))
    cbc = Cipher(algorithms.AES(KEY), modes.CBC(iv)).encryptor()
    ecb = Cipher(algorithms.AES(KEY), modes.ECB()).encryptor()
    return ecb.update(iv) + ecb.finalize() + cbc.update(padded) + cbc.finalize()


def _adler32_zero(clear: bytes) -> int:
    a = b = 0
    for item in clear:
        a = (a + item) % 65521
        b = (b + a) % 65521
    return b << 16 | a


def _manifest(clear: bytes = CONTENT) -> tuple[DepotManifest, bytes]:
    encrypted = _encrypted_chunk(clear)
    payload = ContentManifestPayload()
    file = payload.mappings.add()
    file.filename = "folder/content.txt"
    file.size = len(clear)
    file.sha_content = hashlib.sha1(clear).digest()
    chunk = file.chunks.add()
    chunk.sha = hashlib.sha1(clear).digest()
    chunk.crc = _adler32_zero(clear)
    chunk.offset = 0
    chunk.cb_original = len(clear)
    chunk.cb_compressed = len(encrypted)
    metadata = ContentManifestMetadata(depot_id=123, gid_manifest=456)
    signature = ContentManifestSignature(signature=b"fixture")
    parts = ((0x71F617D0, payload), (0x1F4812BE, metadata), (0x1B81B817, signature))
    raw = b"".join(
        struct.pack("<II", marker, len(item.SerializeToString())) + item.SerializeToString()
        for marker, item in parts
    ) + struct.pack("<I", 0x32C415AB)
    return parse_manifest(raw), encrypted


def test_appinfo_original_bytes_and_integrity(tmp_path: Path) -> None:
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    assert store.save_appinfo(220, b"PICS metadata") == (
        hashlib.sha256(b"PICS metadata").hexdigest(),
        True,
    )
    assert store.save_appinfo(220, b"PICS metadata")[1] is False
    assert store.appinfo_ids() == (220,)
    assert store.appinfo(220) == b"PICS metadata"
    digest = hashlib.sha256(b"PICS metadata").hexdigest()
    (store.root / "appinfo" / "220" / f"{digest}.bin").write_bytes(b"corrupt")
    with pytest.raises(CDNError, match="corrupt"):
        store.appinfo(220)


def test_legacy_sha_chunk_folder_import(tmp_path: Path) -> None:
    manifest, encrypted = _manifest()
    legacy = tmp_path / "legacy" / "depots" / "123"
    legacy.mkdir(parents=True)
    with zipfile.ZipFile(legacy / "456.zip", "w") as output:
        output.writestr("manifest", manifest.raw)
    chunk_path = legacy / manifest.files[0].chunks[0].sha.hex()
    chunk_path.write_bytes(encrypted)
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    record = store.import_legacy(
        tmp_path / "legacy", app_id=220, depot_id=123, manifest_id=456, key=KEY
    )
    assert record.complete and store.verify(123, 456) == (1, 0)
    assert chunk_path.read_bytes() == encrypted


class FakeCDN:
    def __init__(self, manifest: DepotManifest, chunk: bytes) -> None:
        self.manifest = manifest
        self.chunk = chunk
        self.calls = 0
        self.fail = False

    async def get_depot_key(self, _app_id: int, _depot_id: int) -> bytes:
        return KEY

    async def servers(self) -> tuple[str, ...]:
        return ("https://cdn.invalid",)

    async def get_manifest(self, **_kwargs: object) -> DepotManifest:
        return self.manifest

    async def get_chunk(self, **_kwargs: object) -> bytes:
        self.calls += 1
        if self.fail:
            raise CDNError("fixture failure")
        return self.chunk


class FakeSteam:
    def __init__(self, cdn: FakeCDN) -> None:
        self.cdn = cdn

    async def get_app_manifest_ids(self, _app_id: int, *, branch: str) -> dict[int, int]:
        return {123: 456}


@pytest.mark.asyncio
async def test_archive_resume_extract_rekey_and_corruption(tmp_path: Path) -> None:
    manifest, encrypted = _manifest()
    cdn = FakeCDN(manifest, encrypted)
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    archiver = ContentArchiver(FakeSteam(cdn), store, max_downloads=2)  # type: ignore[arg-type]

    cdn.fail = True
    with pytest.raises(CDNError, match="could not be downloaded"):
        await archiver.archive_depot(220, 123)
    assert not store.list()[0].complete

    cdn.fail = False
    first = await archiver.archive_depot(220, 123)
    assert first.chunks_downloaded == 1
    assert store.list()[0].complete
    assert store.verify(123, 456) == (1, 0)
    assert store.extract(123, 456, tmp_path / "out")[0].read_bytes() == CONTENT
    with pytest.raises(CDNError, match="exists"):
        store.extract(123, 456, tmp_path / "out")

    calls = cdn.calls
    second = await archiver.archive_depot(220, 123)
    assert second.chunks_reused == 1 and cdn.calls == calls
    store.rekey("another-strong-password")
    with pytest.raises(Exception, match="wrong archive password"):
        ArchiveStore(store.root, PASSWORD).get_key(123)
    moved = ArchiveStore(store.root, "another-strong-password")
    assert moved.extract(123, 456, tmp_path / "restored")[0].read_bytes() == CONTENT

    chunk = manifest.files[0].chunks[0]
    moved._chunk_path(123, chunk).write_bytes(b"x" * len(encrypted))
    assert moved.verify(123, 456)[1] > 0
    with pytest.raises(CDNError):
        moved.extract(123, 456, tmp_path / "corrupt")


@pytest.mark.asyncio
async def test_workshop_steampipe_archives_through_depot(tmp_path: Path) -> None:
    manifest, encrypted = _manifest()
    steam = FakeSteam(FakeCDN(manifest, encrypted))

    class Workshop:
        async def get_details(self, published_file_id: int) -> WorkshopItem:
            return WorkshopItem(
                published_file_id, 123, 456, "fixture", "", len(CONTENT), b"fixture-proto"
            )

    steam.workshop = Workshop()  # type: ignore[attr-defined]
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    result = await ContentArchiver(steam, store).archive_workshop(42)  # type: ignore[arg-type]
    assert result.source == "steampipe" and result.depot is not None
    assert (store.root / "workshop" / "42" / "metadata.json").is_file()


@pytest.mark.asyncio
async def test_workshop_external_https_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Workshop:
        async def get_details(self, published_file_id: int) -> WorkshopItem:
            return WorkshopItem(
                published_file_id, 123, 0, "fixture", "https://source.test/file", 0, b""
            )

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "source.test":
            return httpx.Response(302, headers={"location": "https://cdn.test/file"})
        return httpx.Response(200, content=CONTENT)

    original = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        "pysteam.content.archive.httpx.AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    steam = FakeSteam(FakeCDN(_manifest()[0], b""))
    steam.workshop = Workshop()  # type: ignore[attr-defined]
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    result = await ContentArchiver(steam, store).archive_workshop(42)  # type: ignore[arg-type]
    assert result.source == "external" and result.bytes_downloaded == len(CONTENT)
    digest = hashlib.sha256(CONTENT).hexdigest()
    assert (store.root / "workshop" / "42" / f"{digest}.bin").read_bytes() == CONTENT

    def insecure(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://cdn.test/file"})

    transport = httpx.MockTransport(insecure)
    with pytest.raises(CDNError, match="remain HTTPS"):
        await ContentArchiver(steam, store).archive_workshop(43)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cpu_process_worker_verifies_chunk(tmp_path: Path) -> None:
    manifest, encrypted = _manifest()
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    steam = FakeSteam(FakeCDN(manifest, encrypted))
    result = await ContentArchiver(
        steam,
        store,
        cpu_workers=1,  # type: ignore[arg-type]
    ).archive_depot(220, 123, manifest_id=456)
    assert result.chunks_downloaded == 1
    assert store.verify(123, 456) == (1, 0)


@pytest.mark.asyncio
async def test_memory_budget_reserves_whole_chunks() -> None:
    from pysteam.content.archive import _MemoryBudget

    budget = _MemoryBudget(64)
    active = 0
    peak = 0

    async def use_chunk() -> None:
        nonlocal active, peak
        await budget.acquire(50)
        try:
            active += 50
            peak = max(peak, active)
            await asyncio.sleep(0.01)
        finally:
            active -= 50
            await budget.release(50)

    import asyncio

    await asyncio.wait_for(asyncio.gather(*(use_chunk() for _ in range(3))), timeout=1)
    assert peak == 50 and budget.available == 64


def test_archive_offline_cli_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    Vault.create(PASSWORD, home)
    monkeypatch.setenv("PYSTEAM_HOME", str(home))
    monkeypatch.setenv("PYSTEAM_VAULT_PASSPHRASE", PASSWORD)
    manifest, encrypted = _manifest()
    archive = tmp_path / "archive"
    store = ArchiveStore(archive, PASSWORD)
    store.save_key(123, KEY)
    store.save_manifest(manifest, app_id=220, branch="public")
    store.save_chunk(123, manifest.files[0].chunks[0], encrypted, KEY)
    runner = CliRunner()
    listed = runner.invoke(cli.main, ["archive", "list", "--archive", str(archive), "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)[0]["complete"] is False
    for command, expected in (
        ("inspect", "folder/content.txt"),
        ("verify", '"missing_or_invalid": 0'),
    ):
        result = runner.invoke(
            cli.main, ["archive", command, "123", "456", "--archive", str(archive), "--json"]
        )
        assert result.exit_code == 0, result.output
        assert expected in result.output
    output = tmp_path / "restored"
    extracted = runner.invoke(
        cli.main,
        ["archive", "extract", "123", "456", "--archive", str(archive), "--output", str(output)],
    )
    assert extracted.exit_code == 0, extracted.output
    assert (output / "folder" / "content.txt").read_bytes() == CONTENT
    repeated = runner.invoke(
        cli.main,
        ["archive", "extract", "123", "456", "--archive", str(archive), "--output", str(output)],
    )
    assert repeated.exit_code != 0 and "--overwrite" in repeated.output


def test_archive_rejects_nonportable_paths_and_oversized_catalog(tmp_path: Path) -> None:
    from pysteam.content.archive import _extraction_parts

    for name in ("CON.txt", "folder/name.", "folder/name ", "folder/a?b"):
        with pytest.raises(CDNError, match="non-portable"):
            _extraction_parts(name)
    store = ArchiveStore(tmp_path / "archive", PASSWORD)
    store.initialize()
    (store.root / "archive.bin").write_bytes(b"x" * 100)
    with pytest.raises(CDNError, match="size limit"):
        store.initialize()
    (store.root / "archive.bin").write_bytes(b"PYSTEAM-ARCHIVE-1\0")
    catalog = store.root / "manifests" / "123" / "456.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"x" * 17000)
    with pytest.raises(CDNError, match="catalog is invalid"):
        store.list()
