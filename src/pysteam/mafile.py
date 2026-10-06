"""Read Steam Guard maFiles without modifying the authenticator's storage."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import msgspec
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pysteam.credentials import LoginCredentials
from pysteam.errors import MaFileError

_MAX_FILE_BYTES = 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ImportedAuthenticator:
    """The login-relevant subset of one existing Steam Guard authenticator."""

    account_name: str
    credentials: LoginCredentials = field(repr=False)


def _read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as source:
            content = source.read(limit + 1)
    except OSError:
        raise MaFileError("could not read maFile or manifest") from None
    if len(content) > limit:
        raise MaFileError("maFile or manifest exceeds the size limit")
    return content


def _json_object(content: bytes) -> dict[str, Any]:
    try:
        value = msgspec.json.decode(content)
    except (msgspec.DecodeError, ValueError):
        raise MaFileError("invalid maFile or manifest JSON") from None
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MaFileError("invalid maFile or manifest JSON")
    return cast("dict[str, Any]", value)


def _decode_base64(value: object, *, length: int | None) -> bytes:
    if not isinstance(value, str):
        raise MaFileError("invalid maFile encryption metadata")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise MaFileError("invalid maFile encryption metadata") from None
    if (length is not None and len(decoded) != length) or (
        length is None and not 8 <= len(decoded) <= 64
    ):
        raise MaFileError("invalid maFile encryption metadata")
    return decoded


def _steam_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise MaFileError("invalid maFile SteamID")
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise MaFileError("invalid maFile SteamID")
    parsed = int(value)
    if not 0 < parsed <= 0xFFFFFFFFFFFFFFFF:
        raise MaFileError("invalid maFile SteamID")
    return parsed


def _manifest_entry(path: Path) -> dict[str, Any] | None:
    manifest_path = path.with_name("manifest.json")
    if not manifest_path.exists():
        return None
    manifest = _json_object(_read_bounded(manifest_path, _MAX_MANIFEST_BYTES))
    version = manifest.get("version")
    if version is not None and (type(version) is not int or version != 1):
        raise MaFileError("unsupported maFile manifest version")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise MaFileError("invalid maFile manifest entries")
    matches = [
        entry for entry in entries if isinstance(entry, dict) and entry.get("filename") == path.name
    ]
    if len(matches) != 1:
        raise MaFileError("maFile has no unique matching manifest entry")
    if version is None and manifest.get("encrypted") is True:
        if matches[0].get("encryption_iv") is None or matches[0].get("encryption_salt") is None:
            raise MaFileError("invalid maFile encryption metadata")
    return cast("dict[str, Any]", matches[0])


def _encryption(entry: dict[str, Any] | None) -> tuple[str, bytes, bytes] | None:
    if entry is None:
        return None
    modern = entry.get("encryption")
    if modern is not None:
        if not isinstance(modern, dict):
            raise MaFileError("invalid maFile encryption metadata")
        scheme = modern.get("scheme")
        if scheme not in ("Argon2idAes256", "LegacySdaCompatible"):
            raise MaFileError("unsupported maFile encryption scheme")
        salt_length = None if scheme == "Argon2idAes256" else 8
        return (
            scheme,
            _decode_base64(modern.get("salt"), length=salt_length),
            _decode_base64(modern.get("iv"), length=16),
        )
    salt = entry.get("encryption_salt")
    iv = entry.get("encryption_iv")
    if salt is None and iv is None:
        return None
    return (
        "LegacySdaCompatible",
        _decode_base64(salt, length=8),
        _decode_base64(iv, length=16),
    )


def _decrypt(content: bytes, scheme: str, salt: bytes, iv: bytes, passphrase: str | bytes) -> bytes:
    if not passphrase:
        raise MaFileError("a passphrase is required for this encrypted maFile")
    password = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase
    if scheme == "Argon2idAes256":
        key = Argon2id(salt=salt, length=32, iterations=3, lanes=12, memory_cost=12 * 1024).derive(
            password
        )
    else:
        key = PBKDF2HMAC(algorithm=hashes.SHA1(), length=32, salt=salt, iterations=50_000).derive(
            password
        )
    try:
        ciphertext = base64.b64decode(content.strip(), validate=True)
        if not ciphertext or len(ciphertext) % 16:
            raise ValueError("invalid ciphertext length")
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
    except (ValueError, binascii.Error):
        raise MaFileError("incorrect passphrase or corrupt encrypted maFile") from None


def load_mafile(
    path: str | Path, *, passphrase: str | bytes | None = None
) -> ImportedAuthenticator:
    """Import login details from one maFile, using its adjacent manifest when present.

    The source is read only. Passwords, tokens, confirmation secrets, and recovery
    codes in the source file are not included in the returned credentials.
    """
    source = Path(path)
    entry = _manifest_entry(source)
    encryption = _encryption(entry)
    content = _read_bounded(source, _MAX_FILE_BYTES)
    if encryption is not None:
        if passphrase is None:
            raise MaFileError("a passphrase is required for this encrypted maFile")
        content = _decrypt(content, *encryption, passphrase)
    elif not content.lstrip().startswith(b"{"):
        if entry is None:
            raise MaFileError("encrypted maFile requires an adjacent manifest")
        raise MaFileError("maFile is not plaintext JSON and has no encryption metadata")
    try:
        account = _json_object(content)
    except MaFileError:
        if encryption is not None:
            raise MaFileError("incorrect passphrase or corrupt encrypted maFile") from None
        raise
    name = account.get("account_name")
    if name is None and entry is not None:
        name = entry.get("account_name")
    if (
        not isinstance(name, str)
        or not 0 < len(name) <= 256
        or name != name.strip()
        or not name.isprintable()
    ):
        raise MaFileError("invalid maFile account name")
    account_id = account.get("steam_id", account.get("steamid"))
    manifest_id = entry.get("steam_id", entry.get("steamid")) if entry is not None else None
    steam_id = _steam_id(account_id if account_id is not None else manifest_id)
    secret = account.get("shared_secret")
    try:
        if not isinstance(secret, str) or len(base64.b64decode(secret, validate=True)) != 20:
            raise ValueError("invalid secret")
    except (ValueError, binascii.Error):
        raise MaFileError("invalid maFile shared secret") from None
    if entry is not None:
        if (
            account_id is not None
            and manifest_id is not None
            and _steam_id(manifest_id) != steam_id
        ):
            raise MaFileError("maFile and manifest SteamIDs do not match")
        expected_name = entry.get("account_name")
        if expected_name and (
            not isinstance(expected_name, str) or expected_name.casefold() != name.casefold()
        ):
            raise MaFileError("maFile and manifest account names do not match")
    return ImportedAuthenticator(name, LoginCredentials(shared_secret=secret, steam_id=steam_id))
