# phcc tools

Everything here operates on one file: `phcc.phext`, the whole project
in a single phext (see `phcc_gate.py` verdicts inside it for its own
account of itself).

**Current canonical phext (F1 receipt re-issue, 2026-11-07):**
`phcc.phext` — 63,195,664 bytes, 63,640 scrolls,
SHA-256 `82bd0745e2dc6b1320e9c00865200ec8cca6accd14689585d7168b48300c1f21`.
Sealed form `phcc.phext.xz` — 5,883,468 bytes,
SHA-256 `ffadce9bf7f56a0d9f534fd7767bb928454e695097ff5c2e27232faea042ad4e`.
Gate verdict: Meta `1.1.1/1.2.10/1.20.1` (gate v8.1.0),
SHA-256 `e32b9ee9b2939dd22ee5eeb176e7e8522228f000c170901dacd45a036bb10ec1`.
Lineage: canonical base `646144c7…` + Slice 6 (linker machine) +
Slice 7 (register-allocation machine) + builds-aligned (assembly
listings + Library-10000 build region), merged by scrolls into the
grand-merge phext (`84303a47…`, gate v8.0.0); then the F5 attribute
fix refresh (fixed tccpp.c/tccgen.c sources, conformance corpus at
Tests Book 11, gate v8.1.0), the catch-up (five drifted files —
Makefile, PATCHES.md, lib/libtcc1.c, libtcc.c, tcc.h — refreshed to
the repo tree), and this re-issue: lib/libtcc1.c at its repo F1
bytes with all three proof receipts re-issued against that source
(WP counts reproduced exactly, 271/297, per function), the phext.c/h
Sec-14 addendum at F4 bytes, and all build artifacts rebuilt. The
libtcc1.c hold recorded at Meta Sec 22 is CLOSED by this re-issue.
A fresh unpack of this phext is byte-identical to the repo tree at
the F5 commit across all 558 files, and `make test` passes from the
carried tree.

## The interface

    phcc unpack --phext X.phext --out DIR [--from vol2|vol3] [--force]
    phcc pack   --tree DIR --out Y.phext [--base Z.phext]
                [--no-vol3] [--ts-python PY]
    phcc analyze --phext X.phext [--out REPORT]
    phcc analyze --phext X.phext --apply --out Y.phext [--report R]
    phcc build-region list --phext X.phext
    phcc build-region wipe --phext X.phext --out Y.phext [--force]
    phcc seal   --phext X.phext [--out X.phext.xz] [--force]
    phcc unseal --sealed X.phext.xz [--out X.phext] [--force]

- `phcc` is a thin dispatcher: `unpack`/`pack` route to
  `phcc_migrate.py`; `analyze` routes to `phcc_analyze.py` (the
  duplication census, and with `--apply` automatic de-duplication
  into dedup stubs that `unpack` expands — receipt bindings a
  rewrite invalidates are reported DEMOTED-TO-STALE, never silently
  rewritten; `tools/test_analyze.py` is its end-to-end self-check);
  `build-region`/`seal`/`unseal` route to `phcc_builds.py`.
  `phext_io.py` is the shared byte-exact phext reader/writer.
- `phcc_gate.py` is the report-only trace gate (**v8.1.0**): the
  v8.0.0 sections (coverage, tiers, proof receipts — 271/297 VCs,
  re-issued against the F1 libtcc1.c source, no STALE; Design
  staleness 351/351 current; machine conformance #1 preprocessor,
  #2 value stack, #3 linker symbol resolution, #4 register
  allocation; generated assembly) plus the report-only conformance
  section (328/333 probes three-way, 0 unclassified, 0 class-(a)
  open; MSVC: MANUAL — NOT ATTESTED, a manual attestation that is
  Will Bickford's act at merge, never an automated run). It never
  blocks; it reports. Run it as
  `python3 tools/phcc_gate.py phcc.phext [--verdict-out OUT.phext]`.
  `check_machine.py` / `check_vstack.py` / `check_linker.py` /
  `check_regalloc.py` are its live static checkers and must sit
  beside it. `verify_gate_splice_81.py` proves every pre-existing
  section function is byte-identical to gate v8.0.0's.
- `build_reissue.py` / `assemble_reissue.py` / `segment_libtcc1.py`
  are the pipeline that produced this re-issue (Vol 3 re-segmentation
  of libtcc1.c, receipt re-issue assembly); `acceptance_local.py`
  is the local acceptance harness (unpack → tree-identity → build →
  test).
- `METHODS.md` states the migration invariants: what a pack/unpack
  round trip preserves byte-for-byte, what it does not (derived
  phases regenerate through their own passes), and the failure
  behaviour.

## Working file plain, seal for storage/publish (the rule)

The WORKING phext is always plain text — every tool above reads and
writes the plain form, and the gate's verdicts bind to it. The xz
seal (`phcc seal`, xz -9 / CRC64) is the persistence and publish
form only: seal the finished plain phext, store/publish the
`.phext.xz`, unseal to work on it again. `unseal(seal(x))` is
byte-identical to `x`. Never edit, gate, or pack from the sealed
form directly — unseal first. (Will's rulings, 2026-11-04 +
2026-11-07.)

## The build region (Library 10000)

Binary build artifacts (objects, archives) live inside the phext in
a wipeable region rooted at `10000.1.1/1.1.1/1.1.1` (the region
manifest). A binary scroll mirrors its origin artifact's Source
address under Library 10000:

    (10000, 1, 1, 4, V, B, Ch, Sec, slot)
    slot 1 = x86_64 object     slot 3 = x86_64 archive
    slot 2 = arm64 object      slot 4 = arm64 archive

Each binary scroll is in the canonical libphext binary format: the
header line `phext-binary:1:base64`, a newline, then the raw binary
as RFC 4648 base64 (standard alphabet, padding required, no line
wrapping). Canonical scrolls carry no provenance — artifact,
origin, kind, target, format, compiler provenance, raw size, and
raw SHA-256 live in the region manifest's entry lines at the root;
decoders verify the decoded bytes against the manifest entry.

`phcc build-region wipe` removes exactly the Library-10000 scrolls.
Generated assembly listings (Design phase, at each artifact's
address) are NOT in the region: they are persistent, hash-bound to
their Source scroll, their compiler commit, and their region
object — after a wipe they read CURRENT with the object noted
absent, by design. Binaries are ephemeral; listings and their
provenance are the record.

Two honest costs of the region's address, recorded so nobody is
surprised: reaching Library 10000 materializes ~10k empty scrolls
in any reader that enumerates coordinates (9,998 across libraries
2..9999 on the climb, a handful more inside the region) — zero
bytes of content, ~10 KB of delimiter bytes in the file — and a
phext whose last scroll is empty loses it to the walker's
trailing-empty convention on reload (a wiped file reads back one
empty climb scroll short; nothing with content is ever lost). Both
are properties of the format, not defects of the tooling; the
gate's checked-scroll list shows the empties like any other scroll.

## Meta section map (Volume 2, Book 10, Ch 1 — the merged lineage)

    Sec 1   Slice 0 placement manifest
    Sec 2   layout notes (Slice 0)
    Sec 3   Slice 1 test placement register
    Sec 4   gate verdict — Slice 1        Sec 5   gate verdict — Slice 2
    Sec 6   Proofs register               Sec 7   gate verdict — Slice 3
    Sec 8   Design register               Sec 9   gate verdict — Slice 4
    Sec 10  machine register #1 (preprocessor, Slice 4)
    Sec 11  consolidation provenance
    Sec 12  gate verdict — Slice 5
    Sec 13  machine register #2 (value stack, Slice 5)
    Sec 14  builds placement addendum (phext/** -> Book 10 Ch 10)
    Sec 15  build register (assembly listings + region provenance)
    Sec 16  machine register #4 (register allocation, Slice 7)
    Sec 17  machine register #3 (linker, Slice 6) — relocated from
            Sec 15 in its home lineage, where it collided with the
            build register; content byte-identical
    Sec 18  merged register (grand-merge lineage + donor accounting)
    Sec 19  gate verdict — grand merge (gate v8.0.0)
    Sec 20  gate verdict — F5 refresh + F1 re-issue (gate v8.1.0)
    Sec 21  conformance register (Book 11 corpus + receipts pointer)
    Sec 22  catch-up / re-issue register (libtcc1.c hold CLOSED)

The sibling verdicts (Slice 6's at its Sec 14, the builds verdict
at its Sec 16, Slice 7's at its Sec 17) were not carried into the
merged file; their SHA-256s are folded into the Sec 18 register so
the record survives without importing a verdict that describes a
different phext.
