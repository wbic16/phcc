# phcc tools

Everything here operates on one file: `phcc.phext`, the whole project
in a single phext (see `phcc_gate.py` verdicts inside it for its own
account of itself).

**Current canonical phext (grand merge, 2026-11-07):**
`phcc.phext` — 56,240,584 bytes, 62,896 scrolls,
SHA-256 `84303a47dbf2fc367c9cd2eaa47f05791f4be1006b4ff7f3674d5f71278b5734`.
Sealed form `phcc.phext.xz` — 5,771,928 bytes,
SHA-256 `560637a52fe35185ce12e1847fd955da3c81ecd37b7d5ad884b08c209978e9ca`.
Gate verdict: Meta `1.1.1/1.2.10/1.19.1` (gate v8.0.0),
SHA-256 `390b28031afdc19dac15f7a3e1d66d0c9c5a19252b5532f7257277ab797d5020`.
Lineage: canonical base `646144c7…` + Slice 6 (linker machine) +
Slice 7 (register-allocation machine) + builds-aligned (assembly
listings + Library-10000 build region), merged by scrolls; the full
account is in the merge register at Meta Sec 18 and in
`~/workspace/phcc-final/REPORT.md`.

## The interface

    phcc unpack --phext X.phext --out DIR [--from vol2|vol3] [--force]
    phcc pack   --tree DIR --out Y.phext [--base Z.phext]
                [--no-vol3] [--ts-python PY]
    phcc build-region list --phext X.phext
    phcc build-region wipe --phext X.phext --out Y.phext [--force]
    phcc seal   --phext X.phext [--out X.phext.xz] [--force]
    phcc unseal --sealed X.phext.xz [--out X.phext] [--force]

- `phcc` is a thin dispatcher: `unpack`/`pack` route to
  `phcc_migrate.py`; `build-region`/`seal`/`unseal` route to
  `phcc_builds.py`. `phext_io.py` is the shared byte-exact phext
  reader/writer.
- `phcc_gate.py` is the report-only trace gate (**v8.0.0, the grand
  merge**): coverage, tiers, proof receipts (271/297 VCs, no STALE),
  Design staleness (351/351 current), machine conformance #1
  (preprocessor), #2 (value stack), #3 (linker symbol resolution),
  #4 (register allocation), and the generated-assembly section. It
  never blocks; it reports. Run it as
  `python3 tools/phcc_gate.py phcc.phext [--verdict-out OUT.phext]`.
  `check_machine.py` / `check_vstack.py` / `check_linker.py` /
  `check_regalloc.py` are its live static checkers and must sit
  beside it.
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

The sibling verdicts (Slice 6's at its Sec 14, the builds verdict
at its Sec 16, Slice 7's at its Sec 17) were not carried into the
merged file; their SHA-256s are folded into the Sec 18 register so
the record survives without importing a verdict that describes a
different phext.
