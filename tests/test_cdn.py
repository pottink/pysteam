import base64
import hashlib
import io
import lzma
import struct
import zipfile
import zlib

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from pysteam import CDNClient, CDNError, CDNHTTPError, DepotChunk, parse_manifest, process_chunk
from pysteam.content.cdn import _decompress_chunk
from pysteam.proto import steammessages_contentsystem_steamclient_pb2 as content_proto
from pysteam.proto.content_manifest_pb2 import (
    ContentManifestMetadata,
    ContentManifestPayload,
    ContentManifestSignature,
)


def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    iv = bytes(range(16))
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = cipher.update(padded) + cipher.finalize()
    iv_cipher = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return iv_cipher.update(iv) + iv_cipher.finalize() + ciphertext


def _manifest(filename: str, *, encrypted: bool = False) -> bytes:
    payload = ContentManifestPayload()
    entry = payload.mappings.add()
    entry.filename = filename
    entry.size = 0
    entry.sha_content = hashlib.sha1(b"").digest()
    metadata = ContentManifestMetadata(
        depot_id=123, gid_manifest=456, filenames_encrypted=encrypted
    )
    signature = ContentManifestSignature(signature=b"test-signature")
    parts = ((0x71F617D0, payload), (0x1F4812BE, metadata), (0x1B81B817, signature))
    return b"".join(
        struct.pack("<II", marker, len(item.SerializeToString())) + item.SerializeToString()
        for marker, item in parts
    ) + struct.pack("<I", 0x32C415AB)


def test_manifest_filename_and_path_regressions() -> None:
    key = bytes(range(32))
    filename = base64.b64encode(_encrypt(b"folder/file.txt\x00", key)).decode("ascii")
    manifest = parse_manifest(_manifest(filename, encrypted=True), depot_key=key)
    assert manifest.file("folder/file.txt").name == "folder/file.txt"
    assert not manifest.filenames_encrypted
    assert parse_manifest(_manifest(filename, encrypted=True)).filenames_encrypted
    wrapped = filename[:32] + "\r\n" + filename[32:] + "\n"
    assert (
        parse_manifest(_manifest(wrapped, encrypted=True), depot_key=key)
        .file("folder/file.txt")
        .name
        == "folder/file.txt"
    )
    with pytest.raises(CDNError, match="encrypted filename is invalid"):
        parse_manifest(
            _manifest(filename[:32] + "!" + filename[32:], encrypted=True), depot_key=key
        )
    for unsafe in ("../escape", "/absolute", "C:\\file", "a//b", "a/./b"):
        with pytest.raises(CDNError):
            parse_manifest(_manifest(unsafe))
    with pytest.raises(CDNError):
        parse_manifest(_manifest("fine") + b"trailing")


def test_encrypted_zip_chunk_integrity() -> None:
    key = bytes(range(32))
    clear = b"pysteam chunk data"
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("chunk", clear)
    encrypted = _encrypt(archive_data.getvalue(), key)
    crc = 0
    # Steam depot chunks use Adler32 with a zero seed.
    for value in clear:
        a = crc & 0xFFFF
        b = crc >> 16
        a = (a + value) % 65521
        b = (b + a) % 65521
        crc = b << 16 | a
    chunk = DepotChunk(hashlib.sha1(clear).digest(), crc, 0, len(clear), len(encrypted))
    assert process_chunk(encrypted, key, chunk) == clear
    with pytest.raises(CDNError):
        process_chunk(
            encrypted,
            key,
            DepotChunk(hashlib.sha1(clear).digest(), crc + 1, 0, len(clear), len(encrypted)),
        )


def test_vzip_bounded_decompression() -> None:
    clear = b"abc" * 100
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 4096, "lc": 3, "lp": 0, "pb": 2}]
    raw = lzma.compress(clear, format=lzma.FORMAT_RAW, filters=filters)
    properties = bytes([3 + 9 * (0 + 5 * 2)]) + struct.pack("<I", 4096)
    crc = zlib.crc32(clear)
    envelope = (
        b"VZa"
        + struct.pack("<I", crc)
        + properties
        + raw
        + struct.pack("<II", crc, len(clear))
        + b"zv"
    )
    assert _decompress_chunk(envelope, 300) == clear
    with pytest.raises(CDNError):
        _decompress_chunk(envelope, 100)


def test_vzip_stream_without_end_marker_stops_at_declared_size() -> None:
    clear = b"abcde" * 2000
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 20, "lc": 3, "lp": 0, "pb": 2}]
    encoded = lzma.compress(clear, format=lzma.FORMAT_RAW, filters=filters)
    # Replace the encoder's end marker with trailing data, as seen in Steam chunks.
    stream = encoded[:-7] + bytes.fromhex("f5b165224a58b791")
    crc = zlib.crc32(clear)
    envelope = (
        b"VZa"
        + struct.pack("<I", crc)
        + bytes([3 + 9 * (5 * 2)])
        + struct.pack("<I", 1 << 20)
        + stream
        + struct.pack("<II", crc, len(clear))
        + b"zv"
    )
    assert _decompress_chunk(envelope, len(clear)) == clear
    tampered = envelope[:-10] + struct.pack("<II", crc ^ 1, len(clear)) + b"zv"
    with pytest.raises(CDNError, match="checksum"):
        _decompress_chunk(tampered, len(clear))


@pytest.mark.asyncio
async def test_cdn_auth_um() -> None:
    class FakeClient:
        async def call_um(self, name, request, _response_type):
            assert name == "ContentServerDirectory.GetCDNAuthToken#1"
            assert (request.app_id, request.depot_id, request.host_name) == (570, 571, "cdn.test")
            return content_proto.CContentServerDirectory_GetCDNAuthToken_Response(
                token="test-token"
            )

    assert (
        await CDNClient(FakeClient(), http=None).get_auth_token(570, 571, "cdn.test")
        == "test-token"
    )


@pytest.mark.asyncio
async def test_manifest_request_code_uses_selected_branch() -> None:
    class FakeClient:
        async def call_um(self, name, request, _response_type):
            assert name == "ContentServerDirectory.GetManifestRequestCode#1"
            assert (request.app_id, request.depot_id, request.manifest_id) == (570, 123, 456)
            assert (request.app_branch, request.branch_password_hash) == ("beta", "hash")
            return content_proto.CContentServerDirectory_GetManifestRequestCode_Response(
                manifest_request_code=42
            )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/depot/123/manifest/456/5/42"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("manifest", _manifest("beta.txt"))
        return httpx.Response(200, content=output.getvalue())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        manifest = await CDNClient(FakeClient(), http=http).get_manifest(
            server="https://cdn.test",
            app_id=570,
            depot_id=123,
            manifest_id=456,
            branch="beta",
            branch_password_hash="hash",
        )
        assert manifest.files[0].name == "beta.txt"


@pytest.mark.asyncio
async def test_manifest_refetch() -> None:
    responses = ["first.txt", "second.txt"]

    async def handler(_request: httpx.Request) -> httpx.Response:
        name = responses.pop(0)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("manifest", _manifest(name))
        return httpx.Response(200, content=output.getvalue())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        cdn = CDNClient(None, http=http)
        arguments = dict(
            server="https://cdn.test",
            app_id=570,
            depot_id=123,
            manifest_id=456,
            request_code=1,
        )
        assert (await cdn.get_manifest(**arguments)).files[0].name == "first.txt"
        assert (await cdn.get_manifest(**arguments)).files[0].name == "second.txt"


@pytest.mark.asyncio
async def test_cdn_http_error_redacts_token() -> None:
    async def denied(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(denied)) as http:
        cdn = CDNClient(None, http=http)
        with pytest.raises(CDNHTTPError) as captured:
            await cdn.get_manifest(
                server="https://cdn.test",
                app_id=570,
                depot_id=123,
                manifest_id=456,
                request_code=1,
                auth_token="token=private-test-token",
            )
        assert captured.value.status_code == 401
        assert captured.value.__cause__ is None
        assert "private-test-token" not in str(captured.value)
