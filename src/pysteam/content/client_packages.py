"""Archive signed-by-hash Steam client update packages from live update hosts."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
import msgspec

from pysteam.content.pics import KVValue, parse_vdf_document
from pysteam.errors import CDNError, TransportError
from pysteam.proto import steammessages_contentsystem_steamclient_pb2 as content

if TYPE_CHECKING:
    from pysteam.client import SteamClient

_NAME = re.compile(r"^[a-z0-9_]{4,100}$")
_FILE = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_MANIFEST = 16 * 1024 * 1024
_MAX_PACKAGE = 4 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ClientPackage:
    filename: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ClientArchiveResult:
    name: str
    version: str
    packages: int
    downloaded: int


def parse_client_manifest(
    raw: bytes, name: str, *, package_format: str = "zip"
) -> tuple[str, tuple[ClientPackage, ...]]:
    if len(raw) > _MAX_MANIFEST or not _NAME.fullmatch(name):
        raise CDNError("client manifest name or size is invalid")
    platform = name.rsplit("_", 1)[-1]
    document = parse_vdf_document(raw)
    data = document.get(platform)
    if data is None:
        raise CDNError("client manifest platform mismatch")
    version = data.get("version")
    if not isinstance(version, str) or not version.isdecimal():
        raise CDNError("client manifest version is invalid")
    if package_format not in ("zip", "vz", "both"):
        raise ValueError("package format must be zip, vz, or both")
    packages: dict[str, ClientPackage] = {}

    def walk(value: dict[str, KVValue]) -> None:
        fields = (("file", "sha2"), ("zipvz", "sha2vz"))
        for filename_key, hash_key in fields:
            if package_format == "zip" and filename_key != "file":
                continue
            if package_format == "vz" and filename_key == "file" and value.get("zipvz"):
                continue
            filename, sha = value.get(filename_key), value.get(hash_key)
            if filename is None or sha is None:
                continue
            if (
                not isinstance(filename, str)
                or not isinstance(sha, str)
                or not _FILE.fullmatch(filename)
                or not _HASH.fullmatch(sha)
            ):
                raise CDNError("client package filename or checksum is invalid")
            earlier = packages.get(filename)
            item = ClientPackage(filename, sha.lower())
            if earlier is not None and earlier != item:
                raise CDNError("client manifest has a conflicting package name")
            packages[filename] = item
        for nested in value.values():
            if isinstance(nested, dict):
                walk(nested)

    walk(data)
    if not packages or len(packages) > 10_000:
        raise CDNError("client manifest has no valid packages")
    return version, tuple(sorted(packages.values(), key=lambda item: item.filename))


class ClientPackageArchiver:
    def __init__(self, client: SteamClient, root: Path, *, max_downloads: int = 8) -> None:
        if not 1 <= max_downloads <= 64:
            raise ValueError("invalid download concurrency")
        self.client = client
        self.root = root
        self.max_downloads = max_downloads

    async def _hosts(self) -> tuple[str, ...]:
        response = await self.client.call_um(
            "ContentServerDirectory.GetClientUpdateHosts#1",
            content.CContentServerDirectory_GetClientUpdateHosts_Request(),
            content.CContentServerDirectory_GetClientUpdateHosts_Response,
        )
        document = parse_vdf_document(response.hosts_kv.encode("utf-8"))
        data = document.get("hosts")
        if data is None:
            raise CDNError("client update host response is invalid")
        realms = data.get("Realms")
        global_hosts = realms.get("SteamGlobal") if isinstance(realms, dict) else None
        if not isinstance(global_hosts, dict):
            raise CDNError("Steam returned no client update hosts")
        hosts: list[tuple[int, str]] = []
        for host, details in global_hosts.items():
            if not isinstance(details, dict) or details.get("https") != "1":
                continue
            if details.get("country_codes"):
                continue
            parsed = urlsplit("https://" + host)
            if parsed.hostname != host or parsed.username or parsed.password or parsed.port:
                continue
            base = details.get("base_url", "/")
            weight = details.get("weight", "1000")
            if not isinstance(base, str) or not base.startswith("/") or ".." in base:
                continue
            if not isinstance(weight, str) or not weight.isdecimal():
                continue
            hosts.append((int(weight), f"https://{host}{base.rstrip('/')}/"))
        if not hosts:
            raise CDNError("Steam returned no usable HTTPS client update hosts")
        return tuple(url for _, url in sorted(hosts))

    async def archive(
        self, name: str = "steam_client_win32", *, package_format: str = "zip"
    ) -> ClientArchiveResult:
        if not _NAME.fullmatch(name):
            raise ValueError("invalid Steam client channel name")
        hosts = await self._hosts()
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
            raw: bytes | None = None
            parsed: tuple[str, tuple[ClientPackage, ...]] | None = None
            for host in hosts:
                try:
                    async with http.stream("GET", host + name) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for piece in response.aiter_bytes():
                            data.extend(piece)
                            if len(data) > _MAX_MANIFEST:
                                raise CDNError("client manifest exceeds size limit")
                        raw = bytes(data)
                        parsed = parse_client_manifest(raw, name, package_format=package_format)
                    break
                except (httpx.HTTPError, CDNError):
                    continue
            if raw is None or parsed is None:
                raise TransportError("client update manifest could not be fetched")
            version, packages = parsed
            manifest_dir = self.root / "client" / name / version
            manifest_dir.mkdir(parents=True, exist_ok=True)
            _write_atomic(manifest_dir / "manifest.vdf", raw)
            semaphore = asyncio.Semaphore(self.max_downloads)
            downloaded = 0

            async def fetch(package: ClientPackage) -> None:
                nonlocal downloaded
                target = self.root / "client" / "objects" / package.sha256[:2] / package.sha256
                if target.exists() and _file_hash(target) == package.sha256:
                    return
                async with semaphore:
                    for host in hosts:
                        descriptor, temporary = tempfile.mkstemp(
                            prefix=".client-package-", dir=manifest_dir
                        )
                        try:
                            digest = hashlib.sha256()
                            size = 0
                            with os.fdopen(descriptor, "wb") as output:
                                async with http.stream("GET", host + package.filename) as response:
                                    response.raise_for_status()
                                    async for piece in response.aiter_bytes(1024 * 1024):
                                        size += len(piece)
                                        if size > _MAX_PACKAGE:
                                            raise CDNError("client package exceeds size limit")
                                        digest.update(piece)
                                        output.write(piece)
                                output.flush()
                                os.fsync(output.fileno())
                            if digest.hexdigest() != package.sha256:
                                raise CDNError("client package SHA-256 mismatch")
                            target.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(temporary, target)
                            downloaded += 1
                            return
                        except (httpx.HTTPError, CDNError):
                            continue
                        finally:
                            if os.path.exists(temporary):
                                os.unlink(temporary)
                    raise TransportError("client package could not be fetched")

            try:
                async with asyncio.TaskGroup() as group:
                    for package in packages:
                        group.create_task(fetch(package))
            except* (CDNError, TransportError) as group:
                raise group.exceptions[0] from None
            catalog = {
                "version": 1,
                "channel": name,
                "client_version": version,
                "packages": [{"file": item.filename, "sha256": item.sha256} for item in packages],
            }
            _write_atomic(manifest_dir / "catalog.json", msgspec.json.encode(catalog))
            return ClientArchiveResult(name, version, len(packages), downloaded)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for piece in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".client-archive-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
