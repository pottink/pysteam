"""Caller-supplied credentials and an encrypted, replaceable storage backend."""

from __future__ import annotations

import asyncio
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import msgspec
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from pysteam.errors import CredentialStoreError

_MAGIC = b"PYSTEAM1"
_MAX_FILE_BYTES = 1024 * 1024
_SALT_BYTES = 16
_NONCE_BYTES = 12


@dataclass(frozen=True, slots=True)
class LoginCredentials:
    password: str | None = field(default=None, repr=False)
    shared_secret: str | None = field(default=None, repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    steam_id: int | None = None
    guard_data: str | None = field(default=None, repr=False)

    def with_fallback(self, fallback: LoginCredentials | None) -> LoginCredentials:
        if fallback is None:
            return self
        return LoginCredentials(
            password=self.password if self.password is not None else fallback.password,
            shared_secret=(
                self.shared_secret if self.shared_secret is not None else fallback.shared_secret
            ),
            refresh_token=(
                self.refresh_token if self.refresh_token is not None else fallback.refresh_token
            ),
            steam_id=self.steam_id if self.steam_id is not None else fallback.steam_id,
            guard_data=self.guard_data if self.guard_data is not None else fallback.guard_data,
        )


class CredentialStore(Protocol):
    async def load(self, account_name: str) -> LoginCredentials | None: ...

    async def save(self, account_name: str, credentials: LoginCredentials) -> None: ...

    async def delete(self, account_name: str) -> None: ...


class _Record(msgspec.Struct, forbid_unknown_fields=True):
    password: str | None = None
    shared_secret: str | None = None
    refresh_token: str | None = None
    steam_id: int | None = None
    guard_data: str | None = None


class EncryptedFileCredentialStore:
    """Multi-account AES-GCM file; the passphrase is never written to disk."""

    def __init__(self, path: str | Path, passphrase: str | bytes) -> None:
        if not passphrase:
            raise ValueError("credential store passphrase must not be empty")
        self.path = Path(path)
        self._passphrase = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase

    @staticmethod
    def _validate_account(account_name: str) -> None:
        if not account_name or len(account_name) > 256:
            raise ValueError("account name must be between 1 and 256 characters")

    def _key(self, salt: bytes) -> bytes:
        return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(self._passphrase)

    def _read_all(self) -> dict[str, _Record]:
        if os.name == "nt" and self.path.is_symlink():
            raise CredentialStoreError("credential store path must not be a symlink")
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags)
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise CredentialStoreError("credential store could not be read") from exc
        try:
            with os.fdopen(descriptor, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise CredentialStoreError("credential store path is not a regular file")
                if os.name != "nt" and info.st_mode & 0o077:
                    raise CredentialStoreError("credential store file permissions are too open")
                raw = source.read(_MAX_FILE_BYTES + 1)
        except OSError as exc:
            raise CredentialStoreError("credential store could not be read") from exc
        if len(raw) > _MAX_FILE_BYTES:
            raise CredentialStoreError("credential store exceeds size limit")
        prefix = len(_MAGIC) + _SALT_BYTES + _NONCE_BYTES
        if not raw.startswith(_MAGIC):
            raise CredentialStoreError("unsupported credential store format")
        if len(raw) < prefix + 16:
            raise CredentialStoreError("credential store is truncated")
        salt = raw[len(_MAGIC) : len(_MAGIC) + _SALT_BYTES]
        nonce = raw[len(_MAGIC) + _SALT_BYTES : prefix]
        try:
            plaintext = AESGCM(self._key(salt)).decrypt(nonce, raw[prefix:], _MAGIC + salt)
            records = msgspec.json.decode(plaintext, type=dict[str, _Record])
        except (InvalidTag, msgspec.DecodeError, msgspec.ValidationError):
            raise CredentialStoreError("wrong passphrase or corrupted credential store") from None
        if not isinstance(records, dict):
            raise CredentialStoreError("credential store has invalid contents")
        return records

    def _write_all(self, records: dict[str, _Record]) -> None:
        plaintext = msgspec.json.encode(records)
        salt = os.urandom(_SALT_BYTES)
        nonce = os.urandom(_NONCE_BYTES)
        raw = (
            _MAGIC + salt + nonce + AESGCM(self._key(salt)).encrypt(nonce, plaintext, _MAGIC + salt)
        )
        if len(raw) > _MAX_FILE_BYTES:
            raise CredentialStoreError("credential store exceeds size limit")
        try:
            self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-", dir=self.path.parent)
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
        except OSError as exc:
            raise CredentialStoreError("credential store could not be updated") from exc

    def _with_lock(
        self, operation: str, account_name: str, value: LoginCredentials | None = None
    ) -> LoginCredentials | None:
        self._validate_account(account_name)
        try:
            self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            with FileLock(str(self.path) + ".lock", timeout=10):
                records = self._read_all()
                if operation == "load":
                    item = records.get(account_name)
                    if item is None:
                        return None
                    return LoginCredentials(
                        item.password,
                        item.shared_secret,
                        item.refresh_token,
                        item.steam_id,
                        item.guard_data,
                    )
                if operation == "save":
                    assert value is not None
                    records[account_name] = _Record(
                        value.password,
                        value.shared_secret,
                        value.refresh_token,
                        value.steam_id,
                        value.guard_data,
                    )
                else:
                    records.pop(account_name, None)
                self._write_all(records)
        except FileLockTimeout as exc:
            raise CredentialStoreError("credential store is locked") from exc
        except OSError as exc:
            raise CredentialStoreError("credential store is unavailable") from exc
        return None

    async def load(self, account_name: str) -> LoginCredentials | None:
        return await asyncio.to_thread(self._with_lock, "load", account_name)

    async def save(self, account_name: str, credentials: LoginCredentials) -> None:
        await asyncio.to_thread(self._with_lock, "save", account_name, credentials)

    async def delete(self, account_name: str) -> None:
        await asyncio.to_thread(self._with_lock, "delete", account_name)
