# Release gate

## Current status (2026-10-01)

- Windows local checks pass on Python 3.13 and 3.14: 26 offline tests, Ruff,
  and mypy. Protobuf generation, issue-audit validation, package build, and
  isolated wheel import pass on Python 3.14.
- Anonymous live checks passed for CM logon, PICS app 570, CDN server
  discovery, and WebAPI server info.
- Cross-platform CI has been configured but has not run because this local
  repository has no remote.
- Dedicated-account credential, QR, refresh-token, GC, and CDN manifest/file
  smoke tests remain to be run. No release has been published.
- The `pysteam-sdk` PyPI JSON endpoint returned HTTP 404 on this date;
  availability and ownership must be checked again before publication.

The first public release is gated on all of the following:

1. Windows, Linux, and macOS CI pass for Python 3.13 and 3.14.
2. `uv sync --locked --group dev`, protobuf generation check, Ruff, mypy,
   pytest, issue-audit validation, build, and isolated wheel import pass.
3. Run the account smoke procedures below with a separate Steam account
   controlled by the maintainer. Record date, tested SteamID, app/depot IDs,
   outcome, and SDK commit, but never credentials, tokens, Guard secrets,
   network packet bodies, or depot keys.
4. Resolve any confirmed first-release defect found by the issue audit or
   smoke tests. `docs/issue-audit.json` contains the kickoff snapshot.
5. Recheck availability of the `pysteam-sdk` distribution name and publish
   only after the gate passes.

## Account smoke procedure

Use a dedicated test account. With its refresh token supplied through
`PYSTEAM_TEST_REFRESH_TOKEN`, run:

```powershell
uv run python scripts/smoke_live.py --i-control-account
```

An anonymous read-only CM/PICS check can be run separately with
`uv run python scripts/smoke_live.py --anonymous`. It does not replace the
account smoke procedure.

This verifies CM discovery, refresh-token access-token generation, logon,
and PICS for app 570. Separately exercise anonymous logon, credential login
with each allowed Guard challenge type, QR approval, reconnect after a
controlled socket closure, and GC messaging in an app that supports it.
For a depot the account owns, set the optional app/depot/manifest variables
`PYSTEAM_TEST_APP_ID`, `PYSTEAM_TEST_DEPOT_ID`, and
`PYSTEAM_TEST_MANIFEST_ID`. Set `PYSTEAM_TEST_FILE` to one manifest filename
to download and verify a sample. If the CDN needs an auth token, set
`PYSTEAM_TEST_CDN_AUTH=1`. The script discards the sample file after checking
it. Inspect exception types and Steam result codes without recording secrets.

Do not publish from CI automatically. The 3.15 preview lane is advisory until
the final interpreter and dependencies are verified and the supported-version
metadata is updated.
