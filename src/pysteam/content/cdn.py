"""Steam depot manifests, encrypted chunks, and verified file downloads."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import lzma
import os
import struct
import tempfile
import zipfile
import zlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
import zstandard
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from google.protobuf.message import DecodeError

from pysteam.errors import CDNError, CDNHTTPError, ProtocolError, SteamResultError, TransportError
from pysteam.proto import enums_clientserver_pb2 as emsg
from pysteam.proto import steammessages_clientserver_2_pb2 as cm_proto
from pysteam.proto import steammessages_contentsystem_steamclient_pb2 as content_proto
from pysteam.proto.content_manifest_pb2 import (
    ContentManifestMetadata,
    ContentManifestPayload,
    ContentManifestSignature,
)

if TYPE_CHECKING:
    from pysteam.client import SteamClient

_PAYLOAD_MAGIC = 0x71F617D0
_METADATA_MAGIC = 0x1F4812BE
_SIGNATURE_MAGIC = 0x1B81B817
_END_MAGIC = 0x32C415AB
_MAX_MANIFEST = 64 * 1024 * 1024
_MAX_CHUNK = 32 * 1024 * 1024
_CONTENT_SERVICE = "ContentServerDirectory."


def _relative_name(name: str) -> str:
    normalized = name.replace("\\", "/").rstrip("\x00")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or ":" in normalized
        or "\x00" in normalized
        or any(part in ("", ".", "..") for part in normalized.split("/"))
        or path.is_absolute()
    ):
        raise CDNError("manifest contains an unsafe file path")
    return str(path)


def _aes_decrypt(data: bytes, key: bytes) -> bytes:
    if len(key) != 32 or len(data) < 32 or len(data) % 16:
        raise CDNError("invalid encrypted depot data")
    iv_decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    iv = iv_decryptor.update(data[:16]) + iv_decryptor.finalize()
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(data[16:]) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise CDNError("depot data padding is invalid") from exc


def _decrypt_filename(value: str, key: bytes) -> str:
    try:
        encrypted = base64.b64decode(value, validate=True)
        clear = _aes_decrypt(encrypted, key).rstrip(b"\x00")
        return _relative_name(clear.decode("utf-8"))
    except (binascii.Error, UnicodeError) as exc:
        raise CDNError("encrypted filename is invalid") from exc


@dataclass(frozen=True, slots=True)
class DepotChunk:
    sha: bytes
    crc: int
    offset: int
    original_size: int
    compressed_size: int


@dataclass(frozen=True, slots=True)
class DepotFile:
    name: str
    size: int
    sha: bytes
    flags: int
    chunks: tuple[DepotChunk, ...]
    link_target: str | None = None


@dataclass(frozen=True, slots=True)
class DepotManifest:
    depot_id: int
    manifest_id: int
    filenames_encrypted: bool
    files: tuple[DepotFile, ...]
    signature: bytes
    raw: bytes = field(default=b"", repr=False)

    def file(self, name: str) -> DepotFile:
        wanted = _relative_name(name)
        for item in self.files:
            if item.name == wanted:
                return item
        raise KeyError(wanted)


def parse_manifest(data: bytes, *, depot_key: bytes | None = None) -> DepotManifest:
    """Parse a v5 protobuf manifest, rejecting truncated or ambiguous sections."""
    if len(data) > _MAX_MANIFEST:
        raise CDNError("manifest exceeds size limit")
    offset = 0
    sections: dict[int, bytes] = {}
    while True:
        if len(data) - offset < 4:
            raise CDNError("manifest is truncated")
        marker = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if marker == _END_MAGIC:
            if offset != len(data):
                raise CDNError("manifest has trailing data")
            break
        if marker not in {_PAYLOAD_MAGIC, _METADATA_MAGIC, _SIGNATURE_MAGIC} or marker in sections:
            raise CDNError("manifest has an invalid or repeated section")
        if len(data) - offset < 4:
            raise CDNError("manifest section length is truncated")
        size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if size > len(data) - offset:
            raise CDNError("manifest section exceeds input")
        sections[marker] = data[offset : offset + size]
        offset += size
    if set(sections) != {_PAYLOAD_MAGIC, _METADATA_MAGIC, _SIGNATURE_MAGIC}:
        raise CDNError("manifest is missing required sections")
    payload, metadata, signature = (
        ContentManifestPayload(),
        ContentManifestMetadata(),
        ContentManifestSignature(),
    )
    try:
        payload.ParseFromString(sections[_PAYLOAD_MAGIC])
        metadata.ParseFromString(sections[_METADATA_MAGIC])
        signature.ParseFromString(sections[_SIGNATURE_MAGIC])
    except DecodeError as exc:
        raise CDNError("manifest protobuf is invalid") from exc
    if metadata.filenames_encrypted and depot_key is not None and len(depot_key) != 32:
        raise ValueError("depot key must be 32 bytes")
    files: list[DepotFile] = []
    for mapping in payload.mappings:
        if len(mapping.sha_content) not in (0, 20):
            raise CDNError("manifest file checksum has invalid length")
        name = (
            _decrypt_filename(mapping.filename, depot_key)
            if metadata.filenames_encrypted and depot_key is not None
            else mapping.filename
            if metadata.filenames_encrypted
            else _relative_name(mapping.filename)
        )
        link = mapping.linktarget or None
        if link and not metadata.filenames_encrypted:
            link = _relative_name(link)
        elif link and depot_key is not None:
            link = _decrypt_filename(link, depot_key)
        chunks_list: list[DepotChunk] = []
        for chunk in mapping.chunks:
            if (
                len(chunk.sha) != 20
                or not 0 < chunk.cb_original <= _MAX_CHUNK
                or not 32 <= chunk.cb_compressed <= _MAX_CHUNK
            ):
                raise CDNError("manifest chunk metadata is invalid")
            chunks_list.append(
                DepotChunk(
                    chunk.sha,
                    chunk.crc,
                    chunk.offset,
                    chunk.cb_original,
                    chunk.cb_compressed,
                )
            )
        chunks = tuple(chunks_list)
        files.append(
            DepotFile(name, mapping.size, mapping.sha_content, mapping.flags, chunks, link)
        )
    return DepotManifest(
        metadata.depot_id,
        metadata.gid_manifest,
        bool(metadata.filenames_encrypted and depot_key is None),
        tuple(files),
        signature.signature,
        data,
    )


def _adler32_zero(data: bytes) -> int:
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def _decompress_chunk(data: bytes, maximum: int) -> bytes:
    if data.startswith(b"VSZa"):
        if len(data) < 23 or data[-3:] != b"zsv":
            raise CDNError("invalid Valve Zstd envelope")
        crc_head = struct.unpack_from("<I", data, 4)[0]
        crc_tail, expected = struct.unpack_from("<II", data, len(data) - 15)
        if crc_head != crc_tail or expected > maximum:
            raise CDNError("invalid Valve Zstd size or checksum header")
        try:
            result = zstandard.ZstdDecompressor().decompress(data[8:-15], max_output_size=maximum)
        except zstandard.ZstdError as exc:
            raise CDNError("Valve Zstd decompression failed") from exc
        if len(result) != expected or zlib.crc32(result) != crc_tail:
            raise CDNError("Valve Zstd checksum mismatch")
        return result
    if data.startswith(b"VZa"):
        if len(data) < 22 or data[-2:] != b"zv":
            raise CDNError("invalid Valve LZMA envelope")
        props = data[7]
        dictionary = struct.unpack_from("<I", data, 8)[0]
        crc, expected = struct.unpack_from("<II", data, len(data) - 10)
        if expected > maximum or dictionary > _MAX_CHUNK:
            raise CDNError("Valve LZMA size exceeds limit")
        lc, remainder = props % 9, props // 9
        lp, pb = remainder % 5, remainder // 5
        try:
            decompressor = lzma.LZMADecompressor(
                format=lzma.FORMAT_RAW,
                filters=[
                    {
                        "id": lzma.FILTER_LZMA1,
                        "dict_size": max(dictionary, 4096),
                        "lc": lc,
                        "lp": lp,
                        "pb": pb,
                    }
                ],
            )
            result = decompressor.decompress(data[12:-10], max_length=maximum + 1)
        except lzma.LZMAError as exc:
            raise CDNError("Valve LZMA decompression failed") from exc
        if len(result) != expected or zlib.crc32(result) != crc:
            raise CDNError("Valve LZMA checksum mismatch")
        return result
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                if len(archive.infolist()) != 1:
                    raise CDNError("depot chunk ZIP must contain one entry")
                with archive.open(archive.infolist()[0]) as stream:
                    result = stream.read(maximum + 1)
        except (OSError, zipfile.BadZipFile) as exc:
            raise CDNError("depot chunk ZIP is invalid") from exc
        if len(result) > maximum:
            raise CDNError("depot chunk ZIP exceeds size limit")
        return result
    raise CDNError("unrecognized depot chunk compression")


def process_chunk(encrypted: bytes, key: bytes, chunk: DepotChunk) -> bytes:
    if len(encrypted) > _MAX_CHUNK or len(encrypted) != chunk.compressed_size:
        raise CDNError("depot chunk compressed size mismatch")
    clear = _aes_decrypt(encrypted, key)
    result = _decompress_chunk(clear, min(chunk.original_size, _MAX_CHUNK))
    if len(result) != chunk.original_size or _adler32_zero(result) != chunk.crc:
        raise CDNError("depot chunk length or checksum mismatch")
    if hashlib.sha1(result).digest() != chunk.sha:
        raise CDNError("depot chunk SHA-1 mismatch")
    return result


class CDNClient:
    def __init__(self, client: SteamClient, *, http: httpx.AsyncClient) -> None:
        self._client = client
        self._http = http

    async def servers(self, *, max_servers: int = 20) -> tuple[str, ...]:
        request = content_proto.CContentServerDirectory_GetServersForSteamPipe_Request(
            cell_id=self._client.cell_id, max_servers=max_servers
        )
        response = await self._client.call_um(
            _CONTENT_SERVICE + "GetServersForSteamPipe#1",
            request,
            content_proto.CContentServerDirectory_GetServersForSteamPipe_Response,
        )
        hosts: list[str] = []
        for item in response.servers:
            if item.use_as_proxy or item.steam_china_only:
                continue
            host = item.vhost or item.host
            if host and "/" not in host and "@" not in host and ":" not in host:
                hosts.append(f"https://{host}")
        return tuple(hosts)

    async def get_manifest_request_code(
        self,
        app_id: int,
        depot_id: int,
        manifest_id: int,
        *,
        branch: str = "public",
        branch_password_hash: str = "",
    ) -> int:
        request = content_proto.CContentServerDirectory_GetManifestRequestCode_Request(
            app_id=app_id,
            depot_id=depot_id,
            manifest_id=manifest_id,
            app_branch=branch,
            branch_password_hash=branch_password_hash,
        )
        response = await self._client.call_um(
            _CONTENT_SERVICE + "GetManifestRequestCode#1",
            request,
            content_proto.CContentServerDirectory_GetManifestRequestCode_Response,
        )
        return response.manifest_request_code

    async def get_auth_token(self, app_id: int, depot_id: int, host_name: str) -> str:
        request = content_proto.CContentServerDirectory_GetCDNAuthToken_Request(
            app_id=app_id, depot_id=depot_id, host_name=host_name
        )
        response = await self._client.call_um(
            _CONTENT_SERVICE + "GetCDNAuthToken#1",
            request,
            content_proto.CContentServerDirectory_GetCDNAuthToken_Response,
        )
        return response.token

    async def get_depot_key(self, app_id: int, depot_id: int) -> bytes:
        request = cm_proto.CMsgClientGetDepotDecryptionKey(app_id=app_id, depot_id=depot_id)
        packets = await self._client._request(
            emsg.k_EMsgClientGetDepotDecryptionKey,
            request,
            emsg.k_EMsgClientGetDepotDecryptionKeyResponse,
        )
        response = cm_proto.CMsgClientGetDepotDecryptionKeyResponse()
        try:
            response.ParseFromString(packets[0].body)
        except DecodeError as exc:
            raise ProtocolError("invalid depot key response") from exc
        if response.eresult != 1:
            raise SteamResultError("get depot key", response.eresult)
        if len(response.depot_encryption_key) != 32:
            raise ProtocolError("depot key response has invalid length")
        return response.depot_encryption_key

    @staticmethod
    def _validate_server(server: str) -> str:
        parsed = urlsplit(server)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CDN server must be an HTTPS origin")
        return f"https://{parsed.netloc}"

    async def _get(self, url: str, *, auth_token: str = "", limit: int) -> bytes:
        params = auth_token.lstrip("?") if auth_token else None
        try:
            async with self._http.stream("GET", url, params=params) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for part in response.aiter_bytes():
                    total += len(part)
                    if total > limit:
                        raise CDNError("CDN response exceeds size limit")
                    chunks.append(part)
        except httpx.HTTPStatusError as exc:
            raise CDNHTTPError(exc.response.status_code) from None
        except httpx.HTTPError:
            raise TransportError("CDN request failed") from None
        return b"".join(chunks)

    async def get_manifest(
        self,
        *,
        server: str,
        app_id: int,
        depot_id: int,
        manifest_id: int,
        depot_key: bytes | None = None,
        auth_token: str = "",
        request_code: int | None = None,
        branch: str = "public",
        branch_password_hash: str = "",
    ) -> DepotManifest:
        origin = self._validate_server(server)
        code = (
            request_code
            if request_code is not None
            else await self.get_manifest_request_code(
                app_id,
                depot_id,
                manifest_id,
                branch=branch,
                branch_password_hash=branch_password_hash,
            )
        )
        suffix = f"/{code}" if code else ""
        url = f"{origin}/depot/{depot_id}/manifest/{manifest_id}/5{suffix}"
        raw = await self._get(url, auth_token=auth_token, limit=_MAX_MANIFEST)
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if len(archive.infolist()) != 1:
                    raise CDNError("manifest ZIP must contain one entry")
                with archive.open(archive.infolist()[0]) as stream:
                    manifest_data = stream.read(_MAX_MANIFEST + 1)
        except (OSError, zipfile.BadZipFile) as exc:
            raise CDNError("manifest ZIP is invalid") from exc
        manifest = parse_manifest(manifest_data, depot_key=depot_key)
        if manifest.depot_id != depot_id or manifest.manifest_id != manifest_id:
            raise CDNError("manifest identity does not match request")
        return manifest

    async def iter_file_chunks(
        self,
        *,
        server: str,
        manifest: DepotManifest,
        file: DepotFile,
        depot_key: bytes,
        auth_token: str = "",
    ) -> AsyncIterator[bytes]:
        if manifest.filenames_encrypted:
            raise CDNError("decrypt manifest filenames before accessing files")
        if len(depot_key) != 32:
            raise ValueError("depot key must be 32 bytes")
        origin = self._validate_server(server)
        digest = hashlib.sha1()
        position = 0
        for chunk in sorted(file.chunks, key=lambda item: item.offset):
            if chunk.offset != position or len(chunk.sha) != 20:
                raise CDNError("manifest file has a gap, overlap, or invalid chunk ID")
            encrypted = await self._get(
                f"{origin}/depot/{manifest.depot_id}/chunk/{chunk.sha.hex()}",
                auth_token=auth_token,
                limit=_MAX_CHUNK,
            )
            clear = process_chunk(encrypted, depot_key, chunk)
            position += len(clear)
            digest.update(clear)
            yield clear
        if position != file.size or (file.sha and digest.digest() != file.sha):
            raise CDNError("depot file size or SHA-1 mismatch")

    async def get_chunk(
        self,
        *,
        server: str,
        depot_id: int,
        chunk: DepotChunk,
        auth_token: str = "",
    ) -> bytes:
        origin = self._validate_server(server)
        return await self._get(
            f"{origin}/depot/{depot_id}/chunk/{chunk.sha.hex()}",
            auth_token=auth_token,
            limit=_MAX_CHUNK,
        )

    async def download_file(
        self,
        *,
        server: str,
        manifest: DepotManifest,
        file: DepotFile,
        depot_key: bytes,
        destination: Path,
        auth_token: str = "",
    ) -> None:
        """Stream to a temporary file and replace destination only after verification."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=".pysteam-", dir=destination.parent)
        try:
            with os.fdopen(handle, "wb") as output:
                async for chunk in self.iter_file_chunks(
                    server=server,
                    manifest=manifest,
                    file=file,
                    depot_key=depot_key,
                    auth_token=auth_token,
                ):
                    await asyncio.to_thread(output.write, chunk)
            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
