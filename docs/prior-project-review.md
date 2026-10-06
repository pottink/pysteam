# Review of earlier Steam projects

Reviewed on 2026-10-01 against local revisions:

- `Q:\dev\steam` (`caf73a6`): a ValvePython fork with WebSocket CM support,
  updated PICS messages, app/package access-token requests, and text/binary
  VDF decoding.
- `Q:\dev\steamctl` (`474fa41`): an application using that fork to fetch
  product info, select depot manifests, request manifest codes, and decrypt
  filenames. Its `sopel/default.cfg` had existing local changes and was not
  modified during this review.

The reusable gap was PICS metadata discovery. `steamctl` reads a branch's
manifest as a `gid` object, matching the modern app 570 response observed in
an anonymous live check. `pysteam` now requests PICS access tokens, parses
bounded text app-info VDF, and extracts both modern `gid` objects and older
scalar manifest IDs. It also forwards the selected branch and password hash
when requesting a CDN manifest code. The live check returned 19 public
manifest references for app 570 and an app access token response.

The old fork's gevent transport, WebAuth API, and application storage are not
part of the new SDK. `steamctl`'s fixed Windows/English depot filtering,
MongoDB/Redis caches, key persistence, and downloader orchestration are
application choices. The SDK keeps manifest selection explicit by app,
depot, and branch, with no implicit platform filter. Saved accounts use a
secret-free profile registry and per-account encrypted stores rather than
`steamctl`'s account database.
