"""Capture the upstream issue inventory. Refresh is a deliberate online operation."""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "issue-audit.json"
REPOS = ("ValvePython/steam", "SteamRE/SteamKit")

# The triage decision applies to the first-release API, not to the upstream project.
VALVE = {
    493: ("unknown", "unverified", "Report has no actionable title; request reproduction", None),
    489: (
        "SteamID",
        "covered",
        "Python 3.14 import warning",
        "tests/test_protocol.py::test_steamid_and_guard_regressions",
    ),
    485: (
        "CDN manifest",
        "covered",
        "Encrypted filename retains a trailing NUL",
        "tests/test_cdn.py::test_manifest_filename_and_path_regressions",
    ),
    481: ("unknown", "unverified", "Report has no actionable title; request reproduction", None),
    478: ("social messaging", "later", "Group messages are outside first-release scope", None),
    474: (
        "PICS",
        "live_pending",
        "Anonymous CM session times out on PICS",
        "tests/test_client.py::test_um_job_correlation_and_pics_response",
    ),
    473: (
        "CDN authentication",
        "live_pending",
        "Legacy CDN auth request receives no reply",
        "tests/test_cdn.py::test_cdn_auth_um",
    ),
    468: ("legacy WebAuth", "later", "Legacy MobileWebAuth is excluded", None),
    467: ("social", "later", "Recent players are outside first-release scope", None),
    462: ("appcache", "later", "Local appinfo.vdf parsing is excluded", None),
    458: (
        "Game Coordinator",
        "live_pending",
        "GC connection fails after protocol changes",
        "tests/test_client.py::test_gc_send_receive",
    ),
    456: ("legacy WebAuth", "later", "Legacy WebAuth is excluded", None),
    452: ("legacy WebAuth", "later", "Legacy web session API is excluded", None),
    451: (
        "legacy WebAuth",
        "later",
        "Report concerns cli_login transfer_parameters, which is excluded",
        None,
    ),
    450: (
        "authentication",
        "live_pending",
        "Session breaks after Steam update",
        "tests/test_http_auth.py::test_credential_auth_challenge_request",
    ),
    448: (
        "authentication",
        "live_pending",
        "Persistent login breaks",
        "tests/test_http_auth.py::test_credential_auth_challenge_request",
    ),
    442: ("legacy WebAuth", "later", "Legacy MobileWebAuth is excluded", None),
    439: ("legacy machine auth", "later", "Machine-auth handler is excluded", None),
    436: ("CDN branch selection", "later", "First release accepts explicit manifest IDs", None),
    429: ("authenticator management", "later", "Adding authenticators is excluded", None),
    427: ("social messaging", "later", "Chat is outside first-release scope", None),
    424: ("matchmaking", "later", "ServerRules is outside first-release scope", None),
    422: (
        "authentication",
        "live_pending",
        "Login fails after Steam service changes",
        "tests/test_http_auth.py::test_credential_auth_challenge_request",
    ),
    420: ("authenticator management", "later", "Authenticator management is excluded", None),
    389: ("profile management", "later", "Profile editing is excluded", None),
    378: ("legacy implementation", "later", "Legacy code path is not retained", None),
    377: ("typing", "covered", "Type annotation request", "uv run mypy"),
    360: ("SteamID niche", "later", "CSGO invite codes are excluded", None),
    357: (
        "authenticator management",
        "later",
        "Authenticator management is excluded; shared errors retain EResult",
        None,
    ),
    355: ("game metadata", "later", "GameData/GameTags API is excluded", None),
    350: ("social presence", "later", "Rich presence is excluded", None),
    349: ("authenticator management", "later", "Authenticator management is excluded", None),
    316: ("legacy WebAuth", "later", "Legacy CLI login is excluded", None),
    285: ("auth tickets", "later", "Auth ticket API is excluded", None),
    273: ("test infrastructure", "later", "Legacy test-suite proposal", None),
    272: (
        "SteamID",
        "covered",
        "Ambiguous invalid SteamID conversion",
        "tests/test_protocol.py::test_steamid_and_guard_regressions",
    ),
    264: ("CDN cache", "later", "OpenCache support is excluded", None),
    114: (
        "CM transport",
        "covered",
        "WebSocket backend request",
        "tests/test_client.py::test_um_job_correlation_and_pics_response",
    ),
    97: ("gevent TLS", "later", "gevent transport is excluded", None),
    49: ("examples", "covered", "Documentation examples requested", "docs/examples.md"),
    47: ("groups", "later", "Group API is excluded", None),
    13: ("chat", "later", "Chat API is excluded", None),
}

STEAMKIT = {
    1648: (
        "encrypted TCP transport",
        "later",
        "Concurrent EnvelopeEncryptedConnection crypto is specific to excluded TCP transport",
        None,
    ),
    1646: ("other language", "later", "Go port is outside Python SDK scope", None),
    1466: (".NET build", "later", "AOT is outside Python SDK scope", None),
    1460: (
        "CM discovery",
        "live_pending",
        "SmartCMList reconnect behavior",
        "tests/test_client.py::test_malformed_cm_packet_fails_pending_request",
    ),
    1438: ("UM via WebAPI", "later", "UM WebAPI transport is excluded", None),
    1434: (
        "WebAPI typing",
        "covered",
        "Dynamic WebAPI result shapes",
        "tests/test_http_auth.py::test_webapi_result_and_key_redaction",
    ),
    1418: ("NetHook", "later", "NetHook is outside SDK scope", None),
    1365: ("NetHook", "later", "NetHook is outside SDK scope", None),
    1343: ("schema maintenance", "later", "Upstream protobuf naming issue", None),
    1289: ("KeyValues", "later", "KeyValues parser is excluded", None),
    1175: ("NetHook", "later", "NetHook is outside SDK scope", None),
    1127: ("NetHook", "later", "NetHook is outside SDK scope", None),
    1118: ("UGC", "later", "UGC is excluded", None),
    1101: (
        "CM transport",
        "covered",
        "Sending while disconnected should fail",
        "tests/test_client.py::test_send_without_connection",
    ),
    1057: (".NET build", "later", "Trimming annotations are outside Python SDK scope", None),
    1054: (
        "CM transport",
        "later",
        "SteamKit connectionSetupTask cleanup is implementation-specific",
        None,
    ),
    1005: ("TCP transport", "later", "TCP is excluded from first release", None),
    1001: (
        "CM discovery",
        "covered",
        "CM server unavailable during PICS should be surfaced and rotated",
        "tests/test_client.py::test_cm_server_unavailable_event",
    ),
    993: (
        "WebAPI",
        "covered",
        "Missing default HTTP timeout",
        "tests/test_http_auth.py::test_webapi_result_and_key_redaction",
    ),
    940: ("schema packaging", "later", "Game-specific schema split is excluded", None),
    863: ("Steam realms", "later", "Alternate realms are excluded", None),
    786: (
        "CM transport",
        "covered",
        "Handler exception silently disconnects",
        "tests/test_client.py::test_malformed_cm_packet_fails_pending_request",
    ),
    778: (
        "WebAPI",
        "covered",
        "HTTP error body distinguishes WebAPI failures",
        "tests/test_http_auth.py::test_webapi_typed_response_and_http_error_body",
    ),
    711: ("social", "later", "SteamFriends is excluded", None),
    665: ("TCP transport", "later", "TCP is excluded from first release", None),
    636: (".NET logging", "later", ".NET logging change is outside Python SDK scope", None),
    561: ("social", "later", "Steam chat is excluded", None),
    514: ("test infrastructure", "covered", "Coverage request", "uv run pytest"),
    424: (
        "test infrastructure",
        "covered",
        "Testability request",
        "tests/test_client.py::test_um_job_correlation_and_pics_response",
    ),
    325: (
        "async transport",
        "covered",
        "Async network methods",
        "tests/test_client.py::test_um_job_correlation_and_pics_response",
    ),
    266: ("GC optimization", "later", "Preallocated GC body is excluded", None),
    258: ("KeyValues", "later", "KeyValues parser is excluded", None),
    191: ("documentation", "covered", "Source documentation request", "docs/examples.md"),
    171: (
        "CM jobs",
        "covered",
        "Destination job failure is not surfaced",
        "tests/test_client.py::test_destination_job_failure",
    ),
    158: ("social", "later", "SteamFriends is excluded", None),
    92: ("UGC", "later", "UGC is excluded", None),
}

CLOSED_REVIEW = {
    "ValvePython/steam": [408, 417, 388, 338, 315, 291],
    "SteamRE/SteamKit": [455, 496, 901, 1216, 40, 1345, 1197, 555, 528],
}

CLOSED_TRIAGE = {
    ("ValvePython/steam", 408): (
        "authentication",
        "Legacy login failure after protocol change",
        "live_pending",
        "scripts/smoke_live.py --i-control-account",
    ),
    ("ValvePython/steam", 417): (
        "CM concurrency",
        "Concurrent legacy calls timed out",
        "covered",
        "tests/test_client.py::test_um_job_correlation_and_pics_response",
    ),
    ("ValvePython/steam", 388): (
        "CM/PICS",
        "Repeated anonymous product-info bootstrap failed",
        "covered",
        "scripts/smoke_live.py --anonymous",
    ),
    ("ValvePython/steam", 338): (
        "authentication errors",
        "Rate limit was misreported as bad credentials",
        "covered",
        "tests/test_http_auth.py::test_auth_result_code_preserved",
    ),
    ("ValvePython/steam", 315): (
        "legacy WebAuth",
        "Legacy cli_login rejected valid credentials",
        "later",
        None,
    ),
    ("ValvePython/steam", 291): (
        "CDN caching",
        "Legacy manifest cache could remain stale",
        "covered",
        "tests/test_cdn.py::test_manifest_refetch",
    ),
    ("SteamRE/SteamKit", 455): (
        "CM WebSocket",
        "WebSocket connection failure had unclear propagation",
        "covered",
        "tests/test_client.py::test_websocket_connect_failure",
    ),
    ("SteamRE/SteamKit", 496): (
        "CM reconnect",
        "Repeated non-user disconnects",
        "covered",
        "tests/test_client.py::test_reconnect_restores_session_and_cancellation_cleans_job",
    ),
    ("SteamRE/SteamKit", 901): (
        "CM jobs",
        "Timed-out PICS waiter remained subscribed",
        "covered",
        "tests/test_client.py::test_request_timeout_removes_waiter",
    ),
    ("SteamRE/SteamKit", 1216): (
        "CDN manifest",
        "Manifest request received HTTP 401",
        "live_pending",
        "scripts/smoke_live.py --i-control-account",
    ),
    ("SteamRE/SteamKit", 40): (
        "CDN manifest",
        "Binary manifest format was replaced by protobuf",
        "covered",
        "tests/test_cdn.py::test_manifest_filename_and_path_regressions",
    ),
    ("SteamRE/SteamKit", 1345): (
        "authentication",
        "Valid password returned InvalidPassword",
        "live_pending",
        "scripts/smoke_live.py --i-control-account",
    ),
    ("SteamRE/SteamKit", 1197): (
        "legacy login key",
        "LoginKey callback did not arrive",
        "later",
        None,
    ),
    ("SteamRE/SteamKit", 555): (
        "Steam Guard",
        "Sample Guard login failed after restart",
        "live_pending",
        "docs/release.md",
    ),
    ("SteamRE/SteamKit", 528): (
        "CM reconnect",
        "Connect could silently do nothing after disconnect",
        "covered",
        "tests/test_client.py::test_reconnect_restores_session_and_cancellation_cleans_job",
    ),
}


def fetch(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "pysteam-issue-audit"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def snapshot() -> dict[str, Any]:
    entries = []
    for repo in REPOS:
        triage = VALVE if repo == REPOS[0] else STEAMKIT
        page = 1
        seen: set[int] = set()
        while True:
            batch = fetch(
                f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}"
            )
            for issue in batch:
                if "pull_request" in issue:
                    continue
                number = issue["number"]
                if number not in triage:
                    raise RuntimeError(f"New issue requires triage: {repo}#{number}")
                seen.add(number)
                capability, disposition, evidence, regression = triage[number]
                entries.append(
                    {
                        "source": repo,
                        "number": number,
                        "url": issue["html_url"],
                        "title": issue["title"],
                        "state": "open",
                        "capability": capability,
                        "reproduction_evidence": evidence + "; see source report",
                        "disposition": disposition,
                        "regression_test": regression,
                        "independently_reproduced": False,
                    }
                )
            if len(batch) < 100:
                break
            page += 1
        if seen != set(triage):
            raise RuntimeError(
                f"Triage table has stale issue numbers for {repo}: {set(triage) - seen}"
            )
        for number in CLOSED_REVIEW[repo]:
            issue = fetch(f"https://api.github.com/repos/{repo}/issues/{number}")
            if issue["state"] != "closed":
                raise RuntimeError(f"Historical issue changed state: {repo}#{number}")
            capability, evidence, disposition, regression = CLOSED_TRIAGE[(repo, number)]
            entries.append(
                {
                    "source": repo,
                    "number": number,
                    "url": issue["html_url"],
                    "title": issue["title"],
                    "state": "closed",
                    "capability": capability,
                    "reproduction_evidence": evidence + "; see source report",
                    "disposition": disposition,
                    "regression_test": regression,
                    "independently_reproduced": False,
                }
            )
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "scope": (
            "All open issues in both source projects at capture time, "
            "plus selected relevant closed reports"
        ),
        "entries": entries,
    }


def check() -> None:
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    required = {
        "source",
        "number",
        "url",
        "title",
        "state",
        "capability",
        "reproduction_evidence",
        "disposition",
        "regression_test",
        "independently_reproduced",
    }
    entries = data["entries"]
    if any(not required <= set(item) for item in entries):
        raise RuntimeError("issue audit has incomplete entries")
    for item in entries:
        regression = item["regression_test"]
        if not regression or regression.startswith("uv run "):
            continue
        path_text, separator, case = regression.partition("::")
        path = ROOT / path_text.split(" ", 1)[0]
        if not path.is_file():
            raise RuntimeError(f"missing issue regression artifact: {regression}")
        if separator and f"def {case}(" not in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"missing issue regression test: {regression}")
    for repo, triage in ((REPOS[0], VALVE), (REPOS[1], STEAMKIT)):
        open_numbers = {
            item["number"] for item in entries if item["source"] == repo and item["state"] == "open"
        }
        if open_numbers != set(triage):
            raise RuntimeError(f"issue audit inventory is incomplete for {repo}")
    print(f"Validated {len(entries)} issue audit entries")


def retriage() -> None:
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    for item in data["entries"]:
        if item["state"] == "open":
            triage = VALVE if item["source"] == REPOS[0] else STEAMKIT
            capability, disposition, evidence, regression = triage[item["number"]]
        else:
            capability, evidence, disposition, regression = CLOSED_TRIAGE[
                (item["source"], item["number"])
            ]
        item.update(
            capability=capability,
            disposition=disposition,
            reproduction_evidence=evidence + "; see source report",
            regression_test=regression,
        )
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh", action="store_true", help="Fetch current GitHub issue snapshot"
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate the committed offline snapshot"
    )
    parser.add_argument("--retriage", action="store_true", help="Apply updated triage offline")
    options = parser.parse_args()
    if options.refresh:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if options.retriage:
        retriage()
    if options.check or not (options.refresh or options.retriage):
        check()
