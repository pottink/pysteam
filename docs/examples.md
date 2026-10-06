# Examples

The examples use Python 3.13 or 3.14 and `pysteam-sdk`. Keep refresh tokens,
passwords, depot keys, and Web API keys in a secret store or environment variable.

## Anonymous CM and PICS

```python
import asyncio
from pysteam import SteamClient


async def main() -> None:
    async with SteamClient() as client:
        await client.login_anonymous()
        info = await client.get_product_info(app_ids=[570])
        print(sorted(info.apps))
        manifest_ids = await client.get_app_manifest_ids(570, branch="public")
        print(manifest_ids)  # {depot_id: manifest_id}


asyncio.run(main())
```

## Credential or QR authentication

```python
import asyncio
import os
from pysteam import SteamClient


async def main() -> None:
    async with SteamClient() as client:
        session = await client.auth.begin_credentials(
            os.environ["STEAM_TEST_USERNAME"],
            os.environ["STEAM_TEST_PASSWORD"],
            remember_login=True,
        )
        # If Steam requests an email or device code, submit it with the
        # code_type listed in session.allowed_confirmations.
        tokens = await session.wait_for_tokens()
        await client.logon(tokens.refresh_token, steam_id=tokens.steam_id)
        print("Authenticated SteamID:", tokens.steam_id)


asyncio.run(main())
```

For QR, call `await client.auth.begin_qr()` and display
`session.challenge_url` to the account owner. After approval, call
`await session.wait_for_tokens()` and then `await client.logon(...)`.
Steam may require another Guard step; handle only the confirmation types
listed by the session.

## Web API with a typed response

```python
import asyncio
import os
from msgspec import Struct
from pysteam import WebAPIClient


class PlayerSummary(Struct):
    steamid: str
    personaname: str


class Summaries(Struct):
    players: list[PlayerSummary]


async def main() -> None:
    async with WebAPIClient(key=os.environ["STEAM_WEB_API_KEY"]) as api:
        result = await api.call_typed(
            "ISteamUser", "GetPlayerSummaries", Summaries,
            version=2, params={"steamids": "76561197960435530"},
        )
        print(result.players[0].personaname)


asyncio.run(main())
```

Methods that need a Web API key require `WebAPIClient(key=...)`.

## CDN manifest and verified download

```python
from pathlib import Path
from pysteam import SteamClient


async def download_owned_depot(
    client: SteamClient, app_id: int, depot_id: int
) -> None:
    manifest_id = (await client.get_app_manifest_ids(app_id))[depot_id]
    server = (await client.cdn.servers())[0]
    depot_key = await client.cdn.get_depot_key(app_id, depot_id)
    manifest = await client.cdn.get_manifest(
        server=server, app_id=app_id, depot_id=depot_id,
        manifest_id=manifest_id, depot_key=depot_key,
    )
    file = manifest.file("path/from/manifest.txt")
    await client.cdn.download_file(
        server=server, manifest=manifest, file=file, depot_key=depot_key,
        destination=Path("downloads") / file.name,
    )
```

The account must have access to the depot. If the CDN server requires an auth
token, get one with `client.cdn.get_auth_token()` and pass `auth_token=` to the
manifest and file methods. A completed download replaces the destination only
after all chunks and the full file have passed integrity checks.
For another branch, pass the same `branch=` to `get_app_manifest_ids()` and
`get_manifest()`, along with `branch_password_hash=` to `get_manifest()` when
Steam requires it.

## Game Coordinator

```python
await client.send_gc(app_id=570, msg_type=your_message_type, payload=your_payload)
reply = await client.recv_gc(timeout=20)
print(reply.appid, reply.msgtype, len(reply.payload))
```

GC message types and payload schemas are game specific. The SDK carries their
bytes without interpreting game-specific messages.
