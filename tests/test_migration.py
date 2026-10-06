"""Project-local account data migration keeps encrypted files and backups intact."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pysteam import EncryptedFileCredentialStore, LoginCredentials, ProfileError
from pysteam.accounts.migration import migrate_legacy_data
from pysteam.accounts.profiles import (
    ProfileRegistry,
    SavedProfile,
    default_profile_dir,
    legacy_profile_dir,
)
from pysteam.cli import main


def _locations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    config = tmp_path / "old-config"
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(config))
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    target = tmp_path / "project" / ".pysteam"
    monkeypatch.setenv("PYSTEAM_HOME", str(target))
    return legacy_profile_dir(), target


def test_default_account_data_is_local_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYSTEAM_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert default_profile_dir() == tmp_path / ".pysteam"
    monkeypatch.setenv("PYSTEAM_HOME", str(tmp_path / "custom"))
    assert default_profile_dir() == tmp_path / "custom"


def test_migrate_legacy_data_moves_store_and_mafile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, target = _locations(tmp_path, monkeypatch)
    registry = ProfileRegistry(old)
    mafile = old / "maFiles" / "backup" / "41.maFile"
    mafile.parent.mkdir(parents=True)
    mafile.write_bytes(b"encrypted-mafile")
    mafile.with_name("manifest.json").write_bytes(b"manifest")
    mafile.with_name("recovery.txt").write_bytes(b"recovery")
    profile = SavedProfile("first", 41, registry.store_path(41), mafile)
    registry.add(profile)
    asyncio.run(
        EncryptedFileCredentialStore(profile.store_path, "secret").save(
            "first", LoginCredentials(password="steam-password", steam_id=41)
        )
    )
    legacy = old / "credentials" / "41.bin"
    legacy.parent.mkdir()
    legacy.write_bytes(b"old-store")

    result, removed = migrate_legacy_data()
    assert result == target and removed
    assert not old.exists()
    moved = ProfileRegistry(target).select("first")
    assert moved.mafile_path == target / "maFiles" / "backup" / "41.maFile"
    assert moved.mafile_path.read_bytes() == b"encrypted-mafile"
    assert moved.mafile_path.with_name("manifest.json").read_bytes() == b"manifest"
    assert moved.mafile_path.with_name("recovery.txt").read_bytes() == b"recovery"
    assert (target / "credentials" / "41.bin").read_bytes() == b"old-store"
    saved = asyncio.run(EncryptedFileCredentialStore(moved.store_path, "secret").load("first"))
    assert saved is not None and saved.password == "steam-password"
    listed = CliRunner().invoke(main, ["account", "list"])
    assert listed.exit_code == 0 and "first" in listed.output


def test_migration_preserves_source_on_conflict_or_missing_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, target = _locations(tmp_path, monkeypatch)
    registry = ProfileRegistry(old)
    registry.add(SavedProfile("first", 41, registry.store_path(41)))
    target.mkdir(parents=True)
    marker = target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(ProfileError, match="already exists"):
        migrate_legacy_data()
    assert marker.read_text(encoding="utf-8") == "keep"
    marker.unlink()
    target.rmdir()
    with pytest.raises(ProfileError, match="credential store is missing"):
        migrate_legacy_data()
    assert old.exists() and not target.exists()
