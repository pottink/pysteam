# Examples

The examples use Python 3.13 or 3.14 and `pysteam-sdk`. Keep refresh tokens,
passwords, depot keys, and Web API keys in a secret store or environment variable.
For everyday login, [register a saved account](#saved-account-profiles) once;
the direct authentication examples below are for applications managing their
own credentials and challenges.

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
        await client.logon(
            tokens.refresh_token,
            account_name=tokens.account_name,
            steam_id=tokens.steam_id,
        )
        print("Authenticated SteamID:", tokens.steam_id)


asyncio.run(main())
```

For QR, call `await client.auth.begin_qr()` and display
`session.challenge_url` to the account owner. After approval, call
`await session.wait_for_tokens()` and then `await client.logon(...)`.
Steam may require another Guard step; handle only the confirmation types
listed by the session.

## Automatic login with a custom credential store

```python
import asyncio
import os
from pathlib import Path

from pysteam import (
    EncryptedFileCredentialStore, GuardChallenge, LoginCredentials, SteamClient,
)


async def on_challenge(challenge: GuardChallenge) -> str | None:
    if challenge.confirmation_type in (2, 3):  # Email or device code
        return await asyncio.to_thread(input, "Steam Guard code: ")
    if challenge.confirmation_type in (4, 5):  # Mobile or email approval
        print("Approve the pending Steam sign-in")
        return None
    raise RuntimeError("Unsupported Steam Guard confirmation")


async def main() -> None:
    store = EncryptedFileCredentialStore(
        Path(os.environ["PYSTEAM_STORE_PATH"]),
        os.environ["PYSTEAM_STORE_PASSPHRASE"],
    )
    async with SteamClient() as client:
        result = await client.login_auto(
            os.environ["STEAM_USERNAME"],
            credentials=LoginCredentials(
                password=os.environ.get("STEAM_PASSWORD"),
                shared_secret=os.environ.get("STEAM_SHARED_SECRET"),
            ),
            store=store,
            on_challenge=on_challenge,
        )
        print("Authenticated SteamID:", result.tokens.steam_id)


asyncio.run(main())
```

After the first login, the store can supply the saved credentials and refresh
token without `STEAM_PASSWORD` or `STEAM_SHARED_SECRET` in the environment.
The application supplies the encryption passphrase at startup; it is never
written into the credential file. Omit `store=` to manage tokens and Guard
data yourself through `LoginResult.tokens`. If human approval is needed and
`on_challenge` is absent, `AuthenticationInteractionRequired` contains the
live `AuthSession` for manual handling. Mobile app approvals are never
performed automatically.

## Import an existing Steam Guard maFile

For the CLI, run `uv run pysteam account add ACCOUNT --mafile PATH` once. It
copies the login-relevant secret into that account's encrypted store, records
the backup path, and leaves the maFile untouched. Later `pysteam login` and
depot commands use the selected account without the path. The following API
example shows direct, read-only import when an application manages its own
store.

`load_mafile()` reads one file from steamguard-cli or Steam Desktop
Authenticator. For encrypted files, pass the authenticator file's passphrase;
the adjacent `manifest.json` supplies its encryption settings. Import never
changes either file and does not access steamguard-cli's system keyring.

```python
import asyncio
import os
from pathlib import Path

from pysteam import EncryptedFileCredentialStore, LoginCredentials, SteamClient, load_mafile


async def main() -> None:
    imported = load_mafile(
        Path(os.environ["STEAM_MAFILE_PATH"]),
        passphrase=os.environ.get("STEAM_MAFILE_PASSPHRASE"),
    )
    store = EncryptedFileCredentialStore(
        Path(os.environ["PYSTEAM_STORE_PATH"]),
        os.environ["PYSTEAM_STORE_PASSPHRASE"],
    )
    saved = await store.load(imported.account_name)
    credentials = imported.credentials.with_fallback(saved)
    if not credentials.refresh_token and not credentials.password:
        credentials = credentials.with_fallback(
            LoginCredentials(password=os.environ["STEAM_PASSWORD"])
        )
    async with SteamClient() as client:
        result = await client.login_auto(
            imported.account_name,
            credentials=credentials,
            store=store,
        )
        print("Authenticated SteamID:", result.tokens.steam_id)


asyncio.run(main())
```

The import returns only the account name, SteamID, and shared secret. Supply a
password or refresh token for the first login. When `store=` is provided,
`login_auto()` saves the credentials and renewed token in that encrypted store;
later runs can use the saved refresh token without `STEAM_PASSWORD`. Omit
`store=` to keep the import entirely read-only. Do not pass the maFile's
recovery code or identity secret to the login API.

## Enroll a new Steam Guard authenticator

To create a new authenticator and register it as a saved account, run:

```powershell
uv run pysteam account add ACCOUNT --enroll
```

The command prompts for the password, any current login confirmation, a
**separate** encryption passphrase for the maFile backup, and Steam's SMS or
email activation code. It saves an encrypted maFile and matching
`manifest.json` **before** finalizing activation, shows the recovery code for
you to write down, and verifies Steam reports an active authenticator. Keep a
backup of the complete output directory and the recovery code. Do not lose the
backup passphrase. It then verifies a fresh login and saves the new account
profile. Existing authenticators are left alone; enrollment stops if one is
already active.

By default the backup goes into a new `maFiles/<random-id>` directory under
`./.pysteam` in the current working directory. Pass `--backup-dir NEW_DIRECTORY` to choose a
different location; that directory must not exist yet. `account show ACCOUNT`
displays the resulting maFile path after registration.

If activation fails after the backup was saved, keep the files and retry with:

```powershell
uv run pysteam account add ACCOUNT --enroll --resume-enrollment "PATH_TO_MAFILE"
```

If activation succeeds but the profile login fails, keep the verified backup
and register it with `pysteam account add ACCOUNT --mafile PATH`.

`GuardEnrollmentClient(client).login_and_begin(...)` and
`PendingGuardEnrollment.finalize(code)` expose the same two phases to
applications. The first phase requires a new output directory and a
passphrase; the resulting `recovery_code` and tokens are redacted in object
representations. The SDK does not automatically transfer or revoke an
existing authenticator or add a phone number to the account. The standalone
`scripts/enroll_guard.py` and `scripts/test_mafile_login.py` remain available
for manual diagnosis without creating a saved profile. The enrollment script
uses `--resume PATH` rather than the account command's `--resume-enrollment`.
For a standalone check, run `uv run python scripts/enroll_guard.py`; it asks
for the account name and saves the backup without adding a profile.

Add `--debug` for timestamped CM and authentication progress. Debug output
contains message IDs, confirmation types, connection stages, and safe error
codes; it omits packet bodies, account names, passwords, secrets, codes, and
tokens. Typer handles command options and usage errors. Rich formats the
status lines, log columns, and final success panel; it adapts colors and
borders to the terminal. Both are installed with `pysteam-sdk`.

## Command-line tools

### Saved account profiles

Register each account once. An existing maFile is imported read-only. When a
password is needed, the CLI asks through a hidden prompt, never an argument:

```powershell
uv run pysteam init
uv run pysteam account add FIRST_ACCOUNT --mafile "FIRST_MAFILE_PATH"
uv run pysteam account add SECOND_ACCOUNT --mafile "SECOND_MAFILE_PATH"
uv run pysteam account add THIRD_ACCOUNT
uv run pysteam account list
uv run pysteam account use SECOND_ACCOUNT
uv run pysteam account show FIRST_ACCOUNT
uv run pysteam login
```

`init` prompts twice for a new vault password. `account add` offers the same
setup if no vault exists. The vault encrypts a random master key; that key
protects all registered account stores. Later CLI processes prompt once for
the vault password. For unattended use, inject
`PYSTEAM_VAULT_PASSPHRASE` from a secret manager. The older
`PYSTEAM_STORE_PASSPHRASE` name is an alias; setting both to different values
is an error. A maFile backup has its own separate password.

To rotate a known password, run `uv run pysteam vault change-password`. This
rewraps the local vault and registered portable archive key capsules. Use
`pysteam archive rekey --archive PATH` when an archive was moved and is no
longer registered here. `pysteam vault status` shows setup state and archive
count.

If the vault password is forgotten, existing stores and archived depot keys
cannot be decrypted. Keep the encrypted files as backups, then create a new
vault in a fresh `PYSTEAM_HOME`, register accounts again from their maFiles,
and reacquire depot keys through Steam. Removing an account alone does not
reset the shared vault password.

To remove and later register one account:

```powershell
uv run pysteam account show FIRST_ACCOUNT
uv run pysteam account remove FIRST_ACCOUNT
uv run pysteam account add FIRST_ACCOUNT --mafile "FIRST_MAFILE_PATH"
```

`account remove` asks for confirmation and does not require the old store
passphrase. It deletes only that profile's managed encrypted store and registry
entry. The maFile backup and any older `credentials/<steamid>.bin` store remain
untouched. Use `--fresh` on `account add` if an older store exists and you do
not know its passphrase. A remaining account becomes the default when you
remove the current default. For scripts, `account remove NAME --yes` skips the
confirmation.

To create a new maFile during setup, use `account add ACCOUNT --enroll` as
described in [enrollment](#enroll-a-new-steam-guard-authenticator). For an
account without a maFile, `account add ACCOUNT` uses interactive Steam Guard
challenges and saves its login for later.

The first registered account is the default; `account use` changes it. `login`,
`guard code`, and depot commands use that profile automatically. `login NAME`
selects another account for login; `--account NAME` selects one for Guard and
depot commands. Depot `--anonymous` ignores the default.
`app` and `doctor` always use anonymous logon. Explicit `--mafile` and `--store`
options remain available for one-off use.

Each account has its own encrypted credential store under the vault. The password, shared secret,
Guard data, and renewed refresh token are saved in the encrypted store, while
`profiles.json` contains only account names, SteamIDs, and paths. The maFile
backup remains separate and untouched. Existing
`credentials/<steamid>.bin` stores can be imported once using their original
passphrase; `account add NAME --mafile PATH --fresh` skips that import and
starts a new login. The older store and original maFile remain untouched.

Account data lives under `./.pysteam` in the current working directory, which
is excluded from this repository by `.gitignore`. `account show NAME` displays
the exact encrypted-store and optional maFile backup paths. `PYSTEAM_HOME`
can select a stable directory when your scripts run from different working
directories. Keep project-local account data out of other version-control and
backup uploads.

If you already have saved data under `%APPDATA%\pysteam` (Windows) or
`${XDG_CONFIG_HOME:-~/.config}/pysteam` (Linux/macOS), move it once from the
directory where you plan to run `pysteam`:

```powershell
uv run pysteam account migrate
uv run pysteam account list
```

The migration copies and verifies encrypted stores, maFiles, manifests, and
recovery files before removing the old directory. It updates saved maFile
paths and does not need store or maFile passphrases. It refuses to overwrite an
existing `./.pysteam` directory.

SDK code can use the selected profile without passing a maFile path:

```python
import asyncio
from pysteam import SteamClient

async def main() -> None:
    async with SteamClient() as client:
        result = await client.login_saved()  # passphrase=... or environment variable
        print(result.tokens.steam_id)

asyncio.run(main())
```

Pass `account_name` to `login_saved(account_name)` to select another profile,
or `passphrase=` if your application obtains the vault password from its own
secret manager. `profile_dir=` selects another registry directory.
The SDK raises `ProfileError` if no profile or vault password is available;
it never prompts or reads profiles merely by constructing `SteamClient`.

### Inspect public PICS app info

This command signs in anonymously and shows a summary of app ID 220 with its
public depot manifest IDs. It does not need a maFile or Steam password:

```powershell
uv run pysteam app 220
```

Use `--json` to print the complete parsed PICS app-info response as JSON, or
`--debug` for redacted CM/PICS progress on stderr:

```powershell
uv run pysteam app 220 --json > app-220.json
uv run pysteam app 220 --debug
```

The JSON is the parsed VDF app-info payload, not a raw CM packet. Replace 220
with another public app ID to inspect it. The earlier
`scripts/inspect_app.py` command remains available as a wrapper.

### SteamID and Steam Guard code

```powershell
uv run pysteam steamid parse STEAM_0:1:4
uv run pysteam guard code
uv run pysteam guard code --account SECOND_ACCOUNT
```

`guard code` reads the selected account's encrypted credential store and
prints the current five-character code and seconds left in its 30-second
window. It requires a saved shared secret from a maFile. Treat the code as
sensitive. For a one-off file, use `guard code --mafile PATH`; it reads the
named maFile and prompts for
its backup passphrase if encrypted. Neither form changes the authenticator.

### Direct maFile login without registration

To check a maFile without writing any credential store, run:

```powershell
uv run python scripts/test_mafile_login.py "PATH_TO_MAFILE"
```

It prompts for the backup passphrase and Steam password, and does not save
credentials unless `--remember` is supplied.

For a one-off CLI login that remembers credentials in the older store layout:

```powershell
uv run pysteam login YOUR_ACCOUNT --mafile "PATH_TO_MAFILE" --remember
```

The `pysteam login ... --remember` flow remains available. Its first run
prompts for the maFile passphrase and, if no token is saved, the Steam password.
It saves the refresh
token, password, Guard data, and shared secret because `--remember` was
requested. Later runs with the same
command reuse the token and prompt only for the backup passphrase. An existing
default store is also reused when `--remember` is omitted. Use `--store PATH`
to select a separate encrypted credential file; that file has its own prompted
passphrase. Without a maFile, use `--store PATH` with the account name or sign
in interactively with the password and Steam Guard challenge. Email codes and
mobile approvals remain interactive. The command never prints tokens or
passwords.

### Depot files and diagnostics

```powershell
uv run pysteam doctor
uv run pysteam depot list 220 221
uv run pysteam depot list 220 221 --account SECOND_ACCOUNT --json
uv run pysteam depot download 220 221 --file "path/from/manifest.txt" --output .\downloads
uv run pysteam depot list 220 221 --anonymous
```

Use depot IDs and file paths from `pysteam app APP_ID` and `depot list`.
`depot download` requires `--file` or `--all` and does not replace an
existing file unless `--overwrite` is passed. Downloaded chunks and the full
file are verified by the SDK before the destination is replaced. The depot
commands use the selected saved account when one exists. `--account NAME`
selects another profile, and `--anonymous` bypasses the default when Steam
permits anonymous access. Many depots require an account that owns the content.
You can still use `--mafile PATH` or `--account NAME --store PATH` for a one-off
login. `--manifest ID` selects a specific manifest; otherwise the public branch
manifest comes from PICS. `doctor` checks CM discovery, WebSocket connection,
anonymous logon, and PICS without accessing saved credentials. Add `--debug`
to network commands for redacted logs.

## Content preservation

The default archive is `./steam-archive`. It keeps original depot manifests,
deduplicated **encrypted** CDN chunks, app metadata, and a separately salted
encrypted depot-key capsule. Move the whole folder to another machine and
unlock it with the vault password to verify or extract offline. The archive
password is separate from the maFile backup password. The archive location can
be changed with `--archive PATH`. `PYSTEAM_HOME` controls the local account
vault, not the archive location.

```powershell
uv run pysteam archive depot 220 221
uv run pysteam archive app 220 --max-downloads 8 --cpu-workers 0
uv run pysteam archive list --json
uv run pysteam archive inspect 221 MANIFEST_ID
uv run pysteam archive verify 221 MANIFEST_ID
uv run pysteam archive extract 221 MANIFEST_ID --output restored
uv run pysteam archive diff 221 OLD_MANIFEST NEW_MANIFEST --json
uv run pysteam archive repair 221 MANIFEST_ID
uv run pysteam depot download 220 221 --all --include "*.txt" --exclude "docs/*"
```

`archive depot` accepts `--manifest ID` and `--branch NAME` for a specific
version. `archive app` archives the depots PICS lists for a branch. A job is
marked complete only after every referenced chunk and file passes integrity
checks. A later run resumes from verified chunks. Network work uses bounded
async workers (default 8, limit 64) and a 256 MiB in-flight budget; set
`--cpu-workers` to use processes for decoding and verification. `--account`
selects a saved account and `--anonymous` requests anonymous access. Steam
access rights still apply. Extraction rejects unsafe paths and requires
`--overwrite` before replacing files.

Batch input is UTF-8 CSV with `AppID,DepotID,ManifestID,Branch` columns;
`ManifestID` and `Branch` may be blank:

```powershell
uv run pysteam archive batch jobs.csv --account SECOND_ACCOUNT
```

To import a steamarchiver `depots/<depot>/<manifest>.zip` plus SHA-named chunk
folder, run the following command. It reads the old files and asks privately
for a 64-character depot key if the destination archive has none:

```powershell
uv run pysteam archive import ./old-steamarchiver APP_ID DEPOT_ID MANIFEST_ID
```

An incomplete legacy folder stays marked incomplete; `archive repair` can
fetch missing chunks later. The SDK offers `ArchiveStore` for offline
inspection and `ContentArchiver` for online preservation:

```python
import os
from pathlib import Path
from pysteam import ArchiveStore, ContentArchiver, SteamClient

async def preserve() -> None:
    password = os.environ["PYSTEAM_VAULT_PASSPHRASE"]
    store = ArchiveStore(Path("steam-archive"), password)
    async with SteamClient() as steam:
        await steam.login_saved(passphrase=password)
        result = await ContentArchiver(steam, store).archive_depot(220, 221)
    store.verify(221, result.manifest_id)
    store.extract(221, result.manifest_id, Path("restored"))
```

`EncryptedFileCredentialStore` remains available independently of the CLI
vault. SDK code supplies its own passphrases and does not prompt.

### App metadata, Workshop, and client updates

```powershell
uv run pysteam appinfo snapshot 220 570
uv run pysteam appinfo update --json
uv run pysteam workshop query 440 --search "map" --page 1 --json
uv run pysteam workshop archive PUBLISHED_FILE_ID
uv run pysteam client archive steam_client_win32 --format zip
```

`appinfo snapshot` stores original PICS response bytes, and `update` refreshes
the saved AppIDs (or the IDs you pass). Workshop query and details use
PublishedFile unified messages. SteamPipe Workshop items archive through the
depot pipeline; an item with an HTTPS file URL is streamed to a separate
content-addressed blob. Steam client update hosts come from the current
ContentServerDirectory response; packages are saved by SHA-256 after checking
the manifest hash. `client archive` accepts `--format zip|vz|both` and
`--max-downloads`. These commands use the selected account, or `--anonymous`.

### Steam backups

```powershell
uv run pysteam sis inspect ./backup/sku.sis --json
uv run pysteam sis export 220 --output ./sis-export
uv run pysteam sis import ./backup/sku.sis
uv run pysteam sis repack ./backup/sku.sis --output ./normalized-backup
```

`sis inspect` also accepts a standalone `.csm` index. Export requires a
complete verified archive; it writes `sku.sis`, encrypted `.csm/.csd` files,
and original manifest sidecars. Import needs matching manifests and depot keys
in the archive, or the exported sidecars and a privately prompted depot key.
Repack accepts encrypted backup containers and writes a new destination. The
source backup is never edited. `sis export` and `sis repack` refuse to replace
existing output unless `--overwrite` is passed.

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
