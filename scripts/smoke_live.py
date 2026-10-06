"""Opt-in live smoke test. Never prints token or packet contents."""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from pysteam import SteamClient, WebAPIClient


async def smoke(*, anonymous: bool) -> None:
    token = None if anonymous else os.environ.get("PYSTEAM_TEST_REFRESH_TOKEN")
    if not anonymous and not token:
        raise RuntimeError("PYSTEAM_TEST_REFRESH_TOKEN is required")
    async with SteamClient(timeout=10, auto_reconnect=False) as client:
        if anonymous:
            await client.login_anonymous()
            print("Anonymous CM logon succeeded")
        else:
            assert token is not None
            await client.logon(token)
            print(f"CM logon succeeded for SteamID {client.steam_id}")
        info = await client.get_product_info(app_ids=[570])
        if 570 not in info.apps:
            raise RuntimeError("PICS did not return app 570")
        print("PICS app 570 succeeded")
        servers = await client.cdn.servers()
        if not servers:
            raise RuntimeError("CDN server discovery returned no servers")
        print("CDN server discovery succeeded")
        app = os.environ.get("PYSTEAM_TEST_APP_ID")
        depot = os.environ.get("PYSTEAM_TEST_DEPOT_ID")
        manifest = os.environ.get("PYSTEAM_TEST_MANIFEST_ID")
        if not anonymous and app and depot and manifest:
            app_id, depot_id, manifest_id = int(app), int(depot), int(manifest)
            key = await client.cdn.get_depot_key(app_id, depot_id)
            auth_token = ""
            if os.environ.get("PYSTEAM_TEST_CDN_AUTH") == "1":
                host = urlsplit(servers[0]).hostname
                if host is None:
                    raise RuntimeError("CDN server URL has no host")
                auth_token = await client.cdn.get_auth_token(app_id, depot_id, host)
            result = await client.cdn.get_manifest(
                server=servers[0],
                app_id=app_id,
                depot_id=depot_id,
                manifest_id=manifest_id,
                depot_key=key,
                auth_token=auth_token,
            )
            print(f"CDN manifest {result.manifest_id} parsed with {len(result.files)} files")
            filename = os.environ.get("PYSTEAM_TEST_FILE")
            if filename:
                sample = result.file(filename)
                with tempfile.TemporaryDirectory(prefix="pysteam-smoke-") as directory:
                    destination = Path(directory) / "sample"
                    await client.cdn.download_file(
                        server=servers[0],
                        manifest=result,
                        file=sample,
                        depot_key=key,
                        destination=destination,
                        auth_token=auth_token,
                    )
                    if destination.stat().st_size != sample.size:
                        raise RuntimeError("CDN sample file size mismatch")
                print("CDN sample file integrity succeeded")
    async with WebAPIClient(timeout=10) as api:
        await api.call("ISteamWebAPIUtil", "GetServerInfo")
        print("Web API server info succeeded")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--i-control-account", action="store_true")
    mode.add_argument("--anonymous", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(smoke(anonymous=arguments.anonymous))


if __name__ == "__main__":
    main()
