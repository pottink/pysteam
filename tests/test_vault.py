"""First-run vault, migration, and portable archive key rotation."""

from __future__ import annotations

from pathlib import Path

import pytest

import pysteam.cli as cli
from pysteam.accounts.credentials import EncryptedFileCredentialStore, LoginCredentials
from pysteam.accounts.profiles import ProfileRegistry, SavedProfile
from pysteam.accounts.vault import Vault, vault_passphrase
from pysteam.content.archive import ArchiveRegistry, ArchiveStore
from pysteam.errors import CredentialStoreError

PASSWORD = "new-vault-password"


def test_vault_round_trip_wrong_password_and_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = Vault.create(PASSWORD, tmp_path)
    assert Vault.open(PASSWORD, tmp_path).credential_passphrase == vault.credential_passphrase
    assert PASSWORD.encode() not in vault.path.read_bytes()
    with pytest.raises(CredentialStoreError, match="wrong vault password"):
        Vault.open("another-password", tmp_path)
    vault.change_password(PASSWORD, "rotated-vault-password")
    with pytest.raises(CredentialStoreError, match="wrong vault password"):
        Vault.open(PASSWORD, tmp_path)
    assert (
        Vault.open("rotated-vault-password", tmp_path).credential_passphrase
        == vault.credential_passphrase
    )
    monkeypatch.setenv("PYSTEAM_VAULT_PASSPHRASE", PASSWORD)
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "conflicting-password")
    with pytest.raises(CredentialStoreError, match="conflict"):
        vault_passphrase()


def test_cli_first_run_prompts_twice_and_unlocks_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path))
    monkeypatch.delenv("PYSTEAM_VAULT_PASSPHRASE", raising=False)
    monkeypatch.delenv("PYSTEAM_STORE_PASSPHRASE", raising=False)
    cli._ACTIVE_VAULT = None
    cli._ACTIVE_PASSWORD = None
    runner = CliRunner()
    result = runner.invoke(cli.main, ["init"], input=PASSWORD + "\n" + PASSWORD + "\n")
    assert result.exit_code == 0, result.output
    assert Vault.open(PASSWORD, tmp_path)
    cli._ACTIVE_VAULT = None
    cli._ACTIVE_PASSWORD = None
    wrong = runner.invoke(cli.main, ["init"], input="wrong-password\n")
    assert wrong.exit_code != 0
    assert "wrong vault password" in wrong.output


@pytest.mark.asyncio
async def test_migration_retry_keeps_old_registry_until_all_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path))
    monkeypatch.setenv("PYSTEAM_VAULT_PASSPHRASE", PASSWORD)
    registry = ProfileRegistry(tmp_path)
    for name, steam_id, secret in (("one", 41, "old-one"), ("two", 42, "old-two")):
        profile = SavedProfile(name, steam_id, registry.store_path(steam_id))
        registry.add(profile)
        await EncryptedFileCredentialStore(profile.store_path, secret).save(
            name, LoginCredentials(password=f"private-{name}", steam_id=steam_id)
        )
    old_registry = registry.path.read_bytes()
    old_stores = {item.steam_id: item.store_path.read_bytes() for item in registry.list()}
    answers = iter(("old-one", "wrong"))
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: next(answers))
    cli._ACTIVE_VAULT = None
    with pytest.raises(CredentialStoreError, match="wrong passphrase"):
        await cli._initialize_vault()
    assert registry.path.read_bytes() == old_registry
    assert all(
        item.store_path.read_bytes() == old_stores[item.steam_id] for item in registry.list()
    )

    answers = iter(("old-one", "old-two"))
    await cli._initialize_vault()
    assert all(item.store_path.parent.name == "accounts" for item in registry.list())
    assert all(
        (tmp_path / "profiles" / f"{item.steam_id}.bin").exists() for item in registry.list()
    )
    for item in registry.list():
        loaded = await EncryptedFileCredentialStore(
            item.store_path, Vault.open(PASSWORD, tmp_path).credential_passphrase
        ).load(item.account_name)
        assert loaded is not None and loaded.password == f"private-{item.account_name}"


def test_cli_password_change_rewraps_registered_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_VAULT_PASSPHRASE", PASSWORD)
    Vault.create(PASSWORD, tmp_path / "home")
    root = tmp_path / "archive"
    store = ArchiveStore(root, PASSWORD)
    store.save_key(123, bytes(range(32)))
    ArchiveRegistry(tmp_path / "home").add(root)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "rotated-vault-password")
    result = CliRunner().invoke(cli.main, ["vault", "change-password"])
    assert result.exit_code == 0, result.output
    with pytest.raises(CredentialStoreError):
        Vault.open(PASSWORD, tmp_path / "home")
    assert Vault.open("rotated-vault-password", tmp_path / "home")
    assert ArchiveStore(root, "rotated-vault-password").get_key(123) == bytes(range(32))
    with pytest.raises(CredentialStoreError):
        ArchiveStore(root, PASSWORD).get_key(123)


def test_rotation_failure_leaves_old_password_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("PYSTEAM_HOME", str(home))
    monkeypatch.setenv("PYSTEAM_VAULT_PASSPHRASE", PASSWORD)
    Vault.create(PASSWORD, home)
    good = tmp_path / "good"
    wrong = tmp_path / "wrong"
    ArchiveStore(good, PASSWORD).save_key(123, bytes(range(32)))
    ArchiveStore(wrong, "another-archive-password").save_key(124, bytes(range(32)))
    registry = ArchiveRegistry(home)
    registry.add(good)
    registry.add(wrong)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "rotated-vault-password")
    result = CliRunner().invoke(cli.main, ["vault", "change-password"])
    assert result.exit_code != 0
    assert Vault.open(PASSWORD, home)
    assert ArchiveStore(good, PASSWORD).get_key(123) == bytes(range(32))
