"""Synthetic, offline compatibility cases for Steam Guard authenticator files."""

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pysteam import MaFileError, load_mafile

STEAM_ID = 76561197960265729
SECRET = base64.b64encode(b"01234567890123456789").decode("ascii")


def _account(name: str = "example", steam_id: int = STEAM_ID) -> dict[str, object]:
    return {
        "account_name": name,
        "steam_id": steam_id,
        "shared_secret": SECRET,
        "identity_secret": "identity-must-not-be-imported",
        "revocation_code": "recovery-must-not-be-imported",
        "tokens": {"refresh_token": "old-token-must-not-be-imported"},
    }


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _encrypt(plaintext: bytes, scheme: str, passphrase: str, salt: bytes, iv: bytes) -> bytes:
    if scheme == "Argon2idAes256":
        key = Argon2id(salt=salt, length=32, iterations=3, lanes=12, memory_cost=12 * 1024).derive(
            passphrase.encode()
        )
    else:
        key = PBKDF2HMAC(algorithm=hashes.SHA1(), length=32, salt=salt, iterations=50_000).derive(
            passphrase.encode()
        )
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize())


def test_plaintext_without_manifest_imports_only_login_details(tmp_path: Path) -> None:
    path = tmp_path / "account.maFile"
    _write(path, _account())
    original = path.read_bytes()
    imported = load_mafile(path)
    assert imported.account_name == "example"
    assert imported.credentials.steam_id == STEAM_ID
    assert imported.credentials.shared_secret == SECRET
    assert imported.credentials.password is None
    assert imported.credentials.refresh_token is None
    assert path.read_bytes() == original
    for forbidden in (SECRET, "identity-must", "recovery-must", "old-token"):
        assert forbidden not in repr(imported)
        assert forbidden not in repr(imported.credentials)


@pytest.mark.parametrize("scheme", ["Argon2idAes256", "LegacySdaCompatible"])
def test_versioned_manifest_encrypted_and_multiple_entries(tmp_path: Path, scheme: str) -> None:
    path = tmp_path / "target.maFile"
    salt = b"0123456789abcdef" if scheme == "Argon2idAes256" else b"12345678"
    iv = b"fedcba9876543210"
    plaintext = json.dumps(_account()).encode()
    ciphertext = _encrypt(plaintext, scheme, "correct-passphrase", salt, iv)
    path.write_bytes(ciphertext)
    _write(
        tmp_path / "manifest.json",
        {
            "version": 1,
            "entries": [
                {"filename": "unrelated.maFile", "steam_id": 42, "account_name": "other"},
                {
                    "filename": path.name,
                    "steam_id": STEAM_ID,
                    "account_name": "example",
                    "encryption": {
                        "scheme": scheme,
                        "salt": base64.b64encode(salt).decode(),
                        "iv": base64.b64encode(iv).decode(),
                    },
                },
            ],
        },
    )
    assert load_mafile(path, passphrase="correct-passphrase").credentials.shared_secret == SECRET
    assert path.read_bytes() == ciphertext
    with pytest.raises(MaFileError, match="passphrase is required"):
        load_mafile(path)
    with pytest.raises(MaFileError, match="incorrect passphrase or corrupt") as caught:
        load_mafile(path, passphrase="wrong-passphrase")
    assert "wrong-passphrase" not in str(caught.value)
    path.write_bytes(ciphertext[:-4] + b"!!!!")
    with pytest.raises(MaFileError, match="incorrect passphrase or corrupt"):
        load_mafile(path, passphrase="correct-passphrase")


def test_legacy_sda_manifest_encryption(tmp_path: Path) -> None:
    path = tmp_path / "target.maFile"
    salt, iv = b"12345678", b"fedcba9876543210"
    account = _account()
    del account["steam_id"]  # Original SDA files keep the SteamID in manifest.json.
    path.write_bytes(_encrypt(json.dumps(account).encode(), "LegacySdaCompatible", "pw", salt, iv))
    _write(
        tmp_path / "manifest.json",
        {
            "encrypted": True,
            "entries": [
                {
                    "filename": path.name,
                    "steamid": STEAM_ID,
                    "encryption_salt": base64.b64encode(salt).decode(),
                    "encryption_iv": base64.b64encode(iv).decode(),
                }
            ],
        },
    )
    imported = load_mafile(path, passphrase="pw")
    assert imported.account_name == "example"
    assert imported.credentials.steam_id == STEAM_ID


def test_argon2id_matches_upstream_key_vector(tmp_path: Path) -> None:
    # From steamguard-cli src/encryption/argon2id_aes.rs at b6c439c9.
    salt = base64.b64decode("GMhL0N2hqXg=")
    key = base64.b64decode("DTm3hc95aKyAGmyVMZdLUPfcPjcXN1i1zYObYJg2GzY=")
    iv = b"fedcba9876543210"
    padder = padding.PKCS7(128).padder()
    plaintext = json.dumps(_account()).encode()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    path = tmp_path / "target.maFile"
    path.write_bytes(base64.b64encode(encryptor.update(padded) + encryptor.finalize()))
    _write(
        tmp_path / "manifest.json",
        {
            "version": 1,
            "entries": [
                {
                    "filename": path.name,
                    "steam_id": STEAM_ID,
                    "account_name": "example",
                    "encryption": {
                        "scheme": "Argon2idAes256",
                        "salt": base64.b64encode(salt).decode(),
                        "iv": base64.b64encode(iv).decode(),
                    },
                }
            ],
        },
    )
    assert load_mafile(path, passphrase="password").credentials.shared_secret == SECRET


def test_manifest_supplies_missing_account_name_and_string_id(tmp_path: Path) -> None:
    path = tmp_path / "target.maFile"
    account = _account()
    del account["account_name"]
    account["steam_id"] = str(STEAM_ID)
    _write(path, account)
    _write(
        tmp_path / "manifest.json",
        {
            "version": 1,
            "entries": [{"filename": path.name, "steam_id": STEAM_ID, "account_name": "example"}],
        },
    )
    assert load_mafile(path).account_name == "example"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_name", "\ninvalid"),
        ("steam_id", 0),
        ("steam_id", "not-a-steamid"),
        ("shared_secret", "not-base64"),
        ("shared_secret", base64.b64encode(b"short").decode()),
    ],
)
def test_invalid_account_fields(tmp_path: Path, field: str, value: object) -> None:
    account = _account()
    account[field] = value
    path = tmp_path / "bad.maFile"
    _write(path, account)
    with pytest.raises(MaFileError) as caught:
        load_mafile(path)
    assert str(value) not in str(caught.value)


def test_manifest_mismatch_and_unsupported_scheme(tmp_path: Path) -> None:
    path = tmp_path / "target.maFile"
    _write(path, _account())
    manifest = {
        "version": 1,
        "entries": [{"filename": path.name, "steam_id": STEAM_ID + 1, "account_name": "example"}],
    }
    _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(MaFileError, match="SteamIDs do not match"):
        load_mafile(path)
    manifest["entries"][0]["steam_id"] = STEAM_ID  # type: ignore[index]
    manifest["entries"][0]["account_name"] = "someone-else"  # type: ignore[index]
    _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(MaFileError, match="account names do not match"):
        load_mafile(path)
    manifest["entries"][0]["account_name"] = "example"  # type: ignore[index]
    manifest["entries"][0]["encryption"] = {"scheme": "unknown"}  # type: ignore[index]
    _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(MaFileError, match="unsupported maFile encryption scheme"):
        load_mafile(path)
    manifest["version"] = 2
    _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(MaFileError, match="unsupported maFile manifest version"):
        load_mafile(path)


def test_corrupt_oversized_and_missing_manifest(tmp_path: Path) -> None:
    path = tmp_path / "bad.maFile"
    path.write_bytes(b"not-json-encrypted-looking")
    with pytest.raises(MaFileError, match="adjacent manifest"):
        load_mafile(path, passphrase="pw")
    path.write_bytes(b"{" + b"x" * (1024 * 1024))
    with pytest.raises(MaFileError, match="size limit"):
        load_mafile(path)
    path.write_bytes(b"{invalid")
    with pytest.raises(MaFileError, match="invalid maFile or manifest JSON"):
        load_mafile(path)
    _write(path, _account())
    (tmp_path / "manifest.json").write_bytes(b"{" + b"x" * (1024 * 1024))
    with pytest.raises(MaFileError, match="size limit"):
        load_mafile(path)
