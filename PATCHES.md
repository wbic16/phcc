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
| `tcc.h` | +48 / −3 | Phext support core declarations (from c27c095; reworked by F3): `IO_BUF_SIZE` 8192 → 32768; `BufferedFile` gains a `phext_coordinate` — the phext library's coordinate type (F3 replaces the seed's nine int counters, which sat after `buffer[1]`, inside the region the input's own bytes are read into); `TCCState` gains nine totals (printed by `tcc_print_stats`; no code assigns them — as the seed left them); nine `TOK_*_BREAK` token defines for the phext delimiters (scroll 0x17 … library 0x01), their values taken from the library's `PHEXT_*_BREAK` constants since F3; `TCC_STATE_VAR` accessors for the nine totals; `#include "phext/phext.h"`. |
| `tccpp.c` | +91 / −4 | Phext support in the preprocessor: consumes the nine phext break tokens while reading input; since F3 the per-file position is advanced by the phext library's `phext_coordinate_*_break` functions instead of the seed's hand-rolled counter arithmetic. F5: the `__attribute__` keyword tokens are never macro-expanded (see F5). |
| `tccgen.c` | +148 / −1 | F5 (first fork change to this file): `packed` enum type selection, declarator/type-carried `aligned` resolution for struct fields, typedef-carried alignment in `_Alignof` type-ids. See F5. |
| `tccdbg.c` | +28 / −5 | F6 (first fork change to this file): an FDE's PC Begin offset travels in the `.eh_frame` relocation's addend on RELA targets (new `dwarf_reloca()`), not only in the field contents, so GNU ld accepts multi-function phcc objects. See F6. |
| `libtcc.c` | +24 | `tcc_print_stats` also prints the nine phext totals (scrolls … libraries) — re-expressed in upstream's current `#`-prefixed stats format during the rebase. See R6. Since F3, the `ONE_SOURCE` block also `#include`s `phext/phext.c` (last in the block, with `tcc.h`'s allocator poisons lifted around it) so amalgamated builds link the library. |
| `Makefile` | +10 | Phext library linkage (F3): in multi-object builds `phext/phext.c` compiles to `$(X)phext.o` and joins `LIBTCC_OBJ`; `ONE_SOURCE` builds get the same code via `libtcc.c`'s include instead. |
| `lib/libtcc1.c` | 2 lines changed | Cast the signed high word to `unsigned` before the left shift in `__ashrdi3` and `__lshrdi3` (C11 UB when the high word is negative). Correctness fix, not a phext feature; upstream-shaped and intended for upstream report once validated. See F1. |
| `phext/phext.h` | new, +397 | Public header for the phext developer library (F2): every type, constant, and function of the libphext-rs 0.4.1 parity surface, documented. C99, no dependencies beyond libc types. F4 adds the hash-index fields to `phext_scrolls`. |
| `phext/phext.c` | new, +2,031 | The library implementation (F2), including a scalar XXH3-128 port (from xxhash-rust's const implementation) for scroll checksums. Single translation unit. F4 adds the coordinate hash index behind `phext_map_get`. |
| `phext/PARITY.md` | new, +268 | The parity audit: all 77 libphext-rs capabilities mapped to their C counterparts, the idiom mapping, divergences D-2…D-6, and the conformance outcome. D-4 superseded annotation added by F4. |
| `phext/README.md` | new, +54 | Library overview, build/test instructions (including the phcc dogfood invocation), and the idiom-mapping summary. |
| `phext/tests/` | new, +2,042 | The conformance suite: `test_phext.c` (+1,853) — libphext-rs's own test_lib.rs / test_phokenize.rs / regressions.rs ported case-for-case; `Makefile` (+22); the two regression-1 fixtures (helios phext + message text, +167 lines between them). |

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

## Post-rebase fork changes

- **F1 — lib/libtcc1.c: unsigned cast before high-word left shift in
  `__ashrdi3` / `__lshrdi3` (2026-11-07).**
  - *File:* `lib/libtcc1.c`, the `__TINYC__` word-wise bodies of
    `__ashrdi3` and `__lshrdi3` (i386 runtime helpers).
  - *Change:* `u.s.high << (32 - b)` → `(unsigned)u.s.high << (32 - b)`
    in both functions (2 lines). `u.s.high` is `Wtype` = signed `int`;
    the composed low word needs only its bit pattern, which the
    unsigned shift supplies with defined behaviour. Matches the cast
    style already used by every other shift in these bodies and in
    `__ashldi3`.
  - *Reason:* by C11 §6.5.7p4, left-shifting a negative signed value
    is undefined behaviour. The branch runs whenever the 64-bit
    operand's high word is negative (any negative `__ashrdi3`
    operand; any `__lshrdi3` operand ≥ 2⁶³) and the shift count is
    1–31 — the common case, not an edge case.
  - *Evidence:* found by the Slice 2 Frama-C/WP pilot on this file —
    Z3 returned a countermodel (goal Failure, not timeout) for the
    `ensures` of both functions in the WP model
    (`wp-esc-__lshrdi3.log`, `wp-esc-__ashrdi3.log`, escalation run,
    Z3 4.8.12). `__ashldi3`, whose shifts are already cast, drew no
    countermodel and is unchanged. Validation (regression test,
    upstream suite, WP before/after) is recorded in
    `~/workspace/phcc-lshrdi3/REPORT.md`. Upstream report is prepared
    but deliberately not yet sent.

- **F2 — phext/: libphext-rs API-parity developer library (2026-11-07).**
  - *Files:* new top-level `phext/` directory — `phext.h`, `phext.c`,
    `PARITY.md`, `README.md`, and `tests/` (harness, Makefile, regression
    fixtures). Additive only: no existing compiler file is touched by
    this change (PATCHES.md itself aside).
  - *Change:* a C99 port of libphext-rs **v0.4.1** (`src/phext.rs`), so a
    C developer gets everything the Rust crate gives a Rust developer:
    9-dimensional coordinates (1-based, **no upper bound** — the 999 cap
    was removed upstream in 0.4.0), scroll fetch / insert / replace /
    remove, phokenize, explode / implode, merge / subtract, expand /
    contract, normalize, range replace, next_scroll iteration, textmap /
    navmap / manifest, index / offset, and XXH3-128 scroll checksums.
    The audit found **77 capabilities — 26 constants, 7 types, 17
    Coordinate-surface items, 27 free functions — and all 77 have C
    counterparts** (full matrix in `phext/PARITY.md`).
  - *Idioms and divergences:* Rust `String` → `phext_buffer` out-params;
    `HashMap` → coordinate-sorted `phext_scrolls` with
    `phext_map_get`/`phext_map_insert`; `Result`/panics → `phext_status`
    return codes, never UB on bad input. Recorded divergences: D-2 strict
    coordinate parse returns `PHEXT_EFORMAT`/`PHEXT_ENUMBER` where Rust's
    `TryFrom` panics on non-numeric/overflowing components; D-3 the C API
    is byte-oriented and does not validate UTF-8 (byte-identical on valid
    UTF-8); D-4 the map is sorted (Rust's is unordered; `implode` output
    identical); D-5 scroll-summary display truncation at byte 4; D-6 the
    lenient `to_coordinate` wraps on overflow like Rust release builds.
  - *Relation to the seed phext surface:* the preprocessor's nine break
    tokens and per-level counters (`tcc.h`/`tccpp.c`) are unchanged and
    stay independent. Wiring those counters to this library is a named
    follow-on (F3-candidate), deliberately not done here.
  - *Evidence:* libphext-rs's own tests ported to C with the same vectors
    and expected values (49 + 8 + 1 test functions): **163,831 checks, 0
    failures under gcc, and 163,831 checks, 0 failures compiled by the
    freshly built phcc itself** (aletheia-core; phcc's own `make test`
    also passes). Differential fuzz against a Rust reference driver on
    libphext-rs 0.4.1: **40,000 randomized cases, 0 divergences** on
    defined behaviour (the only Rust panics are the D-2 parse class).
    Run via `phext/tests/Makefile` (`make test`, or
    `make CC=../../tcc TCCFLAGS=-B../.. test` for the dogfood build).

- **F3 — the preprocessor's phext tracking runs on the phext library
  (2026-11-07).** The follow-on named in F2, landed.
  - *What the seed did (c27c095, 2024):* nine hand-rolled per-file
    counters (`BufferedFile.scroll_num` … `library_num`) and nine lexer
    cases in `next_nomacro1()` that increment one counter and reset the
    lower ones to 1 by hand; every break byte surfaces as the single
    `TOK_SCROLL_BREAK` token. Characterized before changing anything
    (behaviour corpus, below): the counters were **write-only** — no
    code reads them, and the nine `TCCState` totals printed by
    `tcc_print_stats` are never assigned anywhere (they print 0 on
    every compile; left exactly so here). The seed's observable
    behaviour is: (i) break bytes lex to `TOK_SCROLL_BREAK`, are echoed
    verbatim by `-E`, and are rejected by the parser in grammatical
    positions (`declaration expected`, `expression expected`);
    (ii) each break resets `line_num` to 1, visible in diagnostic line
    numbers; (iii) break bytes inside string/char literals and comments
    pass through byte-exact.
  - *Change:* `BufferedFile`'s nine counters become one
    `phext_coordinate`, advanced by the library's
    `phext_coordinate_*_break()` functions — whose transitions
    (increment own component, reset lowers to 1) are exactly the seed's,
    and whose all-zero start (`BufferedFile` is `tcc_mallocz`'d)
    reproduces the seed's numbering step for step. The `TOK_*_BREAK`
    defines take their values from the library's `PHEXT_*_BREAK`
    constants. `phext/phext.c` is linked into `libtcc`: a separate
    `$(X)phext.o` in multi-object builds (`Makefile`), and `#include`d
    at the **end** of `libtcc.c`'s `ONE_SOURCE` block in amalgamated
    builds — last so `tcc.h`'s `_GNU_SOURCE` define precedes its libc
    headers, with `tcc.h`'s allocator poisons
    (`free`/`malloc`/`realloc`/`strdup` → `use_tcc_*`) `#undef`'d for
    its body and restored verbatim after it (the library is an ordinary
    libc consumer; the poisons exist to catch core code calling libc
    allocation directly). The tree now carries one phext implementation.
  - *One deliberate layout repair, disclosed:* the seed's counters sat
    **after** `BufferedFile.buffer[1]` — inside the region the input
    file's own bytes are read into. A break firing before the read
    pointer passed the counter span (~40 bytes) wrote counter values
    into unconsumed input: e.g. a `LIBRARY` break at byte 15 of a file
    stomps the declarations that follow it (the seed's own `-E` echoes
    them as break bytes and errors out). F3 places `phext_coord`
    **before** `buffer[]`, out of the blast radius. On every input
    where the seed did not corrupt itself, behaviour is byte-identical;
    the corruption cases now lex the input as written.
  - *Evidence:* a behaviour corpus of 52 hashed outputs (stdout,
    stderr, exit code, object files) over 17 invocations of 11 inputs —
    synthetic probes for diagnostic line numbers after breaks,
    `#`-directive at beginning-of-line after a break, string/comment
    passthrough of all nine bytes, top-level and in-expression breaks,
    breaks inside `#if 0`, `-bench` stats, the `phext/tests` helios
    fixture, and a 400 KB slice of this repo's own `phcc.phext` —
    recorded against the pre-F3 build before any edit: **49/52
    byte-identical after F3**; the single divergent invocation is the
    corruption reproducer above (before: exit 1, stomped echo; after:
    exit 0, faithful echo). A spaced variant of the same input (every break
    beyond the counter span, where the seed functioned as designed) is
    byte-identical, parse errors included. Upstream suite: `make test`
    ALL TESTS PASSED before and after. Phext conformance suite compiled
    by the modified phcc itself: **163,831 checks, 0 failures**.
    `ONE_SOURCE` build (`make x86_64-tcc`) builds clean and reproduces
    the same corpus result.

- **F4 — the phext map is a hashmap (2026-11-07).** Will's ruling:
  "phcc should use the hashmap interface to speedup compilation,
  don't worry about working directly on the buffer most of the
  time." PARITY divergence D-4 closed in shape.
  - *Before:* `phext_scrolls` served both roles of the reference's
    `HashMap<Coordinate, String>` from one coordinate-sorted array —
    `phext_map_get` / `phext_map_insert` binary-searched it. Correct,
    but a compiler's hot path is coordinate lookups into a packed
    phext (source members fetched by address during compilation),
    and every lookup paid log₂(n) probes.
  - *Change:* the sorted array stays as the materialization — it is
    the iteration order, and `phext_implode` (which already cloned
    and sorted before emitting) keeps producing byte-identical
    output — and `phext_map_get` now probes a coordinate hash index:
    open addressing with linear probing, capacity a power of two at
    load ≤ 0.7, keys mixed by a splitmix64 chain over the nine
    coordinate components in declaration order (deliberately not the
    public FNV-1a `phext_coordinate_hash` — a published value callers
    may rely on; a table wants avalanche strength, not a stable
    value). The index is a pure cache: built lazily on first lookup,
    invalidated by any edit it cannot track exactly (push, sort,
    reset, a shifting insert; a content-replacing insert keeps it),
    every probe hit verified by coordinate equality, and binary
    search remains as the allocation-failure fallback — a lookup
    never fails for want of a cache. `phext_scrolls` gains three
    fields (`index`, `index_cap`, `index_fresh`); the one const cast
    in the library writes only those fields inside the logically
    const `phext_map_get`. PARITY.md's D-4 is annotated accordingly.
  - *Evidence:* the ported parity suite passes **163,831 checks,
    0 failures** under gcc and under the phcc built from this tree
    (dogfood); upstream `make test` ALL TESTS PASSED; the
    `ONE_SOURCE` amalgamated build (`make x86_64-tcc`) also compiles
    clean. Differential
    fuzz vs the Rust reference driver: 40,000 cases (two seeds),
    **0 divergences** on defined behaviour (Rust panics 173 + 166,
    all the D-2 op-20 class); stronger, the new C driver's outputs
    are **byte-identical** to the pre-F4 driver's on both corpora —
    nothing observable changed. Benchmark (aletheia-core, gcc -O2,
    medians of 7 interleaved runs; workload = this repo's
    `phcc.phext`, 49,209,925 bytes → 52,262 stored scrolls; hit
    counts and fetched-byte totals identical in both binaries):
    explode 42.0 ms → 47.9 ms (no explode-path logic changed — the
    only added instructions are flag writes, and a relayout control
    build measured the same, so the delta is attributed to code
    layout; reported, not tuned away); one-time index build at
    first lookup 1.5 ms (break-even ≈ 23,000 lookups); 200,000
    mixed lookups (90% hits / 10% near misses) 21.6 ms → 8.5 ms
    (**2.5×**, 108 → 42 ns per lookup); full sequential pass over
    all 52,262 coordinates 2.6 ms → 1.9 ms (1.4×); store build by
    52,262 shuffled `phext_map_insert` calls 539.7 ms → 540.6 ms —
    parity, stated plainly: the sorted materialization's memmove
    dominates inserts in both, and F4 claims lookup speed, not
    insert speed.

- **F5 — `packed`/`aligned` attributes are honoured, not erased
  (2026-11-07).** Conformance slice 1 (task 50.3.5/4.3.8/3.3.9)
  found the two HIGH silent defects REG-CONF-1/REG-CONF-2:
  `__attribute__((packed))` and `__attribute__((aligned(N)))`
  produced natural layouts with no diagnostic, in every placement.
  Root cause, established from the source and by preprocessed
  output: **the attributes never reached the parser.** phcc
  predefines neither `__GNUC__` nor `__clang__` (only `__TINYC__`),
  so glibc's `<sys/cdefs.h>` — reached via stdio.h, string.h,
  stdint.h, limits.h, … — takes its "compiler doesn't understand
  attributes" branch and defines `__attribute__(xyz)` as an empty
  function-like macro; tccpp's token loop then macro-expanded the
  keyword token (keywords live at `tok >= TOK_IDENT`, the same
  range the macro lookup covers) exactly as if it were an
  identifier, silently, in every translation unit that includes a
  glibc-routed header. The parser and layout machinery were intact
  all along: in header-free translation units every placement
  already laid out correctly. Fix family, three parts:
  - *tccpp.c:* `TOK_ATTRIBUTE1`/`TOK_ATTRIBUTE2` are never
    substituted — not in the live token stream (`next()`) and not
    when a macro body is walked (`macro_subst()`). The tokens are
    keywords, not identifiers; the oracles likewise never treat
    them as macro names. `#ifdef __attribute__` / `defined()`
    semantics are unchanged (only expansion is suppressed).
  - *tccgen.c, struct fields:* with the token surviving, gcc's
    split semantics for `aligned` had to be honoured, which the
    merged `SymAttr.aligned` cannot express: an attribute carried
    by the type itself (via a typedef — the Linux-kernel
    `unaligned_u64` idiom in `tests/tcctest.c`'s aligntest9) is
    part of the type's alignment and *replaces* the natural
    alignment; an attribute on the declarator can only *increase*
    it; `packed` (field or struct) first reduces it to 1, and a
    declarator attribute then applies to that. `struct_decl()`
    now snapshots the type-carried value exactly (parse_btype
    reports it via the `typedef_aligned` side channel), resolves
    each field's effective alignment at `sym_push`, and corrects
    fields again after the closing brace for a post-brace
    `packed`. Bit-fields are excluded from the packed reduction
    (struct_layout's bit-field path reads a nonzero `f->a.aligned`
    as a specified alignment). This also fixed two pre-existing
    divergences the probes exposed in the same family: member
    `aligned` could *decrease* a field's alignment (gcc: it cannot,
    without packed), and struct-level `packed` did not override a
    typedef-carried alignment.
  - *tccgen.c, enums and `_Alignof`:* `enum __attribute__((packed))`
    now selects the smallest integer type holding all enumerator
    values (unsigned when none is negative, else signed — the
    oracles' rule), enumerators included; a post-brace attribute
    is parsed for enums as it already was for structs. And
    `_Alignof` of a type-id naming a typedef'd scalar reports the
    typedef-carried alignment (handed over via the `sotype_aligned`
    side channel, since a `CType` cannot carry it); struct/union
    type-ids are excluded — the type's own alignment rules there.
  - *Evidence:* the conformance corpus re-run: exactly the two
    target probes changed behaviour across all 333 (b_gnu_010,
    b_gnu_011 now agree with gcc and clang byte-for-byte), leaving
    328/333 three-way agreement with the only remaining divergences
    the four documented class-(b) items (`__STDC_VERSION__`,
    `_Complex`, `__builtin_bswap`, `__auto_type`). A differential
    layout fuzz vs gcc AND clang (random struct/union shapes ×
    attribute placements, sizeof/_Alignof/every offsetof compared
    byte-for-byte): 300 files / ~1,500 layouts over two seeds,
    **0 divergences**; an enumerative typedef grid (4 base types ×
    6 carried alignments × packed contexts × 5 declarator
    attributes = 240 structs): **byte-identical to both oracles**.
    Upstream `make test` ALL TESTS PASSED (aligntest9 included);
    phext parity suite 163,831 checks / 0 failures under gcc and
    under the fixed phcc. Known oracle splits, followed but not
    chased: `_Alignof` of an enum with `aligned` (gcc ignores,
    clang applies — phcc follows gcc); aligned on a global
    variable, decrease case (gcc honours, clang ignores — phcc
    follows clang, pre-existing); attributes in a raw type-id
    (gcc honours, clang ignores — phcc follows gcc). Note for the
    phext: this entry changes the Source scrolls of `tccpp.c` and
    `tccgen.c`, so on the next phext refresh the bindings for
    machine #1 (tccpp.c), machines #2 and #4 (tccgen.c), and those
    files' Design views go STALE until regenerated; machine #3
    (tccelf.c), the libtcc1 proof receipts and the assembly
    listings are untouched.

- **F6 — `.eh_frame` FDE PC Begin travels in the relocation addend
  (2026-11-07).** Patch-queue item PQ-1 from the benchmark pass
  (tasks 37.5.7/6.5.9/5.5.9 and 27.6.10/8.6.13/6.6.10): GNU ld
  rejected every phcc object containing ≥2 functions with
  `.eh_frame_hdr refers to overlapping FDEs` / `final link failed:
  bad value` — blocking zlib's default (shared) build and, by
  construction, any GNU-ld link of phcc objects (the normal case
  for autotools shared libraries). Root cause, established from
  the source and from the emitted bytes: in `tccdbg.c`,
  `tcc_debug_frame_end()` emitted each FDE's PC Begin relocation
  through `dwarf_reloc()`, which hardcodes addend 0 in
  `put_elf_reloca()`, and wrote the function's `.text` offset
  (`func_ind`) into the field contents — the REL convention. On
  RELA targets (all 64-bit targets) a consumer resolves a
  relocation from `r_addend` alone and ignores the field contents,
  so every FDE's initial location resolved as if its function
  started at `.text + 0` (`readelf --debug-dump=frames`: two
  functions, both `pc=0..size`; gcc's are contiguous). phcc's own
  linker never noticed: it builds `.eh_frame_hdr` after applying
  the same relocations and performs no overlap validation, so its
  executables silently carried the same wrong FDE addresses.
  Fix: a new `dwarf_reloca()` beside `dwarf_reloc()` records the
  addend in the relocation entry on RELA targets; on REL targets
  it degrades to `dwarf_reloc()` (`put_elf_reloca` rejects an
  addend there, and the field-contents convention is the correct
  one). `tcc_debug_frame_end()` now passes `func_ind` as the
  addend on all five targets (i386, x86_64, arm, arm64, riscv64)
  and writes 0 in the PC Begin field on RELA (`func_ind` on REL)
  — structurally identical to gas/gcc output, whose addends read
  `.text + <function offset>` over zeroed fields. Evidence: the
  PQ-1 reproducer (two trivial functions) now links under GNU ld
  as both an executable and a shared object and runs correctly;
  `readelf` shows FDE ranges contiguous and per-function correct
  (`0..0x1d`, `0x1d..0x3f`; a three-function case gives
  `0..0x12`, `0x12..0x63`, `0x63..0xa9`), and the relocation
  addends match gcc's pattern. zlib 1.4 builds under phcc with
  the benchmark's verbatim recipes **both** ways — default
  (`libz.so.1.4` produced; the step that failed before) and
  `--static` — and `make test` reports "zlib test OK" in both.
  Upstream `make test` ALL TESTS PASSED; a self-host build (phcc
  built by the fixed phcc) builds and passes ALL TESTS PASSED,
  and in a phcc-linked executable the FDEs now sit at the real
  function addresses. Conformance corpus re-run: 328/333
  three-way agreement, the diverge set identical to the post-F5
  baseline (the five documented class-(b) probes) — no
  classification changed. Companion finding, deliberately NOT
  fixed here: phcc objects still lack `.note.GNU-stack` (a GNU
  ld warning that rides along in the same logs). That section is
  an object-writer concern in `tccelf.c`, a separate code path
  from FDE emission in `tccdbg.c`; it wants its own entry and
  its own decision. Note for the phext: this entry changes the
  Source scroll of `tccdbg.c` only (and adds one member,
  `dwarf_reloca`) — on the next phext refresh, `tccdbg.c`'s
  Design view and Volume 3 segmentation go STALE until
  regenerated. `tccelf.c` is untouched, so machine #3's binding
  stays CURRENT, as do the libtcc1 proof receipts, the assembly
  listings, and the Library-10000 build region.

## Maintenance rule

Every future phcc change lands as: (1) a commit, (2) a row or edit in
this file in the same commit, (3) on upstream sync, a rebase (never a
merge) with conflicts resolved under the R1–R7 principle and logged here.
