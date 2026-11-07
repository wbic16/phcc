# phcc tooling

Tools for the phcc modernization programme: TinyCC carried in a
phext, with structure, generated Design views, proofs and a
report-only trace gate bound to the code at its own addresses.

## phcc.phext (repo root)

The canonical consolidated phext, 2026-11-07:

- SHA-256: `61638c143338ad942783a11141a0f1be3f66e522d4a15880b8301d2afbaa1b4f`
- bytes: 43,975,346 · scrolls: 52,781
- gate v4 verdict scroll (Meta, Vol 2, Book 10, Sec 9):
  SHA-256 `47b7b8be8fea46c79f62370248647f6be7faf6aa947c2f636476a6e24c9e51d8`,
  byte-reproducible by re-running the gate (see below).

Lineage (full record inside the phext at Meta 1.1.1/1.2.10/1.11.1):
the consolidation of lineage A — Slice 0 Volumes 1/2 plus the
Slice 1–4 phases (Tests, Design, Regressions, Proofs placements,
preprocessor machine) — with lineage B's Volume 3, the importer-v4
member refinement (32,933 members: 7,626 functions, 2,427 types,
22,880 objects; every importer-v3 member kept its exact address
and payload). Volume 1 is the 2024 monolith slurp, byte-verbatim
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

## Quick checks

```sh
python3 tools/phcc_gate.py phcc.phext                 # report tables
python3 tools/phcc_gate.py phcc.phext --verdict-out /tmp/check.phext
sha256sum /tmp/check.phext   # == phcc.phext if the verdict is current
python3 tools/check_machine.py phcc.phext
python3 tools/check_pipeline.py phcc.phext
python3 tools/reassemble.py --phext phcc.phext --out /tmp/tree
```
