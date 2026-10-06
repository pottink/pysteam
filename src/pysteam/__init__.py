"""Modern async Steam SDK."""

from pysteam.accounts.auth import (
    AccessTokenResult,
    AuthenticationClient,
    AuthenticationInteractionRequired,
    AuthSession,
    AuthTokens,
    GuardChallenge,
    GuardChallengeHandler,
    LoginResult,
)
from pysteam.accounts.credentials import (
    CredentialStore,
    EncryptedFileCredentialStore,
    LoginCredentials,
)
from pysteam.accounts.enrollment import GuardEnrollmentClient, PendingGuardEnrollment
from pysteam.accounts.guard import confirmation_key, guard_code
from pysteam.accounts.mafile import ImportedAuthenticator, load_mafile
from pysteam.accounts.profiles import ProfileRegistry, SavedProfile, default_profile_dir
from pysteam.accounts.vault import Vault
from pysteam.client import PICSInfo, SteamClient
from pysteam.content.archive import (
    ArchiveRecord,
    ArchiveResult,
    ArchiveStore,
    ContentArchiver,
    ManifestDiff,
    WorkshopArchiveResult,
)
from pysteam.content.cdn import (
    CDNClient,
    DepotChunk,
    DepotFile,
    DepotManifest,
    parse_manifest,
    process_chunk,
)
from pysteam.content.client_packages import (
    ClientArchiveResult,
    ClientPackage,
    ClientPackageArchiver,
)
from pysteam.content.pics import PICSAccessTokens, extract_manifest_ids, parse_app_vdf, parse_vdf
from pysteam.content.workshop import WorkshopClient, WorkshopItem, WorkshopQuery
from pysteam.errors import (
    AuthenticationError,
    CDNError,
    CDNHTTPError,
    CredentialStoreError,
    EnrollmentError,
    MaFileError,
    ProfileError,
    ProtocolError,
    RequestTimeout,
    SteamError,
    SteamResultError,
    TransportError,
    WebAPIError,
)
from pysteam.ids import SteamID
from pysteam.webapi import WebAPIClient

__version__ = "0.1.0a0"

__all__ = [
    "AccessTokenResult",
    "ArchiveRecord",
    "ArchiveResult",
    "ArchiveStore",
    "AuthSession",
    "AuthTokens",
    "AuthenticationClient",
    "AuthenticationError",
    "AuthenticationInteractionRequired",
    "CDNClient",
    "CDNError",
    "CDNHTTPError",
    "ClientArchiveResult",
    "ClientPackage",
    "ClientPackageArchiver",
    "ContentArchiver",
    "CredentialStore",
    "CredentialStoreError",
    "DepotChunk",
    "DepotFile",
    "DepotManifest",
    "EncryptedFileCredentialStore",
    "EnrollmentError",
    "GuardChallenge",
    "GuardChallengeHandler",
    "GuardEnrollmentClient",
    "ImportedAuthenticator",
    "LoginCredentials",
    "LoginResult",
    "MaFileError",
    "ManifestDiff",
    "PICSAccessTokens",
    "PICSInfo",
    "PendingGuardEnrollment",
    "ProfileError",
    "ProfileRegistry",
    "ProtocolError",
    "RequestTimeout",
    "SavedProfile",
    "SteamClient",
    "SteamError",
    "SteamID",
    "SteamResultError",
    "TransportError",
    "Vault",
    "WebAPIClient",
    "WebAPIError",
    "WorkshopArchiveResult",
    "WorkshopClient",
    "WorkshopItem",
    "WorkshopQuery",
    "confirmation_key",
    "default_profile_dir",
    "extract_manifest_ids",
    "guard_code",
    "load_mafile",
    "parse_app_vdf",
    "parse_manifest",
    "parse_vdf",
    "process_chunk",
]
