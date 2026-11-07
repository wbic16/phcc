# PATCHES.md — phcc fork delta over upstream TinyCC

phcc is Will Bickford's fork of TinyCC, reworked around phext.
This file is the complete per-file record of how phcc diverges from
upstream, per fork-patch discipline: the delta must always be enumerable
from this file alone.

## Current base (after Slice 0 rebase, 2026-11-07)

- Upstream: TinyCC (github.com/TinyCC/tinycc), commit
  `c638ddfb593214813aa33536fb993b9a45d23793` (2026-11-06, "tccgen: reject
  pointer/function-pointer to floating-point conversions"; tree VERSION
  0.9.28rc upstream, carried as 1.0.0 by the fork — see VERSION below).
- Pre-rebase history (2022-04-01 upstream snapshot + the four original
  2024 fork commits) is preserved on branch `emise/pre-slice0-2026-11-07`.
- The four fork commits were replayed in order onto the new base:
  slurp script (3d60c327), Forking to v1.0 (c48d59ef), phext support
  (6f7b4f57), monolith update (dceabf44).
- Total delta vs upstream base: 9 files (plus this file), +108,508 /
  −5 lines, of which `monolith.phext` alone is +108,291.

## Per-file delta

| File | Δ vs upstream | What and why |
|---|---|---|
| `monolith.phext` | new, +108,291 lines | The 2024 flat slurp: one scroll per source file at 1.1.1/1.1.1/1.1.N, index scroll first, produced by `slurp.sh`. Preserved verbatim; in the Slice 0 phext it lives on as Volume 1. It is *not* placed in Volume 2 of that phext (its own bytes are phext delimiters — a phext cannot byte-exactly contain itself as a scroll). |
| `slurp.sh` | new, +53 | "Phext Slurper v1.0" — the 2024 generator of the monolith. Historical; superseded by importer v2 (Slice 0) but kept for provenance. (Mode 100644, as committed in 2024.) |
| `.gitignore` | +1 | One added ignore line (`.slurp*`) for slurper scratch files. |
| `slurp`-era versioning: `VERSION` | 1 line changed | Upstream `VERSION` (0.9.28rc) set to `1.0.0` — the fork's version identity from commit "Forking to v1.0". See rebase resolution R3. |
| `Changelog` | +7 | Fork's "Version 1.0.0" entry (phext input support) prepended ahead of upstream's 0.9.28 section. See R1. |
| `RELICENSING` | +1 | Adds "Will Bickford — YES — Phext Support" to the relicensing consent list. See R2. |
| `tcc.h` | +39 / −3 | Phext support core declarations (from c27c095): `IO_BUF_SIZE` 8192 → 32768; `BufferedFile` gains nine phext position counters (scroll … library); `TCCState` gains nine matching totals; nine `TOK_*_BREAK` token defines for the phext delimiters (scroll 0x17 … library 0x01); `TCC_STATE_VAR` accessors for the nine totals. |
| `tccpp.c` | +109 / −1 | Phext support in the preprocessor: consumes the nine phext break tokens while reading input and maintains the per-file counters / state totals declared in `tcc.h`. |
| `libtcc.c` | +6 | `tcc_print_stats` also prints the nine phext totals (scrolls … libraries) — re-expressed in upstream's current `#`-prefixed stats format during the rebase. See R6. |

## Rebase resolution log (Slice 0, 2026-11-07)

The 2024 delta was written against a 2022-04-01 upstream snapshot.
Replaying it onto c638ddf produced conflicts in two commits; every
resolution below is minimal (upstream's current form wins on style and
structure; the fork's intent is carried, never dropped silently).

- **R1 — Changelog (content conflict, "Forking to v1.0").** Upstream had
  since written the full 0.9.28 section where the fork's 1.0.0 entry
  landed. Resolution: both kept — fork's 1.0.0 entry first, then
  upstream's 0.9.28 section, then prior history.
- **R2 — RELICENSING (content conflict, same commit).** Upstream added
  three consent names (Reimar Döffinger, noneofyourbusiness, Cyan
  Ogilvie) at the fork's edit point. Resolution: upstream's names kept,
  Will Bickford's line appended after them.
- **R3 — VERSION.txt (modify/delete, same commit).** Upstream renamed
  `VERSION.txt` → `VERSION`. The fork's edit set the version to 1.0.0.
  Resolution: `VERSION.txt` deleted with upstream; the fork's `1.0.0`
  written into `VERSION` (keeping upstream's no-trailing-newline style).
- **R4 — meson.build (modify/delete, same commit).** Upstream removed
  the Meson build entirely; the fork's only meson change was the same
  1.0.0 version bump. Resolution: deletion accepted — the bump is moot
  without the file; version identity is carried by `VERSION` (R3).
- **R5 — tcc.h (content conflict, "Working on phext support").** In
  `TCCState`'s benchmark-info block, upstream changed `total_bytes` to
  `unsigned int` and `total_output[3]` → `total_output[4]`. Resolution:
  upstream's types kept; the fork's nine phext totals inserted above
  them as `int`, as originally written.
- **R6 — libtcc.c (content conflict, same commit).** Upstream reworked
  `tcc_print_stats` ( `#`-prefixed format, `%u` bytes, removed the
  `total_bytes` clamp). The fork added three phext stat lines in the old
  `*` format plus the clamp. Resolution: upstream's format and clamp
  removal kept; the fork's three phext lines re-expressed in the `#`
  format and inserted between the idents line and the timing line. The
  argument list (which had auto-merged) supplies the nine totals.
- **R7 — tccpp.c (same commit)** auto-merged with no manual resolution;
  verified post-rebase: the break-token handling and counters are intact
  (110-line delta replays as +109/−1 against the new base).

## Maintenance rule

Every future phcc change lands as: (1) a commit, (2) a row or edit in
this file in the same commit, (3) on upstream sync, a rebase (never a
merge) with conflicts resolved under the R1–R7 principle and logged here.
