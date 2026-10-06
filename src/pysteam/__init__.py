"""Modern async Steam SDK."""

from pysteam.auth import (
    AccessTokenResult,
    AuthenticationClient,
    AuthenticationInteractionRequired,
    AuthSession,
    AuthTokens,
    GuardChallenge,
    GuardChallengeHandler,
    LoginResult,
)
from pysteam.cdn import (
    CDNClient,
    DepotChunk,
    DepotFile,
    DepotManifest,
    parse_manifest,
    process_chunk,
)
from pysteam.client import PICSInfo, SteamClient
from pysteam.credentials import CredentialStore, EncryptedFileCredentialStore, LoginCredentials
from pysteam.errors import (
    AuthenticationError,
    CDNError,
    CDNHTTPError,
    CredentialStoreError,
    ProtocolError,
    RequestTimeout,
    SteamError,
    SteamResultError,
    TransportError,
    WebAPIError,
)
from pysteam.guard import confirmation_key, guard_code
from pysteam.ids import SteamID
from pysteam.pics import PICSAccessTokens, extract_manifest_ids, parse_app_vdf
from pysteam.webapi import WebAPIClient

__version__ = "0.1.0a0"

__all__ = [
    "AccessTokenResult",
    "AuthSession",
    "AuthTokens",
    "AuthenticationClient",
    "AuthenticationError",
    "AuthenticationInteractionRequired",
    "CDNClient",
    "CDNError",
    "CDNHTTPError",
    "CredentialStore",
    "CredentialStoreError",
    "DepotChunk",
    "DepotFile",
    "DepotManifest",
    "EncryptedFileCredentialStore",
    "GuardChallenge",
    "GuardChallengeHandler",
    "LoginCredentials",
    "LoginResult",
    "PICSAccessTokens",
    "PICSInfo",
    "ProtocolError",
    "RequestTimeout",
    "SteamClient",
    "SteamError",
    "SteamID",
    "SteamResultError",
    "TransportError",
    "WebAPIClient",
    "WebAPIError",
    "confirmation_key",
    "extract_manifest_ids",
    "guard_code",
    "parse_app_vdf",
    "parse_manifest",
    "process_chunk",
]
