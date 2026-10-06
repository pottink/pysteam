"""Saved account profiles and CLI setup never expose or mix credentials."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

import pysteam.cli as cli
from pysteam import (
    AuthTokens,
    EncryptedFileCredentialStore,
    LoginCredentials,
    LoginResult,
    ProfileError,
    ProfileRegistry,
    SavedProfile,
    SteamClient,
)


def _mafile(path: Path, name: str, steam_id: int) -> None:
    path.write_text(
        json.dumps(
            {
                "account_name": name,
                "steam_id": steam_id,
                "shared_secret": base64.b64encode(b"01234567890123456789").decode(),
            }
        ),
        encoding="utf-8",
    )


def test_registry_keeps_multiple_accounts_and_rejects_corruption(tmp_path: Path) -> None:
    registry = ProfileRegistry(tmp_path)
    first = SavedProfile("First", 41, registry.store_path(41), tmp_path / "first.maFile")
    second = SavedProfile("Second", 42, registry.store_path(42))
    registry.add(first)
    registry.add(second)
    assert registry.default() == first
    assert registry.get("second") == second
    assert registry.use("SECOND") == second
    assert ProfileRegistry(tmp_path).default() == second
    with pytest.raises(ProfileError, match="already exists"):
        registry.add(SavedProfile("first", 43, registry.store_path(43)))
    with pytest.raises(ProfileError, match="already exists"):
        registry.add(SavedProfile("Third", 42, registry.store_path(42)))
    raw = registry.path.read_text(encoding="utf-8")
    assert "password" not in raw and "shared_secret" not in raw
    assert "profiles/42.bin" in raw
    if os.name != "nt":
        assert registry.path.stat().st_mode & 0o077 == 0
    registry.path.write_text('{"version":2}', encoding="utf-8")
    with pytest.raises(ProfileError, match="corrupt or unsupported"):
        registry.list()
    registry.path.write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(ProfileError, match="size limit"):
        registry.list()


def test_registry_remove_updates_default_and_preserves_mafile(tmp_path: Path) -> None:
    registry = ProfileRegistry(tmp_path)
    mafile = tmp_path / "first.maFile"
    mafile.write_text("backup", encoding="utf-8")
    first = SavedProfile("First", 41, registry.store_path(41), mafile)
    second = SavedProfile("Second", 42, registry.store_path(42))
    registry.add(first)
    registry.add(second)
    first.store_path.parent.mkdir(parents=True, exist_ok=True)
    first.store_path.write_bytes(b"encrypted store")
    assert registry.remove("FIRST") == first
    assert not first.store_path.exists()
    assert mafile.read_text(encoding="utf-8") == "backup"
    assert registry.default() == second
    assert registry.remove("second") == second
    assert registry.default() is None
    with pytest.raises(ProfileError, match="not found"):
        registry.remove("second")


def test_registry_remove_rejects_a_non_file_store(tmp_path: Path) -> None:
    registry = ProfileRegistry(tmp_path)
    profile = SavedProfile("First", 41, registry.store_path(41))
    registry.add(profile)
    profile.store_path.mkdir(parents=True)
    with pytest.raises(ProfileError, match="not a regular file"):
        registry.remove("First")
    assert registry.default() == profile
    assert profile.store_path.is_dir()


@pytest.mark.asyncio
async def test_sdk_login_saved_selects_account_and_checks_passphrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ProfileRegistry(tmp_path)
    for name, steam_id in (("one", 41), ("two", 42)):
        profile = SavedProfile(name, steam_id, registry.store_path(steam_id))
        registry.add(profile)
        await EncryptedFileCredentialStore(profile.store_path, "store-key").save(
            name,
            LoginCredentials(
                password=f"password-{name}", refresh_token=f"token-{name}", steam_id=steam_id
            ),
        )
    registry.use("two")
    calls: list[str] = []

    async def fake_login_auto(self: SteamClient, name: str, **kwargs: object) -> LoginResult:
        credentials = kwargs["credentials"]
        assert isinstance(credentials, LoginCredentials)
        assert credentials.refresh_token == f"token-{name}"
        calls.append(name)
        return LoginResult(
            "refresh_token", AuthTokens(credentials.steam_id or 0, name, "renewed", "access")
        )

    monkeypatch.setattr(SteamClient, "login_auto", fake_login_auto)
    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"])
    try:
        with pytest.raises(ProfileError, match="PYSTEAM_VAULT_PASSPHRASE"):
            await client.login_saved(profile_dir=tmp_path)
        monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "store-key")
        assert (await client.login_saved(profile_dir=tmp_path)).tokens.steam_id == 42
        assert (await client.login_saved("one", profile_dir=tmp_path)).tokens.steam_id == 41
        assert calls == ["two", "one"]
        with pytest.raises(Exception, match="wrong passphrase"):
            await client.login_saved("two", profile_dir=tmp_path, passphrase="wrong")
    finally:
        await client.aclose()


class _Client:
    def __init__(self, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_args: object) -> None:
        pass

    async def login_auto(
        self, name: str, *, credentials: LoginCredentials, **_kwargs: object
    ) -> LoginResult:
        steam_id = credentials.steam_id or (41 if name == "one" else 42)
        return LoginResult("credentials", AuthTokens(steam_id, name, "private-token", "access"))


def test_cli_register_existing_mafile_and_second_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-123")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "private-password")
    mafile = tmp_path / "one.maFile"
    _mafile(mafile, "one", 41)
    runner = CliRunner()
    first = runner.invoke(cli.main, ["account", "add", "one", "--mafile", str(mafile)])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli.main, ["account", "add", "two"])
    assert second.exit_code == 0, second.output
    registry = ProfileRegistry()
    assert registry.default() is not None and registry.default().account_name == "one"
    assert registry.get("two") is not None
    assert runner.invoke(cli.main, ["account", "use", "two"]).exit_code == 0
    assert registry.default() is not None and registry.default().account_name == "two"
    default_login = runner.invoke(cli.main, ["login"])
    assert default_login.exit_code == 0, default_login.output
    assert "Login succeeded" in default_login.output
    shown = runner.invoke(cli.main, ["account", "show", "one"])
    assert shown.exit_code == 0
    assert "maFile backup:" in shown.output and "one.maFile" in shown.output
    assert "private-password" not in shown.output
    listed = runner.invoke(cli.main, ["account", "list"])
    assert listed.exit_code == 0 and "one" in listed.output and "two" in listed.output
    stored = asyncio.run(
        EncryptedFileCredentialStore(
            registry.select("one").store_path,
            cli.Vault.open("vault-password-123", registry.directory).credential_passphrase,
        ).load("one")
    )
    assert stored is not None and stored.password == "private-password"
    assert stored.shared_secret is not None and stored.refresh_token == "private-token"
    assert b"private-password" not in registry.select("one").store_path.read_bytes()
    code = runner.invoke(cli.main, ["guard", "code", "--account", "one"])
    assert code.exit_code == 0, code.output
    assert "private-password" not in code.output


def test_cli_remove_allows_account_reregistration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-old")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "private-password")
    mafile = tmp_path / "one.maFile"
    _mafile(mafile, "one", 41)
    runner = CliRunner()
    first = runner.invoke(cli.main, ["account", "add", "one", "--mafile", str(mafile)])
    assert first.exit_code == 0, first.output
    assert runner.invoke(cli.main, ["account", "add", "two"]).exit_code == 0
    registry = ProfileRegistry()
    store_path = registry.select("one").store_path

    cancelled = runner.invoke(cli.main, ["account", "remove", "one"], input="n\n")
    assert cancelled.exit_code == 0
    assert "cancelled" in cancelled.output
    assert store_path.is_file() and registry.get("one") is not None

    removed = runner.invoke(cli.main, ["account", "remove", "ONE", "--yes"])
    assert removed.exit_code == 0, removed.output
    assert str(mafile) in removed.output and "to keep" in removed.output
    assert not store_path.exists() and mafile.is_file()
    assert registry.default() is not None and registry.default().account_name == "two"

    added = runner.invoke(cli.main, ["account", "add", "one", "--mafile", str(mafile)])
    assert added.exit_code == 0, added.output
    assert registry.default() is not None and registry.default().account_name == "two"
    key = cli.Vault.open("vault-password-old", registry.directory).credential_passphrase
    saved = asyncio.run(EncryptedFileCredentialStore(store_path, key).load("one"))
    assert saved is not None and saved.password == "private-password"
    with pytest.raises(Exception, match="wrong passphrase"):
        asyncio.run(EncryptedFileCredentialStore(store_path, "wrong-password").load("one"))


def test_registration_migrates_legacy_store_without_changing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "new-vault-password")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    prompts: list[str] = []

    def prompt(label: str, **_kwargs: object) -> str:
        prompts.append(label)
        return "old-key"

    monkeypatch.setattr(cli, "_prompt_secret", prompt)
    mafile = tmp_path / "one.maFile"
    _mafile(mafile, "one", 41)
    old_path = cli._default_store_path(41)
    asyncio.run(
        EncryptedFileCredentialStore(old_path, "old-key").save(
            "one", LoginCredentials(password="old-password", refresh_token="old-token", steam_id=41)
        )
    )
    old_content = old_path.read_bytes()
    result = CliRunner().invoke(cli.main, ["account", "add", "one", "--mafile", str(mafile)])
    assert result.exit_code == 0, result.output
    assert prompts == ["Existing credential store passphrase"]
    assert old_path.read_bytes() == old_content
    profile = ProfileRegistry().select("one")
    key = cli.Vault.open("new-vault-password", cli.default_profile_dir()).credential_passphrase
    saved = asyncio.run(EncryptedFileCredentialStore(profile.store_path, key).load("one"))
    assert saved is not None and saved.password == "old-password"
    assert saved.shared_secret is not None and saved.refresh_token == "private-token"


def test_registration_rejects_mafile_account_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    mafile = tmp_path / "one.maFile"
    _mafile(mafile, "one", 41)
    result = CliRunner().invoke(cli.main, ["account", "add", "two", "--mafile", str(mafile)])
    assert result.exit_code != 0
    assert "does not match" in result.output
    assert ProfileRegistry().list() == ()


@pytest.mark.asyncio
async def test_default_profile_auth_and_explicit_anonymous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-123")
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "store-key")
    registry = ProfileRegistry()
    registry.add(SavedProfile("one", 41, registry.store_path(41)))
    await EncryptedFileCredentialStore(registry.store_path(41), "store-key").save(
        "one", LoginCredentials(password="password", steam_id=41)
    )
    calls: list[str] = []

    class Fake:
        async def login_anonymous(self) -> None:
            calls.append("anonymous")

        async def login_auto(self, name: str, **_kwargs: object) -> LoginResult:
            calls.append(name)
            return LoginResult("credentials", AuthTokens(41, name, "refresh", "access"))

    fake = Fake()
    await cli._authenticate(fake, account=None, mafile=None, store_path=None, remember=False)  # type: ignore[arg-type]
    await cli._authenticate(  # type: ignore[arg-type]
        fake, account=None, mafile=None, store_path=None, remember=False, anonymous=True
    )
    assert calls == ["one", "anonymous"]


def test_cli_enrollment_registers_only_after_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-123")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "private-password")
    monkeypatch.setattr(cli, "_pause", lambda _message: None)
    path = tmp_path / "new.maFile"
    events: list[str] = []

    class Pending:
        mafile_path = path
        recovery_code = "RTEST"
        confirmation_type = 3

        async def finalize(self, _code: str) -> Path:
            events.append("activate")
            _mafile(path, "one", 41)
            return path

    class Enrollment:
        def __init__(self, _client: object) -> None:
            pass

        async def login_and_begin(self, name: str, password: str, **_kwargs: object) -> Pending:
            assert name == "one" and password == "private-password"
            events.append("begin")
            return Pending()

    monkeypatch.setattr(cli, "GuardEnrollmentClient", Enrollment)
    result = CliRunner().invoke(cli.main, ["account", "add", "one", "--enroll"])
    assert result.exit_code == 0, result.output
    assert events == ["begin", "activate"]
    assert ProfileRegistry().select("one").mafile_path == path.resolve()
    assert "RTEST" in result.output


def test_incomplete_enrollment_keeps_backup_and_no_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pysteam import EnrollmentError

    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-123")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "private-password")
    monkeypatch.setattr(cli, "_pause", lambda _message: None)
    path = tmp_path / "pending.maFile"

    class Pending:
        mafile_path = path
        recovery_code = "RTEST"
        confirmation_type = 3

        async def finalize(self, _code: str) -> Path:
            raise EnrollmentError("activation failed")

    class Enrollment:
        def __init__(self, _client: object) -> None:
            pass

        async def login_and_begin(self, name: str, _password: str, **_kwargs: object) -> Pending:
            _mafile(path, name, 41)
            return Pending()

    monkeypatch.setattr(cli, "GuardEnrollmentClient", Enrollment)
    result = CliRunner().invoke(cli.main, ["account", "add", "one", "--enroll"])
    assert result.exit_code != 0
    assert "--resume-enrollment" in result.output
    assert path.is_file()
    assert ProfileRegistry().list() == ()


def test_cli_resumes_enrollment_from_existing_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYSTEAM_STORE_PASSPHRASE", "vault-password-123")
    monkeypatch.setattr(cli, "SteamClient", _Client)
    monkeypatch.setattr(cli, "_prompt_secret", lambda _label, **_kwargs: "private-password")
    path = tmp_path / "pending.maFile"
    _mafile(path, "one", 41)
    calls: list[str] = []

    class Pending:
        mafile_path = path
        recovery_code = None
        confirmation_type = 0

        async def finalize(self, _code: str) -> Path:
            calls.append("finalize")
            return path

    class Enrollment:
        def __init__(self, _client: object) -> None:
            pass

        async def login_and_resume(
            self, name: str, password: str, *, mafile_path: Path, **_kwargs: object
        ) -> Pending:
            assert name == "one" and password == "private-password"
            assert mafile_path == path
            calls.append("resume")
            return Pending()

    monkeypatch.setattr(cli, "GuardEnrollmentClient", Enrollment)
    result = CliRunner().invoke(
        cli.main, ["account", "add", "one", "--enroll", "--resume-enrollment", str(path)]
    )
    assert result.exit_code == 0, result.output
    assert calls == ["resume", "finalize"]
    assert ProfileRegistry().select("one").mafile_path == path.resolve()
