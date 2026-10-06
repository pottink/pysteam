# Release gate

## Current status (2026-10-06)

- Offline checks pass on Python 3.13 and 3.14, including 117 tests, protobuf
  generation, issue-audit validation, Ruff, mypy, package builds, and isolated
  wheel import and CLI checks.
- Windows, Linux, and macOS CI passed on Python 3.13 and 3.14 for the last
  checked `main` commit. The Python 3.15 preview lane also passed. Check CI
  again after each release change.
- Anonymous live checks passed for CM logon, PICS app data and manifest
  references, CDN server discovery, WebAPI server info, and Steam time sync.
  `pysteam doctor` and `pysteam app 220` also passed.
- Multi-account profiles, vault migration, Steam Guard enrollment handoff,
  authentication, and content tools have offline coverage. Dedicated-account
  login, QR, GC, authenticated depot, and archive/restore checks remain pending.
- Anonymous depot-key access for a protected depot returned EResult 15, as
  expected; the CLI explains that an entitled account is needed.
- The `pysteam-sdk` PyPI JSON endpoint returned HTTP 404 on this date. This is
  not a reservation; check again immediately before publishing.
- The portable archive, first-run vault, SteamPipe/SIS import and export,
  Workshop metadata and content, and Steam client package commands have
  offline fixtures and command checks. Anonymous live Workshop discovery and
  Steam client update manifest retrieval passed. A package download and
  controlled-account archive/restore smoke have not been run.
- Synthetic 1, 8, and 16-worker archive benchmarks are recorded in
  [archive-benchmark.md](archive-benchmark.md). They are local fixture
  measurements, not Steam CDN throughput claims.
- Vault password rotation updates registered archive capsules during a normal
  run and rolls them back on a handled failure. A power loss during rotation
  can leave a subset using the new password; preserve both passwords until
  all registered archives have been verified.
- No release has been published.

The first public release is gated on all of the following:

1. Windows, Linux, and macOS CI pass for Python 3.13 and 3.14.
2. `uv sync --locked --group dev`, protobuf generation check, Ruff, mypy,
   pytest, issue-audit validation, build, and isolated wheel import/CLI pass.
3. Run the account and archive smoke procedures below with a separate Steam account
   controlled by the maintainer. Record date, tested SteamID, app/depot IDs,
   outcome, and SDK commit, but never credentials, tokens, Guard secrets,
   network packet bodies, or depot keys.
4. Verify portable offline extraction, SIS export and import, and Workshop
   content with controlled content on each supported platform.
5. Resolve any confirmed first-release defect found by the issue audit or
   smoke tests. `docs/issue-audit.json` contains the kickoff snapshot.
6. Recheck availability of the `pysteam-sdk` distribution name and publish
   only after the gate passes.

## Account smoke procedure

Use a dedicated test account. Supply `PYSTEAM_TEST_USERNAME` and its refresh
token through `PYSTEAM_TEST_REFRESH_TOKEN`, then run:

```powershell
uv run python scripts/smoke_live.py --i-control-account
```

An anonymous read-only CM/PICS check can be run separately with
`uv run python scripts/smoke_live.py --anonymous`. It does not replace the
account smoke procedure.

This verifies CM discovery, refresh-token logon,
and PICS for app 570. Separately exercise anonymous logon, credential login
with each allowed Guard challenge type, QR approval, reconnect after a
controlled socket closure, and GC messaging in an app that supports it.
For a depot the account owns, set the optional app/depot/manifest variables
`PYSTEAM_TEST_APP_ID`, `PYSTEAM_TEST_DEPOT_ID`, and
`PYSTEAM_TEST_MANIFEST_ID`. Set `PYSTEAM_TEST_FILE` to one manifest filename
to download and verify a sample. If the CDN needs an auth token, set
`PYSTEAM_TEST_CDN_AUTH=1`. The script discards the sample file after checking
it. Inspect exception types and Steam result codes without recording secrets.

For automatic Steam Guard login, use a separate account with a known shared
secret and supply `PYSTEAM_TEST_USERNAME`, `PYSTEAM_TEST_PASSWORD`,
`PYSTEAM_TEST_SHARED_SECRET`, and `PYSTEAM_TEST_STORE_PASSPHRASE` through a
secret manager. Run `uv run python scripts/smoke_live.py --auto-login`. The
encrypted test store is created in a temporary directory and removed after
the login. This opt-in procedure has not yet been run.

Before publishing the enrollment feature, use a separate account without an
existing mobile authenticator. Exercise both account setup paths with two
test accounts:

```powershell
uv run pysteam account add NEW_TEST_ACCOUNT --enroll
uv run pysteam account add EXISTING_TEST_ACCOUNT --mafile "PATH_TO_TEST_MAFILE"
uv run pysteam account list
uv run pysteam account use EXISTING_TEST_ACCOUNT
uv run pysteam login
uv run pysteam guard code
```

Supply `PYSTEAM_VAULT_PASSPHRASE` through a secret manager
(`PYSTEAM_STORE_PASSPHRASE` remains an alias). Check an entitled
depot command without repeating the maFile path, explicit `--account`
selection, and that switching the default does not mix encrypted stores.
Confirm `--anonymous` bypasses the selected account for depot access.

Verify that the backup folder contains an encrypted maFile and manifest, that
`load_mafile()` can read it with the passphrase, and that Steam reports active
enrollment. Record only the outcome, date, SteamID, and SDK commit. Keep the
recovery code, passphrase, backup contents, and activation code out of the
test record. Also verify `--resume-enrollment` on an intentionally interrupted
enrollment with a separate test account; do not remove or transfer an existing
authenticator as part of this smoke test.

## Content archive smoke procedure

On a dedicated account with rights to a small test depot, set
`PYSTEAM_TEST_USERNAME`, `PYSTEAM_TEST_REFRESH_TOKEN`,
`PYSTEAM_TEST_APP_ID`, `PYSTEAM_TEST_DEPOT_ID`, and
`PYSTEAM_TEST_MANIFEST_ID` through the test environment. Then run:

```powershell
uv run python scripts/smoke_archive.py --i-control-account
```

The script archives encrypted chunks, verifies the offline copy, extracts the
files to a temporary directory, and compares file digests. It is opt-in and
has not been run in this workspace. Also exercise `pysteam archive repair`
after removing a chunk from a *copy* of a test archive, `archive rekey` after
moving that copy to another directory, and SIS export/import with the same
controlled depot. Record IDs and results only; keep depot keys and tokens out
of logs and fixtures.

## Publishing

The release workflow at `.github/workflows/release.yml` runs only when started
manually. It requires a `v`-prefixed Git tag whose version exactly matches
`pyproject.toml`, repeats the offline checks, builds from source, tests the
wheel, and uploads the same artifacts through PyPI Trusted Publishing. It does
not publish on a push, tag creation, or ordinary CI run.

Once all release gates above pass:

1. Inspect the wheel and source archive for unintended files or private data.
   A PyPI upload is public and cannot be replaced at the same version.
2. In the GitHub repository, create an environment named `pypi` and configure
   its required reviewer and deployment restrictions for release tags.
3. In the PyPI account's **Publishing** settings, add a pending GitHub Trusted
   Publisher with project `pysteam-sdk`, owner `pottink`, repository `pysteam`,
   workflow `release.yml`, and environment `pypi`. The names must match exactly.
   A pending publisher does not reserve the project name.
4. Merge the release workflow into `main`, wait for CI to pass, then create and
   push an annotated tag for the package version. For the current alpha:

   ```powershell
   git tag -a v0.1.0a0 -m "pysteam-sdk 0.1.0a0"
   git push origin v0.1.0a0
   ```

5. Manually dispatch **Publish to PyPI** at that tag, using GitHub Actions or
   `gh workflow run release.yml --ref v0.1.0a0`. Approve the protected `pypi`
   environment after reviewing the build. The workflow needs no PyPI token.
6. Check the published files and install from PyPI in an isolated environment:

   ```powershell
   uv run --no-project --isolated --python 3.14 --with pysteam-sdk==0.1.0a0 python -c "import pysteam"
   ```

The 3.15 preview lane remains advisory until the final interpreter and
dependencies are verified and the supported-version metadata is updated.
