"""App inspection output is readable and JSON mode is machine-readable."""

from __future__ import annotations

import json

import pytest

import pysteam.cli as inspect


@pytest.mark.asyncio
async def test_app_inspection_summary_and_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app_info = {
        "appid": "220",
        "common": {"name": "[bold red]Half-Life 2[/]", "type": "Game"},
        "depots": {"221": {"manifests": {"public": {"gid": "123456789"}}}},
    }

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def login_anonymous(self) -> None:
            pass

        async def get_app_info(self, app_id: int) -> dict[str, object]:
            assert app_id == 220
            return app_info

    monkeypatch.setattr(inspect, "SteamClient", FakeClient)
    await inspect._inspect_app(220, as_json=False)
    summary = capsys.readouterr().out
    assert "[bold red]Half-Life 2[/]" in summary
    assert "123456789" in summary

    await inspect._inspect_app(220, as_json=True)
    assert json.loads(capsys.readouterr().out) == app_info
