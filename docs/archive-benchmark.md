# Offline archive scheduler benchmark

Run: `uv run python scripts/benchmark_archive.py`

Measured on Windows with Python 3.13 on 2026-10-01. The fixture contains
64 unique 64 KiB chunks (4 MiB total), AES-encrypted ZIP payloads, a local
synthetic manifest, and 25 ms simulated CDN latency per chunk. Each mode
uses the same archive code and verifies the same data. `workers=1` is the
sequential baseline. The memory figure is peak Python allocations reported
by `tracemalloc`, not total process RSS.

| Download workers | Wall time | Throughput | CPU time | Peak Python heap |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 5.013 s | 0.80 MiB/s | 1.844 s | 1.26 MiB |
| 8 | 1.675 s | 2.39 MiB/s | 1.750 s | 2.30 MiB |
| 16 | 1.605 s | 2.50 MiB/s | 1.812 s | 3.98 MiB |

The gain is about 3.0× at eight workers and 3.1× at sixteen for this fixture.
Actual Steam CDN speed, CPU use, and memory depend on chunk size, server
latency, storage, and entitlement; this synthetic run is not a live download
smoke test.

## Live CDN comparison

Measured on Windows with Python 3.14 on 2026-10-06. Each run downloaded the
same current app 570 depot 373303 (192,837,504 encrypted bytes), using an
anonymous CM session and a locally supplied depot key. The machine's active
Ethernet link negotiated at 2.5 Gbps. Download-phase time starts before
manifest retrieval and ends when the last chunk is checked and stored; total
time includes the final full-depot verification. These are single-run local
measurements, except that the one-server case was repeated once.

| First-choice CDN servers | Download workers | CPU workers | Download phase | Effective archive input rate | Total time |
| --- | ---: | ---: | ---: | ---: | ---: |
| One server | 32 | 0 | 16.9 s | 11.4 MB/s | 23.6 s |
| One server, repeat | 32 | 0 | 16.2 s | 11.9 MB/s | 23.3 s |
| Spread across eight | 32 | 0 | 13.5 s | 14.3 MB/s | 20.4 s |
| Spread across eight | 32 | 4 | 13.6 s | 14.2 MB/s | 20.3 s |
| Spread across eight | 64 | 0 | 12.7 s | 15.2 MB/s | 19.0 s |

Spreading the workers' first requests across the eight returned servers helped
in this run. Four decoding processes did not help this depot. The effective
rate includes chunk decryption, checksum checks, and local writes; it is not
a direct measurement of the network interface. Another CDN region, route, or
machine may give different results.
