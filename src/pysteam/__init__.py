"""Modern async Steam SDK."""

from pysteam.auth import AuthenticationClient, AuthSession, AuthTokens
from pysteam.cdn import (
    CDNClient,
    DepotChunk,
    DepotFile,
    DepotManifest,
    parse_manifest,
    process_chunk,
)
from pysteam.client import PICSInfo, SteamClient
from pysteam.errors import (
    AuthenticationError,
    CDNError,
    CDNHTTPError,
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
    "AuthSession",
    "AuthTokens",
    "AuthenticationClient",
    "AuthenticationError",
    "CDNClient",
    "CDNError",
    "CDNHTTPError",
    "DepotChunk",
    "DepotFile",
    "DepotManifest",
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
