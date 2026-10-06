# pysteam

`pysteam-sdk` is an asyncio-first Python SDK for Steam. The import package is
`pysteam`. It is a new API; it does not provide the legacy `steam` namespace.

The project is under active development. The package version is pre-release and
must not be used as proof of Steam service interoperability until the opt-in
account smoke tests in `docs/release.md` have passed.

## API

`SteamClient` manages a secure WebSocket CM connection, anonymous and
refresh-token logon, Unified Messages, PICS, Game Coordinator packets, and
access to `AuthenticationClient` and `CDNClient`. `WebAPIClient` offers both
dictionary and `msgspec`-typed responses. `SteamID` and Steam Guard helpers
are synchronous. See [examples](docs/examples.md) for usage.

Python 3.13 and 3.14 are supported. Python 3.15 is checked in an advisory CI
lane while interpreter and dependency compatibility are verified.

## Issue audit and release

The kickoff snapshot in [issue-audit.json](docs/issue-audit.json) records all
42 open ValvePython/steam issues and all 36 open SteamRE/SteamKit issues, plus
15 relevant closed reports. Each entry records scope and regression coverage.
The [release gate](docs/release.md) requires account-controlled live smoke
tests before publication.

## Development

```powershell
uv sync --group dev
uv run python scripts/generate_protos.py --check
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv build --no-sources
```

The source schemas are pinned as a Git submodule under
`vendor/steam-protobufs`. If they are absent after cloning, run
`git submodule update --init --recursive` before generating.
The source distribution includes the schema snapshot and its Unlicense notice
so protobuf generation remains reproducible outside a Git checkout.

## Source provenance

- Steam protocol schemas: SteamTracking/Protobufs, pinned by the submodule.
  The upstream repository marks them Unlicense.
- Historical API and issue reference: ValvePython/steam at
  `26166e047b66a7be10bdf3c90e2e14de9283ab5a` (MIT).
- Current behavior reference: SteamRE/SteamKit at
  `84c990c3982eedb5abd733116b987c9870a0dccb` (LGPL-2.1-only).
  `tests/fixtures/steamkit_client_hello.json` pins a wire-frame fixture
  derived from its `MsgHdrProtoBuf.Serialize` header layout and the shared
  protobuf schema.

The Python implementation is original code. SteamKit implementation code is
not copied into this package.
