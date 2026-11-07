# phcc migration methods — phext ⇄ directory tree

Two commands move the whole project between its one-file phext form
and a normal directory tree:

```sh
phcc unpack --phext phcc.phext --out tree/ [--from vol2|vol3] [--force]
phcc pack   --tree tree/ --out phcc.phext [--base previous.phext]
            [--no-vol3] [--ts-python PY]
```

`phcc` is a thin dispatcher (tools/phcc) over the engine
(tools/phcc_migrate.py, usable directly with subcommands `export` /
`import`). Everything is byte-exact or it fails loudly — there is no
lossy mode.

## unpack — phext → tree

Reads the placement manifest stored inside the phext (Collection 1 /
Meta, Volume 2, Book 10: path → coordinate, SHA-256, size, git mode)
and materialises exactly those 558 files, restoring git modes.

- `--from vol2` (default): each file is its Volume 2 Source scroll,
  whole bytes at the file's address.
- `--from vol3`: each structured file is reassembled from its
  Volume 3 member+gap segment scrolls (index-authoritative order;
  the Volume 2 scroll is never consulted for structured files);
  file-level files (no index — recorded in the degradation register)
  fall back to the Volume 2 bridge scroll.

Every file's bytes are SHA-256-verified against the manifest (and,
under vol3, every segment payload against its index entry, with span
tiling checked) **before** it is written. A mismatch means that file
is not written, the failure is listed, and the exit code is 1.
unpack also writes `phcc-manifest.tsv` into the tree (path, SHA-256,
size, mode, route taken) as the run's verification record. It refuses
a non-empty target directory unless `--force` is given (exit 2).

## pack — tree → phext

- **Stage A** (in the engine): Volume 1 + Volume 2. Volume 1 is the
  2024 flat slurp, copied verbatim from the tree's `monolith.phext`
  if present, else inherited from `--base` (a previous phext); with
  neither, pack aborts. Volume 2 places every file by the established
  placement (Slice 0 §1 Books: Book = module, Chapter = component,
  Section = file, path-sorted; `tools/**` → Book 10 Chapter 9) and
  regenerates the placement manifest. Files are enumerated by
  `git ls-files` when the tree is a git work tree, else by directory
  walk (mode from the executable bit). A file no placement rule
  covers aborts the pack, by name — nothing is silently dropped.
- **Stage B** (reused, not rewritten): importer v3 (`import_fn.py`)
  segments each Volume 2 file into Volume 3 member scrolls
  (function / type / object members + gap segments tiling the file
  exactly), then importer v4 (`import_v4.py`) applies its
  classification refinement. These run as subprocesses and need a
  Python with `tree-sitter` + `tree-sitter-c` (`--ts-python`, or
  `$PHCC_TS_PYTHON`). `--no-vol3` stops after stage A.

Both stages fail (exit 1, nothing half-written to `--out`) on: a file
containing phext delimiter bytes (0x01, 0x17–0x1F set — such a file
cannot be a scroll byte-exactly), an unplaceable path, a missing
Volume 1 source, or a stage-B error.

## Round-trip invariants (proven on the canonical corpus)

- **tree → phext → tree: identity.** All 558 files byte-identical
  (diff -r clean; unpack manifests' hash columns identical), via
  both the vol2 and the vol3 unpack routes.
- **phext → tree → phext: identity on all content scrolls.** Of the
  canonical phext's 52,781 scrolls, the re-packed phext reproduces
  byte-identically: Volume 1 (319/319), all Volume 2 Source payloads
  (559/559), and the **entire Volume 3** (50,816/50,816 — every index
  scroll and every member payload). The segmentation is a fixed
  point of pack: unpack∘pack loses nothing the tree ever held.

## What is NOT preserved by a pack, and why that is correct

pack's input is a *tree*; the tree only ever contained the source.
Three classes of scrolls in the canonical phext therefore do not
come back:

1. **The other UML phases** — Requirements, Design (incl. the 629
   generated Design views and the preprocessor machine scroll),
   Tests placements, Regressions, Docs, Whitepapers, Training, and
   Proofs (Collections 2, 3, 5–10; 1,061 scrolls). These are derived
   or annotative layers that slice passes generate *against* a phext
   (the gate, the view extractor, the trace gate). They are rebuilt
   by re-running those passes on the packed phext, not carried by
   the tree. The gate's hash-binding makes this safe: a stale view
   or receipt reads STALE, never silently current.
2. **Meta provenance scrolls** (9 scrolls in Meta Volume 2 beyond
   the manifest and notes). Same reason: they record the history of
   passes run on the phext, not tree content.
3. **Three Meta scrolls differ in header lines only** — the
   placement manifest, its layout notes, and the Volume 3 rebind
   manifest. Their data rows are identical; the header lines name
   the producing tool and the base phext's hash, and provenance must
   tell the truth about its producer. A pack that forged the
   original headers would be lying about where the file came from.

Also never packed, by design: `monolith.phext` and `phcc.phext`
themselves (a phext's bytes *are* the delimiter set — a phext cannot
byte-exactly contain itself as a scroll; the monolith survives as
Volume 1), `phcc-manifest.tsv` (unpack's own output, regenerated
every run), and `.git`. Every exclusion is recorded in the packed
manifest.

## Lineage of the code

- Byte format (`phext_io.py`): unchanged from the Slice 0/1 tools.
- unpack vol2: adapted from Slice 0 `export_phcc.py`.
- unpack vol3: adapted from importer v4 `reassemble.py`.
- pack stage A: adapted from Slice 0 `import_phcc.py` (placement
  table verbatim; tree enumeration generalised beyond git;
  `tools/**` placement added).
- pack stage B: importers v3/v4 (`import_fn.py`, `import_v4.py`)
  run unmodified.
