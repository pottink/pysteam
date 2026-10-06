# Release guide

The distribution name is `pysteam-sdk` and the import name is `pysteam`. The
release workflow is manual. It builds from a version tag, verifies the resulting
wheel and source archive, then uploads them through PyPI Trusted Publishing.

## Release checklist

1. Run the checks on Windows, Linux, and macOS with Python 3.13 and 3.14.
   The Python 3.15 preview lane is advisory until its final release and
   dependencies are verified.
2. Confirm generated protobuf classes, the issue audit, formatting, types,
   tests, and both distribution artifacts:

   ```powershell
   uv sync --locked --group dev
   uv run python scripts/generate_protos.py --check
   uv run python scripts/audit_issues.py --check
   uv run ruff check src scripts tests
   uv run ruff format --check src scripts tests
   uv run mypy
   uv run pytest -q
   uv build --no-sources
   uv run python scripts/check_release_artifacts.py
   uv run python scripts/check_wheel.py --python 3.14
   ```

3. Run opt-in live checks with a separate Steam account controlled by the
   maintainer. Cover saved login, Steam Guard challenges, CM reconnects, PICS,
   a permitted depot archive and offline extraction, Workshop, and SIS import
   and export. See the smoke scripts for their environment variables:

   ```powershell
   uv run python scripts/smoke_live.py --saved-account TEST_ACCOUNT
   uv run python scripts/smoke_archive.py --i-control-account --account TEST_ACCOUNT
   ```

4. Keep smoke records outside the repository. Record the date, package commit,
   tested app and depot IDs, and outcome. Never commit credentials, tokens,
   account identities, Guard material, depot keys, or raw authenticated
   traffic.
5. Resolve confirmed in-scope defects. Review the
   [issue audit](issue-audit.json) and check the distribution name on PyPI
   immediately before publishing.

## Trusted Publisher setup

Create a GitHub environment named `pypi`, with the desired reviewer and
deployment restrictions. In PyPI's Publishing settings, configure a pending
GitHub Trusted Publisher for project `pysteam-sdk`, owner `pottink`,
repository `pysteam`, workflow `release.yml`, and environment `pypi`.
The values must match. A pending publisher does not reserve the package name.

After the checklist passes, update `pyproject.toml` to the release version,
merge the release commit into `main`, and wait for CI. Create and push an
annotated `v`-prefixed tag matching that version. Manually dispatch
**Publish to PyPI** at that tag and approve the protected environment after
reviewing the build. The workflow does not publish on ordinary pushes or tag
creation and needs no PyPI token.

Inspect the published files and install the exact version in an isolated
environment. A PyPI upload is public and its version cannot be replaced.
