from __future__ import annotations

import base64
import importlib.util
import io
import json
import logging
import re
from pathlib import Path

import pytest
from rich.console import Console
from rich.panel import Panel

from pysteam import AuthTokens, LoginCredentials, LoginResult

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "test_mafile_login.py"
_SPEC = importlib.util.spec_from_file_location("test_mafile_login_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


@pytest.mark.asyncio
async def test_remembered_login_does_not_prompt_for_steam_password_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mafile = tmp_path / "user.maFile"
    mafile.write_text(
        json.dumps(
            {
                "account_name": "user",
                "steam_id": 42,
                "shared_secret": base64.b64encode(b"01234567890123456789").decode("ascii"),
            }
        ),
        encoding="utf-8",
    )
    store_path = tmp_path / "credentials.bin"
    monkeypatch.setattr(smoke, "_default_store_path", lambda _steam_id: store_path)
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return "password-to-save" if prompt.startswith("Steam password") else "test-passphrase"

    monkeypatch.setattr(smoke, "_ask_secret", answer)
    calls: list[LoginCredentials] = []

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def login_auto(self, account_name: str, *, credentials, store) -> LoginResult:
            assert account_name == "user"
            assert store is not None
            calls.append(credentials)
            if len(calls) == 1:
                await store.save(
                    account_name,
                    LoginCredentials(
                        password=credentials.password,
                        shared_secret=credentials.shared_secret,
                        refresh_token="sensitive-refresh-token",
                        steam_id=42,
                    ),
                )
            return LoginResult(
                "credentials" if len(calls) == 1 else "refresh_token",
                AuthTokens(42, "user", "sensitive-refresh-token", "sensitive-access-token"),
            )

    monkeypatch.setattr(smoke, "_DiagnosticSteamClient", FakeClient)
    await smoke._run(mafile, remember=True, store_path=None)
    await smoke._run(mafile, remember=True, store_path=None)
    assert sum(prompt.startswith("Steam password") for prompt in prompts) == 1
    assert calls[1].password == "password-to-save"
    assert calls[1].refresh_token == "sensitive-refresh-token"
    output = capsys.readouterr().out
    assert "Login succeeded" in output
    assert "password-to-save" not in output
    assert "sensitive-refresh-token" not in output
    assert "sensitive-access-token" not in output


def test_rich_debug_logging_has_millisecond_timestamps(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_output = io.BytesIO()
    output = io.TextIOWrapper(raw_output, encoding="cp1252", write_through=True)
    monkeypatch.setattr(
        smoke,
        "_CONSOLE",
        Console(file=output, width=160, color_system=None, legacy_windows=True),
    )
    logger = logging.getLogger("pysteam")
    previous_level, previous_propagate = logger.level, logger.propagate
    handler = smoke._enable_debug_logging()
    try:
        smoke._CONSOLE.print(Panel.fit("Steam Guard login check"))
        logger.debug("CM packet received")
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
    rendered = raw_output.getvalue().decode("cp1252")
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", rendered)
    assert "DEBUG" in rendered
    assert "pysteam.client           |" not in rendered
    assert "CM packet received" in rendered
    assert "| DEBUG | CM packet received" in rendered
    assert all(not line.endswith(" ") for line in rendered.splitlines())
