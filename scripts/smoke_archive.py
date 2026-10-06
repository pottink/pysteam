"""Opt-in live archive and offline restore using a controlled Steam account."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from pysteam import ArchiveStore, ContentArchiver, SteamClient
from pysteam.accounts.vault import vault_passphrase

main = typer.Typer(add_completion=False)


@main.command()
def smoke(
    i_control_account: Annotated[
        bool, typer.Option("--i-control-account", help="Confirm controlled test account use.")
    ] = False,
    account: Annotated[
        str | None, typer.Option("--account", help="Use a saved controlled-account profile.")
    ] = None,
) -> None:
    if not i_control_account:
        raise typer.BadParameter("pass --i-control-account to run the live check")
    names = ["PYSTEAM_TEST_APP_ID", "PYSTEAM_TEST_DEPOT_ID"]
    if account is None:
        names.extend(("PYSTEAM_TEST_USERNAME", "PYSTEAM_TEST_REFRESH_TOKEN"))
    if any(not os.environ.get(name) for name in names):
        raise typer.BadParameter("controlled-account smoke variables are incomplete")
    passphrase = vault_passphrase() or typer.prompt("Vault password", hide_input=True)
    asyncio.run(_run(account=account, passphrase=passphrase))


async def _run(*, account: str | None, passphrase: str) -> None:
    app_id = int(os.environ["PYSTEAM_TEST_APP_ID"])
    depot_id = int(os.environ["PYSTEAM_TEST_DEPOT_ID"])
    manifest = os.environ.get("PYSTEAM_TEST_MANIFEST_ID")
    manifest_id = int(manifest) if manifest else None
    with tempfile.TemporaryDirectory(prefix="pysteam-live-archive-") as directory:
        root = Path(directory)
        store = ArchiveStore(root / "archive", passphrase)
        async with SteamClient(timeout=20, auto_reconnect=True) as client:
            if account is None:
                await client.logon(
                    os.environ["PYSTEAM_TEST_REFRESH_TOKEN"],
                    account_name=os.environ["PYSTEAM_TEST_USERNAME"],
                )
            else:
                await client.login_saved(account, passphrase=passphrase)
            result = await ContentArchiver(client, store).archive_depot(
                app_id, depot_id, manifest_id=manifest_id
            )
        checked, missing = store.verify(depot_id, result.manifest_id)
        if missing:
            raise RuntimeError("live archive integrity check failed")
        files = [
            item.name
            for item in store.manifest(depot_id, result.manifest_id).files
            if not item.link_target and not item.flags & (64 | 512)
        ]
        if files:
            store.extract(depot_id, result.manifest_id, root / "restore", files=files[:1])
        print(
            f"Archive and offline restore passed: app {app_id}, depot {depot_id}, "
            f"manifest {result.manifest_id}, {checked} chunks"
        )


if __name__ == "__main__":
    main()
