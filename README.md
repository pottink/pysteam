<p align="center">
  <img src="https://raw.githubusercontent.com/pottink/pysteam/main/docs/assets/pysteam-banner.svg" alt="pysteam — Python-first Steam SDK" width="100%">
</p>

<p align="center">
  <strong>Steam, from modern Python.</strong><br>
  An asyncio SDK and CLI for Steam authentication and content preservation.
</p>

<p align="center">
  <img alt="Python 3.13 and 3.14" src="https://img.shields.io/badge/Python-3.13%20%7C%203.14-3973A8?logo=python&amp;logoColor=white">
  <img alt="Status: alpha" src="https://img.shields.io/badge/status-alpha-E6AE58">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-43BFAE">
</p>

`pysteam-sdk` installs as `pysteam`. It is an independent Steam SDK built on secure CM WebSockets and current protobuf messages. **This first release is an alpha; APIs and archive formats may change.**

## What you can do

| Area | Possibilities |
| --- | --- |
| **Explore Steam** | Inspect PICS app data, branches, depot manifests, and SteamIDs. |
| **Sign in** | Use anonymous, password, refresh-token, or QR login; handle Steam Guard codes and interactive challenges. |
| **Manage accounts** | Import a maFile, enroll an authenticator, and switch between encrypted saved profiles. |
| **Preserve content** | Archive raw depot manifests and encrypted chunks; verify and extract offline. Import or export Steam backups. |
| **Explore updates** | Snapshot app metadata, query Workshop, and archive Steam client packages. |
| **Build integrations** | Call Unified Messages and WebAPI endpoints, or exchange Game Coordinator messages. |

## Get started

With [uv](https://docs.astral.sh/uv/) installed, add the SDK to a Python project:

```powershell
uv add pysteam-sdk
```

To use the standalone CLI:

```powershell
uv tool install pysteam-sdk
pysteam app 220
pysteam doctor
```

The last two commands inspect public app data and test connectivity without an account.

## Use your account

```powershell
uv run pysteam init
uv run pysteam account add YOUR_NAME --mafile "path/to/account.maFile"
# Or: uv run pysteam account add YOUR_NAME --enroll
uv run pysteam login
uv run pysteam guard code
uv run pysteam depot list 220 221
uv run pysteam archive app 220
uv run pysteam archive verify 221 MANIFEST_ID
uv run pysteam archive extract 221 MANIFEST_ID --output restored
```

`init` creates a protected vault under `./.pysteam`; account setup offers it automatically. Later commands ask for its password once per run. Set `PYSTEAM_VAULT_PASSPHRASE` through a secret manager for unattended use. Existing `PYSTEAM_STORE_PASSPHRASE` remains an alias. The maFile backup password is separate. Use `vault change-password` to rotate the vault and registered archive key capsules. See the [account and archive guide](https://github.com/pottink/pysteam/blob/main/docs/examples.md#content-preservation).

## Use the SDK

```python
import asyncio
from pysteam import SteamClient

async def main() -> None:
    async with SteamClient() as steam:
        await steam.login_anonymous()
        app = await steam.get_app_info(220)
        print(app["appid"])

asyncio.run(main())
```

See the [Python examples](https://github.com/pottink/pysteam/blob/main/docs/examples.md) for authentication, WebAPI, CDN, and Game Coordinator usage.

## Project links

- [CLI and SDK examples](https://github.com/pottink/pysteam/blob/main/docs/examples.md) · [protobuf updater](https://github.com/pottink/pysteam/blob/main/scripts/update_protos.py) · [issue audit](https://github.com/pottink/pysteam/blob/main/docs/issue-audit.json)
- [Development and release checks](https://github.com/pottink/pysteam/blob/main/docs/release.md) · [package layout](https://github.com/pottink/pysteam/blob/main/docs/architecture.md) · [content references](https://github.com/pottink/pysteam/blob/main/docs/content-references.md)

Licensed under [MIT](https://github.com/pottink/pysteam/blob/main/LICENSE). Independent of Valve and Steam.
