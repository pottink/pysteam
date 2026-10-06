"""Project-local master vault for account and archive encryption keys."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from pysteam.accounts.profiles import default_profile_dir, ensure_private_directory
from pysteam.errors import CredentialStoreError

_MAGIC = b"PYSTEAM-VAULT-1\0"
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KEY_SIZE = 32
_MAX_SIZE = 256


def vault_passphrase(explicit: str | None = None) -> str | None:
    """Resolve the new name and its legacy alias without ambiguous precedence."""
    current = os.environ.get("PYSTEAM_VAULT_PASSPHRASE")
    legacy = os.environ.get("PYSTEAM_STORE_PASSPHRASE")
    if current is not None and legacy is not None and current != legacy:
        raise CredentialStoreError("vault passphrase environment variables conflict")
    return explicit if explicit is not None else current if current is not None else legacy


def _wrapping_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=_KEY_SIZE, n=2**17, r=8, p=1).derive(passphrase.encode("utf-8"))


def _write_private(path: Path, data: bytes) -> None:
    ensure_private_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-vault-", dir=path.parent)
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


@dataclass(frozen=True, slots=True, repr=False)
class Vault:
    directory: Path
    _key: bytes = field(repr=False)

    @property
    def path(self) -> Path:
        return self.directory / "vault.bin"

    @property
    def credential_passphrase(self) -> bytes:
        """A separate secret for existing encrypted credential-store files."""
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"pysteam-account-stores-v1",
        ).derive(self._key)

    @classmethod
    def exists(cls, directory: str | Path | None = None) -> bool:
        root = Path(directory) if directory is not None else default_profile_dir()
        return (root / "vault.bin").is_file()

    @classmethod
    def create(cls, passphrase: str, directory: str | Path | None = None) -> Vault:
        if len(passphrase) < 12:
            raise CredentialStoreError("new vault password must have at least 12 characters")
        root = Path(directory) if directory is not None else default_profile_dir()
        ensure_private_directory(root)
        path = root / "vault.bin"
        try:
            with FileLock(str(path) + ".lock", timeout=10):
                if path.exists():
                    raise CredentialStoreError("vault already exists")
                key = os.urandom(_KEY_SIZE)
                cls._save(path, key, passphrase)
                return cls(root, key)
        except FileLockTimeout:
            raise CredentialStoreError("vault is locked") from None

    @classmethod
    def open(cls, passphrase: str, directory: str | Path | None = None) -> Vault:
        root = Path(directory) if directory is not None else default_profile_dir()
        path = root / "vault.bin"
        if path.is_symlink():
            raise CredentialStoreError("vault path must not be a symlink")
        try:
            with path.open("rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise CredentialStoreError("vault path is not a regular file")
                if os.name != "nt" and info.st_mode & 0o077:
                    raise CredentialStoreError("vault permissions are too open")
                raw = source.read(_MAX_SIZE + 1)
        except FileNotFoundError:
            raise CredentialStoreError("vault is not initialized; run 'pysteam init'") from None
        except OSError:
            raise CredentialStoreError("vault could not be read") from None
        prefix = len(_MAGIC) + _SALT_SIZE + _NONCE_SIZE
        if len(raw) > _MAX_SIZE or len(raw) < prefix + 16 or not raw.startswith(_MAGIC):
            raise CredentialStoreError("vault format is invalid or unsupported")
        salt = raw[len(_MAGIC) : len(_MAGIC) + _SALT_SIZE]
        nonce = raw[len(_MAGIC) + _SALT_SIZE : prefix]
        try:
            key = AESGCM(_wrapping_key(passphrase, salt)).decrypt(
                nonce, raw[prefix:], _MAGIC + salt
            )
        except InvalidTag:
            raise CredentialStoreError("wrong vault password or corrupt vault") from None
        if len(key) != _KEY_SIZE:
            raise CredentialStoreError("vault contains an invalid key")
        return cls(root, key)

    @staticmethod
    def _save(path: Path, key: bytes, passphrase: str) -> None:
        salt, nonce = os.urandom(_SALT_SIZE), os.urandom(_NONCE_SIZE)
        raw = (
            _MAGIC
            + salt
            + nonce
            + AESGCM(_wrapping_key(passphrase, salt)).encrypt(nonce, key, _MAGIC + salt)
        )
        _write_private(path, raw)

    def change_password(self, old: str, new: str) -> None:
        if len(new) < 12:
            raise CredentialStoreError("new vault password must have at least 12 characters")
        try:
            with FileLock(str(self.path) + ".lock", timeout=10):
                if Vault.open(old, self.directory)._key != self._key:
                    raise CredentialStoreError("vault changed while it was unlocked")
                self._save(self.path, self._key, new)
        except FileLockTimeout:
            raise CredentialStoreError("vault is locked") from None
