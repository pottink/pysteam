"""CLI option validation stays local and never contacts Steam."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import typer
from typer.testing import CliRunner

from pysteam.cli import main as pysteam_command


def _load_command(name: str) -> typer.Typer:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_command_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.main, typer.Typer)
    return module.main


def test_typer_rejects_conflicting_login_options(tmp_path: Path) -> None:
    mafile = tmp_path / "test.maFile"
    mafile.write_text("{}", encoding="utf-8")
    result = CliRunner().invoke(
        _load_command("test_mafile_login"), [str(mafile), "--store", str(tmp_path / "store.bin")]
    )
    assert result.exit_code == 2
    assert "--store requires --remember" in result.output


def test_typer_rejects_conflicting_enrollment_options(tmp_path: Path) -> None:
    mafile = tmp_path / "test.maFile"
    mafile.write_text("{}", encoding="utf-8")
    result = CliRunner().invoke(
        _load_command("enroll_guard"),
        ["--output", str(tmp_path / "out"), "--resume", str(mafile)],
    )
    assert result.exit_code == 2
    assert "--output and --resume cannot be combined" in result.output


def test_typer_requires_one_live_smoke_mode() -> None:
    command = _load_command("smoke_live")
    for arguments in ([], ["--anonymous", "--auto-login"]):
        result = CliRunner().invoke(command, arguments)
        assert result.exit_code == 2
        assert "choose exactly one" in result.output


def test_inspect_app_rejects_invalid_app_id_without_network() -> None:
    result = CliRunner().invoke(_load_command("inspect_app"), ["0"])
    assert result.exit_code == 2
    assert "not in the range" in result.output


def test_installed_pysteam_group_exposes_app_subcommand() -> None:
    result = CliRunner().invoke(pysteam_command, ["app", "0"])
    assert result.exit_code == 2
    assert "not in the range" in result.output
    help_result = CliRunner().invoke(pysteam_command, ["--help"])
    assert help_result.exit_code == 0
    assert "app" in help_result.output
