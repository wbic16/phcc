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
  Section = file, path-sorted; `tools/**` → Book 10 Chapter 9,
  `README.md` → Book 10 Chapter 1) and regenerates the placement
  manifest. One placement lives outside Source: `docs/**` → the
  Docs phase (Collection 9, Volume 2, Book 1 Chapter 1, Section =
  file) — tree documentation sits in the phase the 6D UML model
  reserves for it. Files are enumerated by
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

## analyze — duplication census + automatic de-duplication

```sh
phcc analyze --phext phcc.phext [--out REPORT]
phcc analyze --phext phcc.phext --apply --out dedup.phext [--report R]
```

`phcc` routes `analyze` to `phcc_analyze.py`. The census is
read-only, in two tiers:

- **EXACT** — cluster by payload SHA-256, at two granularities:
  Volume 3 segment payloads (the importer's per-member hashes are
  reused from the file indexes — the same identification rule as
  unpack's vol3 route — and verified against recomputation; a
  mismatch is reported in the census and makes `--apply` refuse),
  and whole scrolls for every scroll that is not a Volume 3
  segment/index. Bytes duplicated in a cluster of n copies of size
  s is (n−1)·s. Whole-scroll clusters are split into *manifest-file
  clusters* (apply can rewrite them) and *census-only* clusters
  (Volume 1 history, Tests placements, registers — no expansion
  path exists, so they are reported, never rewritten).
- **NEAR** (report-only) — for Source members (segment kinds
  function / type / object), a normalized hash: C comments stripped
  by a string/char-aware scanner, whitespace collapsed. A NEAR
  cluster claims *identical after normalization* and nothing more;
  this tier is never applied.

`--apply` writes a NEW phext (the input is never modified) in which,
per exact cluster, the lowest-coordinate member stays canonical and
every other member's body is replaced by a **dedup stub** — exactly
one line, `#phcc-dedup-ref <coordinate> <sha256>`, naming the
canonical scroll and the SHA-256 of the bytes it stands for (for a
segment target, the payload's hash — the value the file index
records). Only two classes are rewritten, because those are the two
`phcc unpack` can expand: Volume 3 segment payloads (the
`#phcc-member` header line and the segment's address are kept
byte-exact) and Volume 2 whole-file scrolls named by the placement
manifest. `unpack` expands stubs automatically on both routes
(vol2, vol3 segments, and the vol3 bridge): the target must exist,
must not itself be a stub (chains are never written and never
followed), and must hash to the stub's SHA-256 — then the ordinary
manifest/index verification runs on the expanded bytes, so a
deduplicated phext unpacks under exactly the same rules as a plain
one. Apply is idempotent: stubs are references, not content, and a
second apply writes zero stubs and byte-identical output.

Excluded from de-duplication everywhere: Library-10000 build-region
scrolls and binary-format scrolls (artifacts, already canonical
base64 — the census tallies them, and notes duplicate groups among
binary scrolls, but never clusters them for rewriting), and
zero-byte payloads (a stub is larger than the payload).

Measured on the canonical corpus (2026-11-07), so the economics
are on the record: the stub line costs ~103 bytes, and Volume 3's
duplicated payloads are mostly micro-payloads (whitespace gaps,
one-line declarations — 164,432 duplicated bytes across 1,444
clusters, mean stubbed payload ~9 bytes). Full stubbing therefore
*grows* this phext by 1,594,735 bytes (+2.5%): 132 of 17,549
segment stubs save bytes (net +7,660), the rest are provenance,
not compression. The corpus's real duplicated bytes live in the
whole-scroll tier — 837,713 bytes (837,665 of them census-only),
dominated by the Volume 1 slurp re-holding placed files. Read
`analyze`
as an audit instrument first and a rewriting instrument second;
any future byte win is a size threshold on apply, not a different
mechanism.

**Safety law.** A rewrite is never silent about bindings. The
segment/file hashes a rewrite changes are scanned against every
scroll in the phext, and the apply report lists as
**DEMOTED-TO-STALE** every binding the rewrite invalidates: gate
verdicts and Proofs-collection receipts whose text names a changed
hash, Design views that bind a changed hash or derive from a
touched file, and the current gate verdict in any case (it binds
the Volume 3 members digest of the whole phext). Demotion is the
tier system's designed response to a source edit — receipts and
views are listed, never edited, and read STALE until their own pass
re-issues them. Scrolls that merely *mention* a changed hash
without asserting a binding are listed separately, as mentions.

## analyze — statement tier: statement-level de-duplication as a native expression

    phcc analyze --phext X.phext --statements [--out REPORT]
    phcc analyze --phext X.phext --build-stmt --out Y.phext [--report R]
    phcc analyze --phext Y.phext --verify-stmt [--out REPORT]

The member-stub de-duplication above is bounded by byte economics
(a stub costs ~103 B against ~9 B mean payloads). The statement
tier is the phext-native expression of the same fact, with the
file framing removed: segment payloads are split at STATEMENT
grain, each distinct statement is held exactly once in a
statement library, and each member scroll expresses its payload
as an ordered sequence of coordinate references. Files survive
only as the unpack export view. The metrics are structural —
instances vs distinct (the ratio), reference integrity, lossless
round-trip — never byte break-even.

**Splitter.** `split_segments` cuts a payload into
(indent, core, terminator) triples: after `;` at paren depth 0
("semi"), after `{` ("open"), after `}` ("close", merging a
following `;` across whitespace only — "close-semi"), each
preprocessor line as one segment ("pp", backslash continuations
respected; a chunk ended by an intervening directive is a
"split"), the remainder a "tail". String/char literals and
comments are consumed atom-aware (structural characters inside
them are content); semicolons inside parentheses never cut (the
for-header rule); paren depth is clamped at 0 so fragment
payloads still segment. **Partition invariant: indent + core
concatenation reproduces the payload byte-for-byte, always** —
the expression is lossless for any payload, C or not. Known
limits: initializer lists are single segments (commas never
cut); a label binds to the statement it prefixes (colons never
cut); a do-while tail `while (x);` is its own "semi" segment;
trigraphs are not honoured. Statement identity is the exact core
bytes — the payload minus its leading whitespace, which is
positional and travels in the reference.

**Reference sequence format** (phext_io, exact-match grammar).
A rewritten member payload is the member header line, then
`#phcc-stmt-seq 1\n`, then one line per segment:
`#phcc-stmt-ref <coordinate> <sha256-of-core> <indent-hex>\n`,
or `#phcc-stmt-ref EMPTY <indent-hex>\n` for a whitespace-only
segment. A payload that opens with the magic but does not parse
in full is corruption, never a plain payload; unpack expands
references through `phcc_migrate.resolve_stmt_seq`, verifying
each target against the reference's recorded SHA-256.

**Coordinates — found, not assigned.** A statement's address is
a function of its own bytes: Library 20000, the eight remaining
components are SHA-256(core) digest bytes 0–7 mod 5 + 1, and
collisions probe forward deterministically in digest order as a
base-5 counter. The component base is a measured walk-cost
decision: the first build used mod 99 and materialized
15,341,147 empty scrolls (15.3 MB of delimiters, ~90 s
verification walk) around 66,272 statements; mod 5 (390,625
cells) materializes 108,452 and verifies in ~8 s, keeping every
address corpus-independent. A register scroll at Meta
1.1.1/1.2.10/1.23.1 (placement-manifest book, Section 23)
records the layout, source SHA-256, counts and derivation.

**Census of the canonical corpus** (50,285 payloads, partition
invariant holds on every one): 134,780 statement instances,
66,272 distinct (exact) — **ratio 2.03×**; 62,541 distinct under
NEAR normalization (2.16× headroom). Per group: win32 headers
59,963/25,356 (2.36×), compiler core 33,275/19,710 (1.69×),
tests 16,763/9,444, backends 1.62–1.74× each. The most-repeated
statements are structural (`}` ×8,662, `#endif` ×2,568,
`break;` ×1,093). **The block census contradicts the natural
guess**: the top repeated blocks (≥3 statements) are brace
closers, preprocessor guards and win32 struct-field runs — not
hoistable code; only 17 blocks in compiler .c files carry ≥2
executable statements at ≥6 occurrences, the best saving 36 of
134,780 references (0.03%). The repeated mass lives in single
statements, so factoring is prototyped at that grain (below).

**Proofs on the built expression** (`phcc-stmt.phext`,
75,227,453 B, beside the canonical phext): (a) all 134,780
references resolve and hash-verify, and all 50,285 expanded
payloads match their file-index SHA-256; (b) `unpack --from
vol3` reproduces the original 558-file tree byte-for-byte
(manifest hash columns identical); (c) the statement library
holds 66,272 scrolls with 66,272 distinct contents, exactly the
set the references name — each distinct statement held exactly
once. Exercised end-to-end (plus splitter/grammar unit cases) by
`tools/test_stmt.py`, 32 checks.

**The floor this flexes on.** Older toolchains de-duplicate at
function/section grain at finest, and leave no artifact:
measured on a program whose six functions share one identical
6-statement block but differ in their return value, GNU gold
`--icf=all` folds only the byte-identical control pair (37 B of
text) and all six block copies survive; GNU bfd ld does not
accept `--icf` at all; MSVC `/OPT:ICF` is the same function
grain by documentation; compiler CSE works within one function
at IR level and leaves nothing inspectable. The statement
expression of the same program holds the block's statements
once each (77 instances / 41 distinct), capturing within- and
cross-function repetition below that floor, as a durable,
hash-verified artifact.

| toolchain | finest dedup grain | inspectable artifact |
|---|---|---|
| GNU ld (bfd) | none (no ICF) | — |
| GNU gold / lld `--icf=all` | identical function/section | link map only |
| MSVC `/OPT:ICF` | identical function (COMDAT) | link map only |
| gcc/clang CSE | expression, within one function, IR only | none |
| phcc statement expression | statement, within + across functions | the phext itself, hash-verified |

**Factoring prototype (census-scoped).** The dominant
*executable* cluster is the tccpp.c scroll-break tail —
`file->line_num = 1; tok_flags |= TOK_FLAG_BOL; p++;
tok = TOK_SCROLL_BREAK;` — at all nine phext-break cases of
`next_nomacro`, each ending `goto keep_tok_flags;`. Hoisted
into a static helper (the goto stays at each site; control flow
cannot be called), measured .text effect on tccpp.o: phcc
48,514 → 48,065 B (−449, −0.93%), gcc -O0 39,192 → 38,913
(−279), gcc -O2 unchanged (the optimizer already absorbs it).
The factored tree passes `make test` in full. A measurement,
not a shipped codegen change: at statement grain the
*expression* is the factoring — the object-level effect is real
only where codegen is unoptimised, which is precisely phcc's
own regime.

## prune — member-graph pruning (the -O2 ladder, rung A)

`phcc prune --phext X.phext --out Y.phext --harvest H.json` emits a
pruned phext for one build configuration. Tools-side only: no
compiler source is touched and no PATCHES entry is created; the
prune is a statement about a *configuration* (a harvest of one
build), never about the project in the abstract. The harvest
(`nm -A` over a built tree's objects and archives, objects mapped
to sources) is the compiler's own knowledge of what the link
needed, and it is the ground truth throughout:

- **Graph.** Nodes are Volume 3 members of *graph files* —
  compiled sources, archive-constituent sources (including
  archive members with no loose object: their stems resolve
  against the carried set and their undefineds join the model),
  and the `#include` closure over them — quoted includes, plus
  angle includes the configured build graph vouches for (the
  target resolves to exactly one carried file that is a
  build prerequisite: gnulib's `<libc-config.h>` is real;
  textually present but `#ifdef`-gated includes like
  `<windows.h>` in a Linux build are not followed). Edges follow raw
  identifier tokens in payloads (comments, string literals, asm
  operands and macro bodies included — the safe direction), with
  two fallbacks for identifiers no member is named by: a provider
  index over type members' payloads (enum enumerators —
  `ERROR_WARN`, the `TCC_OPTION_*` table), and a suffix index over
  member names for paste families (`ELFW(R_INFO)` → `ELF64_R_INFO`).
- **Roots.** Definers of `main`; definers of exactly the symbols
  the replayed link closure demands (seed = every non-archive
  object's undefineds; archive members pulled as the linker pulls
  them; a pulled object's *undemanded* globals are not rooted —
  they are the pruning frontier); members carrying
  `__attribute__((constructor|destructor|used))`; every member of
  a token-table file (`*-tok.h`, `tcctok.h` — positional
  enumerator factories whose names are manufactured by pasting);
  every member carrying an `#if`-family/`#endif` line (conditional
  halves may live in different members); members named in ambient
  text (keep-whole bytes and gap payloads); the paste net
  (name-as-substring survivors); `--root` extras.
- **File classes.** Keep-whole wins over graph membership
  (a compiled test program is a test input, not pruning surface);
  the runtime-prefix files the build did not compile are the
  compiler's runtime-source surface and stay; uncompiled source
  files drop whole — unless the build references them, in two
  tiers: reachable as a prerequisite from the default goal in
  the configured build's own dependency graph (the harvest's
  `make -qp` database — generation templates live here:
  coreutils' `lib/arpa_inet.in.h`, from which `arpa/inet.h` is
  generated; unreachable rules, emitted for unconfigured
  objects, do not rescue), or named by basename in a kept
  build-instruction file (the Makefile names `conftest.c`).
  A path-qualified text scan is deliberately not a tier:
  template files name every file that could build under any
  configuration. The keep sets are
  per-project parameters (`--keep-prefixes`, `--keep-files`,
  `--runtime-prefix`); coreutils, whose recipe builds neither its
  tests nor a runtime surface, passes them empty and prunes at
  whole-file grain.
- **Emission.** Volume 1 verbatim; kept files byte-verbatim;
  graph files with drops re-tiled at member grain (spans and
  segment headers rewritten, payload hashes unchanged); the
  placement manifest rewritten for the pruned set; a **prune
  manifest** at Meta 1.1.1/1.2.10/2.1.1 records the base phext's
  SHA-256, the configuration, counts, and the full auditable
  dropped list (files, members with spans and payload hashes,
  build-referenced keeps, archive pull results, closure-forced
  keeps). Derived phases (Design/Tests/Proofs collections, gate
  verdicts) are *not* carried: their hash bindings name the
  unpruned source set. The emitted phext must pass the loader's
  full verification before it replaces the output path.
- **Validation.** After reachability, every undefined symbol of
  every harvested source must still have a kept definer; a miss
  force-keeps the definer, is recorded, and reachability resumes.
  The receipts loop — prune → unpack → build → test — is the
  outer gate: each failure class it exposed (enumerators,
  build-referenced files, positional token tables, paste
  suffixes, conditional halves) is now a root rule above and a
  case in `tools/test_prune.py`.

Receipts (2026-11-08, base = published tip 36a7932f, configuration
= default host build + test suite, harvest from a gcc build):
phcc's own carry — 612 files → 516 kept / 96 dropped whole;
50,683 member rows → 2,031 dropped (4.0%); closure-forced keeps 0.
Source volumes 22,243,000 → 10,258,757 bytes (Vol 2
5,688,686 → 4,022,493; Vol 3 16,554,314 → 6,236,264).
The pruned tree builds clean and passes `make test` in full; the
pruned-built compiler rebuilds the pruned tree (stage 2) and the
stage-2 compiler's output on the differential workload is
identical to the unpruned compiler's (whose emitted workload
binary is in fact byte-identical to the pruned compiler's).
Conformance corpus under both compilers: 330/333 with the
identical diverge set [a_pp_018, b_gnu_015, b_gnu_016], 0/333
per-probe differences. Source volumes: the honest deltas are in
the prune report; the total phext delta additionally reflects the
omitted derived phases and must not be quoted as the pruning win.

Second subject (phccbox's bundle unit, coreutils 9.12, carried
whole-file since it has no Volume 3 segmentation): 3,848 files
carried → 3,495 kept / 353 dropped whole (254 gnulib lib, 39 gl,
46 gnulib-tests, 14 src — uncompiled modules and unconfigured
SIMD variants); source bytes 53,503,476 → 51,781,301. The pruned
carry builds with the same recipe, and in a same-directory A/B
the single-binary `coreutils`, `libstdbuf.so`, and the localized
phccbox bundle object are byte-identical to the unpruned carry's;
a 17-applet smoke run is identical. (The box binary is
build-path-sensitive, so the A/B shares one build directory.
47 tree files — the info manual and .gmo catalogs — contain phext
delimiter bytes and cannot ride a text carry at this tip.)

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
- **phext → statement phext → tree: identity.**
  `analyze --build-stmt` rewrites every member payload as a
  statement reference sequence; unpack of the statement phext
  reproduces the original 558-file tree byte-for-byte, and
  `analyze --verify-stmt` proves every reference hash-verified
  and each distinct statement held exactly once (see the
  statement-tier section).
- **phext → dedup phext → tree: identity.** `analyze --apply` is
  lossless by construction and by proof: unpack of the deduplicated
  phext (both routes) reproduces the original tree byte-for-byte,
  a census of the deduplicated phext reports zero exact clusters in
  both rewritten classes, and re-packing the expanded tree
  re-segments to the same member hashes. The end-to-end behaviour
  (planted duplicates of every class, the demote list, the refusal
  on unverifiable index hashes) is exercised by
  `tools/test_analyze.py`.

Placement completion (2026-11-07): the placement table predated F2
and the seal, and a whole-tree pack of the current tree aborted on
13 unplaceable paths. It now covers the whole tree: 603 files
placed — the 558 above plus `README.md`, the three `docs/**`
guides (Docs phase), and the files DevUX added under `examples/**`
and `tools/**` — with whole-tree pack + both unpack routes
re-verified at 603/603 byte-identical. The recorded exclusions are
exactly: `phcc.phext`, `phcc.phext.xz`, `phcc-manifest.tsv` (when
present), and the eight `phext/**` paths (next paragraph).

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
Volume 1), `phcc.phext.xz` (the generated seal *of* the phext —
produced from it by `phcc seal`, never packed into it),
`phcc-manifest.tsv` (unpack's own output, regenerated every run),
`.git` — and the whole of `phext/**`. The C parity library already
lives at Source Book 10 Chapter 10 under the builds pass's Sec-14
placement addendum (Meta Sec 14); pack's path-sort sectioning would
renumber `phext.c`/`phext.h` off the addendum's Sections 1–2 and
split each across two addresses at the next merge, so the directory
is carried by the addendum as one component. (One member,
`phext/tests/regression-1-helios.phext`, could not be a scroll
anyway: it is a phext file, and its bytes are delimiters.) Every
exclusion is recorded in the packed manifest, per file, with its
reason.

## Lineage of the code

- Byte format (`phext_io.py`): unchanged from the Slice 0/1 tools.
- unpack vol2: adapted from Slice 0 `export_phcc.py`.
- unpack vol3: adapted from importer v4 `reassemble.py`.
- pack stage A: adapted from Slice 0 `import_phcc.py` (placement
  table verbatim; tree enumeration generalised beyond git;
  `tools/**` placement added; `README.md` + `docs/**` placements
  and the seal + `phext/**` named exclusions added 2026-11-07).
- pack stage B: importers v3/v4 (`import_fn.py`, `import_v4.py`)
  run unmodified.
- analyze (`phcc_analyze.py`, 2026-11-07): new module; the dedup
  stub format lives in `phext_io.py` as a marked extension (the
  byte format's first addition since Slice 1), and unpack's stub
  expansion lives in `phcc_migrate.py`'s two routes, sharing
  `resolve_stub`. Segment identification is the vol3 route's rule,
  restated in the analyzer so both tools mean the same segments.
