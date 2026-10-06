# Content preservation references

Reviewed 2026-10-01. These are behavior and format references; the new
implementation in `src/pysteam` was written independently.

| Project | Pinned revision | License | Relevant behavior |
| --- | --- | --- | --- |
| [steamarchiver](https://github.com/benjamin-lowry/steamarchiver/tree/f5e5acd229c44bd0859bc8d6817849f59a66d160) | `f5e5acd229c44bd0859bc8d6817849f59a66d160` | Apache-2.0 | SHA-named encrypted chunks, zipped original manifests, PICS appinfo, client updates, CSM/CSD/SIS backups. |
| [steamarchiver_python](https://github.com/Dimensional/steamarchiver_python/tree/8cd7e679ebb6f00ca1f4b902472d55349d8e5145) | `8cd7e679ebb6f00ca1f4b902472d55349d8e5145` | Apache-2.0 | Workshop and backup workflow variants. |
| [DepotDownloader](https://github.com/SteamRE/DepotDownloader/tree/989f37b1fbc012798bf41bdf0e66a60adf785ae5) | `989f37b1fbc012798bf41bdf0e66a60adf785ae5` | GPL-2.0 | Bounded concurrent downloads, file filters, update verification, server failover, SteamPipe Workshop manifests. |

The [SteamTracking protobuf snapshot](../vendor/steam-protobufs/steam) is the
wire-schema source. `scripts/generate_protos.py` reproducibly generates its
selected Python classes. `steammessages_publishedfile.steamclient.proto` was
added to the generated subset for Workshop queries and details.

The CSM index format is `SCFS`, a 20-byte header and 36-byte chunk entries
(SHA-1, CSD offset, reserved field, length). SIS is text VDF referencing
depot IDs, manifest IDs, and CSM/CSD containers. The importer validates
offsets, lengths, identities, encrypted chunks, and complete files against
the original depot manifest before marking an archive complete.

No source code was copied from the reference projects. In particular,
DepotDownloader's GPL implementation is not translated into this MIT package.
