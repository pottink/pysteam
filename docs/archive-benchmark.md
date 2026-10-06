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
