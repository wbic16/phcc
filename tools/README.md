# phcc tooling

Tools for the phcc modernization programme: TinyCC carried in a
phext, with structure, generated Design views, proofs and a
report-only trace gate bound to the code at its own addresses.

## phcc.phext (repo root)

The canonical merged phext, 2026-11-07:

- SHA-256: `646144c7afd7e39d485dec02b7e4ab58e5adda0b9bcbe24abba886d662b6c275`
- bytes: 49,209,925 · scrolls: 52,815
- gate v5 verdict scroll (Meta, Vol 2, Book 10, Sec 12):
  SHA-256 `be476b923a5042cf709cbc23ba3dc4a43b3760b785729ac6cc126501f059680b`,
  byte-reproducible by re-running the gate (see below).

Lineage (full record inside the phext at Meta 1.1.1/1.2.10/1.11.1):
the consolidation of lineage A — Slice 0 Volumes 1/2 plus the
Slice 1–4 phases (Tests, Design, Regressions, Proofs placements,
preprocessor machine) — with lineage B's Volume 3, the importer-v4
member refinement (32,933 members: 7,626 functions, 2,427 types,
22,880 objects; every importer-v3 member kept its exact address
and payload). On top of that base, the two sibling lines were
merged (2026-11-07): Slice 5's value-stack machine (design §A.3
machine #2 — machine scroll at tccgen.c's Design address, 26 trace
tests, 5 sourced regressions, gate v5 register at Meta Sec 13 and
verdict at Sec 12; 34 scrolls added) and the hardened Slice 2 proof
receipts (four Proofs scrolls transplanted from the hardened
lineage: WP partial 271/297 VCs discharged, __moddi3 fully
discharged, T3 not granted, receipts hash-current in the gate).
Merge accounting vs the consolidated base: exactly those 34
additions + 4 changed scrolls; every other scroll byte-identical.
Volume 1 is the 2024 monolith slurp, byte-verbatim
(319/319 scrolls at the same coordinates) — the old standalone
`monolith.phext` was a proof-of-concept and is not a build input;
building phcc is `./configure && make && make test` on the plain
source tree.

## The tools

| file | what it does |
|---|---|
| `phext_io.py` | Byte-exact phext read/write helpers (walk/implode, coordinate format, SHA-256). Everything else imports this. Stdlib only. |
| `import_fn.py` | Importer v3: tree-sitter segmentation of the source tree into Volume 3 member scrolls (functions / types / objects + gap segments, index-authoritative order). |
| `import_v4.py` | Importer v4: v3 + bare-specifier and `extern "C"` linkage-block classification; a refinement of v3's Volume 3, never a re-placement. Needs tree-sitter (the granularity venv) and `import_fn.py` beside it. |
| `reassemble.py` | Exit test: rebuilds all 558 files from Volume 3 segments (bridge scrolls for file-level files) and byte-compares against the Slice 0 manifest. Writes the tree for a ranch build. |
| `extract_design.py` | Slice 3 generator: derives the Design-phase Scroll-1 views from Volume 3 members (never re-parses files), binds each view to its Source SHA-256 + members digest, places the §A.2 pipeline view and the Design register. |
| `check_pipeline.py` | Verifies the pipeline view's machine-checked names/edges block against the extractor-derived call graph. |
| `check_machine.py` | Slice 4 static conformance (level 1) for the preprocessor conditional-stack machine scroll: events resolve to real Vol 3 `def` members of tccpp.c, guard vocabulary resolves to real state. |
| `trace_model.py` | Independent Python model of the preprocessor machine, used by the trace tests. |
| `run_trace_tests.py` | Slice 4 dynamic conformance (level 2): authored trace tests + the tests/pp corpus against a built `tcc -E`, model paths validated against the machine scroll's transitions. |
| `phcc_gate.py` | The trace gate, v4.0.0, REPORT-ONLY (it never blocks): per-Book phase coverage, receipt-driven tiers (T3 only on full WP discharge with current hashes; CBMC bounded = T2), Design-view staleness, machine conformance. `--verdict-out` writes its verdict scroll into a phext copy; re-running it on a phext that carries the verdict reproduces the verdict byte-identically. |
| `consolidate.py` | The 2026-11-07 lineage consolidation, stage 1: merges A-phases + B-Vol 3 with a full scroll-set diff proof against both inputs. |
| `compare_views.py` | Consolidation stage 2 audit: classifies every regenerated Design view (byte-identical / own members changed / universe growth only). |
| `add_provenance.py` | Consolidation stage 3: places the consolidation provenance scroll (Meta, Vol 2, Book 10, Sec 11) and verifies it is the only diff. |
| `phcc` | The migration interface (below): `phcc unpack` / `phcc pack`. Thin dispatcher over `phcc_migrate.py`. |
| `phcc_migrate.py` | Migration engine: unpack verifies every file's SHA-256 against the in-phext manifest before writing (Volume 2 scrolls, or Volume 3 segment reassembly); pack = stage A placement (adapted from the Slice 0 importer) + importers v3/v4 run unmodified for Volume 3. |

## Migration: phext ⇄ directory tree

Two commands move the whole project between its one-file form and a
normal directory tree — byte-exact, or it fails loudly:

```sh
tools/phcc unpack --phext phcc.phext --out tree/ [--from vol2|vol3] [--force]
tools/phcc pack   --tree tree/ --out phcc.phext [--base previous.phext]
```

- `unpack` materialises the 558 files of the in-phext placement
  manifest, each SHA-256-verified before it is written (exit 1, the
  file withheld, on any mismatch). `--from vol2` reads each file's
  whole-bytes Source scroll; `--from vol3` reassembles structured
  files from their Volume 3 member+gap segments (file-level files
  ride the Volume 2 bridge). It writes `phcc-manifest.tsv` into the
  tree as the verification record.
- `pack` rebuilds the phext from a tree: stage A places Volume 2 by
  the Slice 0 §1 Books (plus `tools/**` at Book 10 Ch 9) and takes
  Volume 1 verbatim from the tree's `monolith.phext` or the `--base`
  phext; stage B runs importers v3/v4 for Volume 3 (needs a Python
  with tree-sitter: `--ts-python` or `$PHCC_TS_PYTHON`).

Round trips are proven on this corpus: tree→phext→tree is the
identity for all 558 files, and phext→tree→phext reproduces
every content scroll byte-identically (Volume 1 319/319, Volume 2
559/559, Volume 3 50,816/50,816). What a pack does not carry — the
derived phases (Design views, Tests placements, Proofs, the gate
verdict) and Meta provenance — and why that is correct: see
[`tools/METHODS.md`](METHODS.md).

## Quick checks

```sh
tools/phcc unpack --phext phcc.phext --out /tmp/tree          # verified tree
tools/phcc unpack --phext phcc.phext --out /tmp/tree3 --from vol3
tools/phcc pack --tree /tmp/tree --base phcc.phext --out /tmp/repacked.phext
python3 tools/phcc_gate.py phcc.phext                 # report tables
python3 tools/phcc_gate.py phcc.phext --verdict-out /tmp/check.phext
sha256sum /tmp/check.phext   # == phcc.phext if the verdict is current
python3 tools/check_machine.py phcc.phext
python3 tools/check_pipeline.py phcc.phext
python3 tools/reassemble.py --phext phcc.phext --out /tmp/tree
```
