# PATCHES.md — divergence from TinyCC upstream

phcc is a fork of TinyCC (https://repo.or.cz/tinycc.git). This file is
the per-file record of what changed since the fork. It was started
2026-11-24 with the distributed-compile change; the fork's earlier
divergence (the phext rework, monolith.phext, and the v1.0 programme)
predates this file and is recorded in the repository history and
monolith.phext. Entries below are complete for the change that
introduced them.

## 2026-11-24 — distributed compilation (branch emise/distributed-compile)

New files only; no upstream TinyCC file is modified by this change.

- `DISTRIBUTED.md` (new) — design note for the distributed compile
  protocol: hash-pinned work units, untrusted carrier nodes, verified
  objects, no silent local fallback.
- `dist/phccd.c` (new) — the compile worker: libtcc linked in,
  SHA-256 unit-identity verification on receipt, fork-per-connection
  TCP server, object cache keyed by unit hash.
- `dist/phcc-dist.py` (new) — the driver: preprocesses translation
  units locally, computes unit identities, dispatches units across
  workers, verifies returned object hashes, optionally verifies
  byte-identity against local compiles (`--verify-local`).
- `dist/build-worker.sh` (new) — builds `phccd` as a static binary
  against the tree's `libtcc.a`.
- `dist/start-worker.sh` (new) — node-side starter script for the
  worker (deployed with the binary, not run from the repo).
- `PATCHES.md` (new) — this file.
