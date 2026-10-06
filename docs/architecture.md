# Package layout

`import pysteam` is the stable SDK entry point. `pysteam.cli:main` remains the
installed `pysteam` command.

| Location | Responsibility |
| --- | --- |
| `src/pysteam/client.py` | Async CM connection, logon, jobs, reconnects, and SDK service access. |
| `src/pysteam/protocol.py`, `proto/` | CM packet framing and generated Steam protobuf classes. |
| `src/pysteam/accounts/` | Authentication, Steam Guard, maFiles, profiles, credential stores, and the vault. |
| `src/pysteam/content/` | PICS, CDN, portable archives, Workshop, client updates, and SIS backups. |
| `src/pysteam/cli.py` | Typer application, shared login and vault workflows, and command registration. |
| `src/pysteam/_cli/` | Small command groups for accounts, depots, archives, app metadata, Workshop, client packages, and SIS. |
| `src/pysteam/ids.py`, `webapi.py`, `errors.py` | Small cross-cutting SDK primitives. |

Generated protobuf files stay isolated under `proto/`. Scripts for schema
generation, benchmarks, and opt-in smoke checks live in `scripts/`; tests live
in `tests/`. CLI modules use the SDK rather than exposing command helpers as
the SDK API.
