"""CLI workflows keep secrets out of output and protect depot destinations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import pysteam.cli as cli
from pysteam.auth import AuthTokens, LoginResult
from pysteam.cdn import DepotFile, DepotManifest
from pysteam.credentials import LoginCredentials
from pysteam.errors import MaFileError, ProtocolError, SteamResultError
from pysteam.mafile import ImportedAuthenticator


def test_steamid_parse_and_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["steamid", "parse", "STEAM_0:1:4"])
    assert result.exit_code == 0
    assert "76561197960265737" in result.output
    assert "Account ID" in result.output
    assert runner.invoke(cli.main, ["depot", "download", "--help"]).exit_code == 0
    assert "--file" in runner.invoke(cli.main, ["depot", "download", "--help"]).output


def test_guard_code_import_never_displays_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mafile = tmp_path / "account.maFile"
    mafile.write_bytes(b"fixture")
    secret = "c2Vuc2l0aXZlLXNoYXJlZC1zZWNyZXQ="
    imported = ImportedAuthenticator("account", LoginCredentials(shared_secret=secret, steam_id=42))
    monkeypatch.setattr(cli, "load_mafile", lambda _path: imported)
    result = CliRunner().invoke(cli.main, ["guard", "code", "--mafile", str(mafile)])
    assert result.exit_code == 0
    assert secret not in result.output
    assert "Expires in" in result.output


def test_login_reuses_saved_token_without_password_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def prompt(label: str, *, confirmation: bool = False) -> str:
        prompts.append(label)
        return "store-passphrase"

    class Store:
        def __init__(self, _path: Path, _passphrase: str) -> None:
            pass

        async def load(self, account: str) -> LoginCredentials:
            assert account == "account"
            return LoginCredentials(refresh_token="private-token", steam_id=42)

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def login_auto(self, account: str, *, credentials, store, on_challenge):
            assert credentials.refresh_token == "private-token"
            assert store is not None
            assert on_challenge is not None
            return LoginResult("refresh_token", AuthTokens(42, account, "private-token", "access"))

    monkeypatch.setattr(cli, "_prompt_secret", prompt)
    monkeypatch.setattr(cli, "EncryptedFileCredentialStore", Store)
    monkeypatch.setattr(cli, "SteamClient", Client)
    result = CliRunner().invoke(cli.main, ["login", "account", "--store", "saved.bin"])
    assert result.exit_code == 0, result.output
    assert prompts == ["Credential store passphrase"]
    assert "Login succeeded" in result.output
    assert "private-token" not in result.output
    assert "store-passphrase" not in result.output


@pytest.mark.asyncio
async def test_mafile_reuses_default_store_without_steam_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    saved = tmp_path / "saved.bin"
    saved.write_bytes(b"fixture")
    prompts: list[str] = []
    imported = ImportedAuthenticator(
        "account", LoginCredentials(shared_secret="secret", steam_id=42)
    )

    def load(_path: Path, *, passphrase: str | None = None) -> ImportedAuthenticator:
        if passphrase is None:
            raise MaFileError("a passphrase is required for this encrypted maFile")
        assert passphrase == "backup-passphrase"
        return imported

    def prompt(label: str, *, confirmation: bool = False) -> str:
        prompts.append(label)
        return "backup-passphrase"

    class Store:
        def __init__(self, path: Path, passphrase: str) -> None:
            assert path == saved
            assert passphrase == "backup-passphrase"

        async def load(self, _account: str) -> LoginCredentials:
            return LoginCredentials(refresh_token="saved-token", steam_id=42)

    class Client:
        async def login_auto(self, account: str, *, credentials, store, on_challenge):
            assert account == "account"
            assert credentials.refresh_token == "saved-token"
            assert credentials.shared_secret == "secret"
            return LoginResult("refresh_token", AuthTokens(42, account, "saved-token", "access"))

    monkeypatch.setattr(cli, "load_mafile", load)
    monkeypatch.setattr(cli, "_prompt_secret", prompt)
    monkeypatch.setattr(cli, "_default_store_path", lambda _steam_id: saved)
    monkeypatch.setattr(cli, "EncryptedFileCredentialStore", Store)
    result = await cli._authenticate(  # type: ignore[arg-type]
        Client(), account=None, mafile=tmp_path / "account.maFile", store_path=None, remember=False
    )
    assert result is not None and result.method == "refresh_token"
    assert prompts == ["maFile backup passphrase"]


@pytest.mark.asyncio
async def test_depot_manifest_auth_retry_and_download_safety(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "accounts"))
    file = DepotFile("folder/file.txt", 3, b"", 0, ())
    manifest = DepotManifest(221, 123, False, (file,), b"")
    calls: list[tuple[str, str]] = []

    class CDN:
        async def get_depot_key(self, app_id: int, depot_id: int) -> bytes:
            assert (app_id, depot_id) == (220, 221)
            return b"k" * 32

        async def servers(self) -> tuple[str, ...]:
            return ("https://cdn.test",)

        async def get_manifest(self, **kwargs: object) -> DepotManifest:
            calls.append(("manifest", str(kwargs["auth_token"]) if "auth_token" in kwargs else ""))
            if not kwargs.get("auth_token"):
                from pysteam.errors import CDNHTTPError

                raise CDNHTTPError(403)
            return manifest

        async def get_auth_token(self, app_id: int, depot_id: int, host: str) -> str:
            assert (app_id, depot_id, host) == (220, 221, "cdn.test")
            return "secret-cdn-token"

        async def download_file(self, *, destination: Path, **kwargs: object) -> None:
            assert kwargs["auth_token"] == "secret-cdn-token"
            calls.append(("download", str(destination)))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"abc")

    class Client:
        cdn = CDN()

        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def login_anonymous(self) -> None:
            pass

        async def get_app_manifest_ids(self, app_id: int, *, branch: str) -> dict[int, int]:
            assert (app_id, branch) == (220, "public")
            return {221: 123}

    monkeypatch.setattr(cli, "SteamClient", Client)
    await cli._depot_list(220, 221, None, "public", None, None, None, True)
    listed = json.loads(capsys.readouterr().out)
    assert listed["files"] == [{"name": "folder/file.txt", "size": 3, "flags": 0}]
    await cli._depot_download(
        220, 221, None, "public", None, None, None, ("folder/file.txt",), tmp_path, False
    )
    assert (tmp_path / "folder" / "file.txt").read_bytes() == b"abc"
    assert "secret-cdn-token" not in capsys.readouterr().out
    with pytest.raises(Exception, match="destination exists"):
        await cli._depot_download(
            220, 221, None, "public", None, None, None, ("folder/file.txt",), tmp_path, False
        )
    assert (tmp_path / "folder" / "file.txt").read_bytes() == b"abc"
    assert calls.count(("manifest", "secret-cdn-token")) == 3


@pytest.mark.asyncio
async def test_depot_key_denial_explains_account_access() -> None:
    class CDN:
        async def get_depot_key(self, _app_id: int, _depot_id: int) -> bytes:
            raise SteamResultError("get depot key", 15)

    class Client:
        cdn = CDN()

        async def get_app_manifest_ids(self, _app_id: int, *, branch: str) -> dict[int, int]:
            return {221: 123}

    with pytest.raises(Exception, match="owns this depot"):
        await cli._manifest(Client(), 220, 221, None, "public")  # type: ignore[arg-type]


def test_doctor_reports_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def login_anonymous(self) -> None:
            pass

        async def get_app_info(self, app_id: int) -> dict[str, object]:
            assert app_id == 220
            return {"common": {"name": "Half-Life 2"}}

    monkeypatch.setattr(cli, "SteamClient", Client)
    result = CliRunner().invoke(cli.main, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "CM discovery" in result.output
    assert "Anonymous CM logon" in result.output
    assert "Half-Life 2" in result.output


def test_depot_download_rejects_unsafe_destinations(tmp_path: Path) -> None:
    with pytest.raises(ProtocolError, match="escapes"):
        cli._destination(tmp_path, DepotFile("../outside.txt", 1, b"", 0, ()))
    with pytest.raises(ProtocolError, match="symlink"):
        cli._destination(tmp_path, DepotFile("link.txt", 1, b"", 512, ()))


@pytest.mark.asyncio
async def test_whole_depot_download_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = (
        DepotFile("keep/readme.txt", 1, b"", 0, ()),
        DepotFile("skip/hidden.txt", 1, b"", 0, ()),
        DepotFile("keep/image.png", 1, b"", 0, ()),
    )
    manifest = DepotManifest(221, 123, False, files, b"")
    downloaded: list[str] = []

    class CDN:
        async def download_file(
            self, *, file: DepotFile, destination: Path, **_kwargs: object
        ) -> None:
            downloaded.append(file.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"x")

    class Client:
        cdn = CDN()

        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

    async def fake_auth(*_args: object, **_kwargs: object) -> None:
        pass

    async def fake_manifest(
        *_args: object, **_kwargs: object
    ) -> tuple[DepotManifest, bytes, str, str]:
        return manifest, b"k" * 32, "https://cdn.invalid", ""

    monkeypatch.setattr(cli, "SteamClient", Client)
    monkeypatch.setattr(cli, "_authenticate", fake_auth)
    monkeypatch.setattr(cli, "_manifest", fake_manifest)
    await cli._depot_download(
        220,
        221,
        None,
        "public",
        None,
        None,
        None,
        (),
        tmp_path,
        False,
        all_files=True,
        includes=("*.txt",),
        excludes=("skip/*",),
        max_downloads=2,
    )
    assert downloaded == ["keep/readme.txt"]
