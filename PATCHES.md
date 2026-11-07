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
| `tcc.h` | +57 / −3 | Phext support core declarations (from c27c095; reworked by F3): `IO_BUF_SIZE` 8192 → 32768; `BufferedFile` gains a `phext_coordinate` — the phext library's coordinate type (F3 replaces the seed's nine int counters, which sat after `buffer[1]`, inside the region the input's own bytes are read into); `TCCState` gains nine totals (printed by `tcc_print_stats`; no code assigns them — as the seed left them); nine `TOK_*_BREAK` token defines for the phext delimiters (scroll 0x17 … library 0x01), their values taken from the library's `PHEXT_*_BREAK` constants since F3; `TCC_STATE_VAR` accessors for the nine totals; `#include "phext/phext.h"`. F7: four token kinds for the C11 prefixed literals (`TOK_U16CHAR`/`TOK_U32CHAR`/`TOK_U16STR`/`TOK_U32STR`) and a widened `TOK_HAS_VALUE`. F10: `TCCState` gains the version-script fields (`version_scripts`, the verdef section/index state, the per-dynsym version array, the parsed-script pointer) with their `TCC_STATE_VAR` accessors. |
| `tccpp.c` | +91 / −4 | Phext support in the preprocessor: consumes the nine phext break tokens while reading input; since F3 the per-file position is advanced by the phext library's `phext_coordinate_*_break` functions instead of the seed's hand-rolled counter arithmetic. F5: the `__attribute__` keyword tokens are never macro-expanded (see F5). F7: the literal scanner/parser handles the C11 encoding prefixes (`u`, `U`, `u8`) beside `L` (see F7). |
| `tccgen.c` | +331 / −16 | F5 (first fork change to this file): `packed` enum type selection, declarator/type-carried `aligned` resolution for struct fields, typedef-carried alignment in `_Alignof` type-ids. See F5. F7: `char16_t`/`char32_t` literal types and generalized string-initializer handling for the new literal kinds (see F7). F11: initializer cursor advance and offset accounting across anonymous struct/union members (`decl_cumofs`, `decl_next_field`). See F11. F13: `__builtin_constant_p` no longer calls a named object/function address (array decay, function designator) a constant. See F13. F15: excess initializers warn and discard (the `decl_excess` helper, `DIF_DISCARD`). See F15. |
| `tccdbg.c` | +28 / −5 | F6 (first fork change to this file): an FDE's PC Begin offset travels in the `.eh_frame` relocation's addend on RELA targets (new `dwarf_reloca()`), not only in the field contents, so GNU ld accepts multi-function phcc objects. See F6. |
| `tccasm.c` | +149 / −1 | F9: CFI directive family accepted by the assembler (operands parsed and shape-validated, unwind data dropped — see F9). F13: `asm_instr()` parses but does not constraint-check or emit asm statements sitting in code that will not be emitted (`nocode_wanted`). See F13. |
| `tcctok.h` | +22 | F9: `DEF_ASMDIR` tokens for the 22 CFI directives (inserted before `section`, which remains the last directive token). |
| `libtcc.c` | +40 | `tcc_print_stats` also prints the nine phext totals (scrolls … libraries) — re-expressed in upstream's current `#`-prefixed stats format during the rebase. See R6. Since F3, the `ONE_SOURCE` block also `#include`s `phext/phext.c` (last in the block, with `tcc.h`'s allocator poisons lifted around it) so amalgamated builds link the library. F10: `tcc_set_linker` records `version-script=` filenames on the state (parsing is deferred to link time); `tcc_delete` frees them. F14 makes `tcc_add_library` search directory-major (every library form within one directory before the next), matching GNU ld. |
| `tccelf.c` | +891 / −15 | F10 (first fork change to this file): `--version-script` support — script parser and verdict machinery, a localization demote pass composed after `set_elf_sym`'s resolution order, version recording at the two dynsym export points, VERDEF emission (`.gnu.version_d`, DT_VERDEF/DT_VERDEFNUM), and `version_add`/`fill_dynamic` taught to share the versym index space with definitions. See F10. F16: archive extraction follows GNU ld's rule — a standing COMMON pulls a member that strongly defines the symbol, a weak UNDEF never pulls — and a definition in a real section (data or bss) displaces a standing common in `set_elf_sym`. See F16. |
| `tests/tests2/60_errors_and_warnings.expect` | 1 line changed | F15: the `test_conflicting_array_definition` expectation was upstream's `error: too many initializers`; it now expects the oracle-conformant `warning: excess elements in array initializer` (both oracles emit exactly this text and accept). See F15. |
| `Makefile` | +10 | Phext library linkage (F3): in multi-object builds `phext/phext.c` compiles to `$(X)phext.o` and joins `LIBTCC_OBJ`; `ONE_SOURCE` builds get the same code via `libtcc.c`'s include instead. |
| `lib/libtcc1.c` | 2 lines changed | Cast the signed high word to `unsigned` before the left shift in `__ashrdi3` and `__lshrdi3` (C11 UB when the high word is negative). Correctness fix, not a phext feature; upstream-shaped and intended for upstream report once validated. See F1. |
| `include/float.h` | +30 | C11 `<float.h>` completion (F8): adds `FLT_EVAL_METHOD` (2 on i386, whose backend evaluates on the x87 stack; 0 on the other backends), the `FLT`/`DBL`/`LDBL_HAS_SUBNORM` family, the `*_DECIMAL_DIG` family, and the `*_TRUE_MIN` family. Additions only — no upstream line changed. See F8. |
| `phext/phext.h` | new, +397 | Public header for the phext developer library (F2): every type, constant, and function of the libphext-rs 0.4.1 parity surface, documented. C99, no dependencies beyond libc types. F4 adds the hash-index fields to `phext_scrolls`. |
| `phext/phext.c` | new, +2,031 | The library implementation (F2), including a scalar XXH3-128 port (from xxhash-rust's const implementation) for scroll checksums. Single translation unit. F4 adds the coordinate hash index behind `phext_map_get`. |
| `phext/PARITY.md` | new, +268 | The parity audit: all 77 libphext-rs capabilities mapped to their C counterparts, the idiom mapping, divergences D-2…D-6, and the conformance outcome. D-4 superseded annotation added by F4. |
| `phext/README.md` | new, +54 | Library overview, build/test instructions (including the phcc dogfood invocation), and the idiom-mapping summary. |
| `include/uchar.h` | new, +28 | C11 `<uchar.h>` for the hosted (glibc) header set (F7): `char16_t`/`char32_t` as `uint_least16_t`/`uint_least32_t` plus the four conversion-function declarations. The tree had no uchar.h outside win32/. |
| `win32/include/uchar.h` | +5 / −1 | F7: the typedef gate widened from `__STDC_VERSION__ >= 201112L` to also admit `__TINYC__` — phcc implements the u/U literals while reporting 199901L, so its PE builds need the typedefs the gate was withholding. |
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
- **F7 — C11 `char16_t`/`char32_t` literals are implemented
  (2026-11-07).** Patch queue item PQ-4 (task 27.6.10/8.6.13/
  6.6.10): the benchmark programme's FFmpeg build died in
  `libavformat/shared.c` on `MKTAG(u'\xFF','S','h','$')` — phcc
  lexed the `u` prefix as an identifier because the literal
  scanner only knew `L`. The fix extends the existing `L'…'`/
  `L"…"` machinery instead of adding a parallel one:
  - *tcc.h:* four token kinds (`TOK_U16CHAR`, `TOK_U32CHAR`,
    `TOK_U16STR`, `TOK_U32STR` at 0xd0–0xd3, previously unassigned)
    and `TOK_HAS_VALUE` widened to cover them — required, not
    decorative: a prefixed literal carried through a macro body
    (the FFmpeg case is a macro argument) loses its value in the
    token stream unless the stream treats it as a value token.
  - *tccpp.c:* the literal parser is parametrized by encoding
    (0 narrow, 1 `wchar_t`, 2 UTF-16, 3 UTF-32) instead of a
    boolean `is_long`. `\u`/`\U` escapes are code points,
    surrogate-split into UTF-16 strings above U+FFFF; `\x` stays
    one element *of the string's encoding* (matching the
    oracles' observable behaviour, including inside a UTF-32
    string); narrow `\u`/`\U` still encode as UTF-8, as before.
    Source text in prefixed strings is decoded as UTF-8 and
    re-encoded, so a literal `é` or 😀 in a `u"…"`/`U"…"` string
    lands as the right code units. The lexer recognizes the
    `u`/`U` prefixes beside `L` in both the quote and the
    stray-backslash paths, keeps `u8"…"` a plain `TOK_STR`, and
    no longer treats a leading `u`/`U` as an identifier start
    when a quote follows. `tcc -E` prints the new literals with
    their prefixes (byte-identical preprocessed output to gcc
    for the probe set).
  - *tccgen.c:* `u'…'` has type `unsigned short`, `U'…'`
    `unsigned int` (C11's `uint_least16_t`/`uint_least32_t`
    semantics on every phcc target). String literals initialize
    arrays through the same code path as `L"…"`, generalized by
    element size: same-encoding concatenation copies verbatim,
    an unprefixed literal concatenated with a prefixed one is
    decoded as UTF-8 and re-encoded into the wide element size
    (the oracles' observable rule), and a narrow literal still
    initializes `uint16_t`/`uint32_t` arrays, as it already did
    for `unsigned` arrays. One latent casualty found by the
    probes and fixed in the same pass: the inserted cases had
    intercepted `TOK_LCHAR`'s non-PE fallthrough to `TOK_CINT`;
    `L'…'` is spelled out explicitly again (PE: `unsigned
    short`; elsewhere `int`).
  - *Headers:* new `include/uchar.h` for the hosted set (the
    tree had none): the two typedefs plus `c16rtomb`,
    `mbrtoc16`, `c32rtomb`, `mbrtoc32` declarations. The win32
    set already shipped a uchar.h but gates its typedefs on
    `__STDC_VERSION__ >= 201112L`, which phcc never reports;
    the gate now also admits `__TINYC__` so PE builds see the
    typedefs the literals need.
  - *Oracle split, followed not chased:* a `char16_t` constant
    above the BMP and a `\x` escape whose value exceeds the
    element width — gcc (and its PP) truncate with a warning,
    clang rejects both as errors. phcc follows gcc exactly
    (value `0xDE00` for `u'\U0001F600'`, one unit for
    `u"\x1F600"`), per the programme's F5 precedent of picking
    one oracle per split.
  - *Evidence:* the FFmpeg minimal reproducer now compiles and
    runs, exit-identical to gcc. A differential probe set
    (values, `sizeof`/`_Alignof`, string contents incl.
    surrogate pairs, static/local/exact-fit initializers,
    concatenation incl. mixed prefixes and macro-carried
    literals, pointers, `#if`, `_Generic`) prints **byte-
    identical output under gcc 13.3.0, clang 18.1.3 and phcc**.
    Upstream `make test` ALL TESTS PASSED. Conformance corpus
    spot re-run unchanged: the same five documented class-(b)
    divergences (328/333), nothing new. The PE cross compiler
    compiles the new literals against the win32 headers
    (compile receipt only — no PE execution available).
    FFmpeg itself, on the benchmark recipe, now builds **past
    shared.c and through ~1,600 objects** before stopping at
    the *next* queue items, each isolated with a reproducer in
    phcc-pq4/repro-next/: the `mathops.h` `"i"`-constraint /
    `__builtin_constant_p` idiom (~190 TUs), SSE register
    clobbers rejected (`%xmm0`), SSE/MMX opcodes missing from
    the assembler (`movdqa`, `pshufd`, `xorps`, …), and a
    designated-initializer defect on anonymous-aggregate
    members (libswscale/format.c). One further failure is not
    the compiler's: `sys/sysctl.h` not found (libavutil/cpu.c)
    is a configure-detection divergence. Note for the phext:
    this entry changes the Source scrolls of `tccpp.c`,
    `tccgen.c`, `tcc.h` and `win32/include/uchar.h` and adds
    `include/uchar.h`, so on the next phext refresh the
    bindings for machine #1 (tccpp.c), machines #2 and #4
    (tccgen.c), those files' Design views and the gate verdict
    go STALE until regenerated; machine #3 (tccelf.c), the
    libtcc1 proof receipts and the assembly listings are
    untouched.
- **F8 — `include/float.h`: C11 <float.h> completion (2026-11-07).**
  The benchmark programme's patch queue PQ-5 (task
  27.6.10/8.6.13/6.6.10): GNU sed 4.10 and GNU grep 3.12 build under
  phcc and their main suites pass, but `make check` aborted in
  gnulib-tests compiling `test-float-h.c:28` —
  `'FLT_EVAL_METHOD' undeclared`. Audit of the shipped header
  against C11 §5.2.4.2.2 found the gap was the whole post-C89 layer,
  not the one macro: of the section's required macros, ten were
  missing — `FLT_EVAL_METHOD` (C99), and the C11 additions
  `FLT_DECIMAL_DIG`, `DBL_DECIMAL_DIG`, `LDBL_DECIMAL_DIG`,
  `FLT_TRUE_MIN`, `DBL_TRUE_MIN`, `LDBL_TRUE_MIN`,
  `FLT_HAS_SUBNORM`, `DBL_HAS_SUBNORM`, `LDBL_HAS_SUBNORM`. All
  other required macros were present with correct values. The fix
  is +30 lines, additions only; no upstream line is changed.
  - *`FLT_EVAL_METHOD` values follow the backends, not the oracle:*
    x86-64 evaluates float/double in SSE registers, each type in
    its own format (objdump of the generated code: `mulsd`/`addsd`/
    `mulss`) → **0**. i386 evaluates on the x87 stack (`fldl`/
    `fmull`/`faddl` — arithmetic at 80-bit), so float and double
    are evaluated in the format of long double → **2** (the value
    gcc also reports for x87 i386). ARM, AArch64, RISC-V and C67
    execute each FP operation in the operand type's own register
    format → **0**. Selected by `#if defined __i386__`, so cross
    compilers serving i386 get 2 and every other target gets 0.
  - *Remaining values:* `*_DECIMAL_DIG` 9/17, and `LDBL_DECIMAL_DIG`
    21 (x86 80-bit) / 36 (AArch64/RISC-V quad) / 17 (long double =
    double branch), beside the pre-existing per-branch
    `DECIMAL_DIG`; `*_HAS_SUBNORM` 1 — every format the header
    describes is an IEC 60559 format with gradual underflow;
    `*_TRUE_MIN` are the smallest positive subnormals (2^-149,
    2^-1074, and per-branch long-double 2^-16445 / 2^-16494 /
    2^-1074) written at full decimal precision.
  - *Deliberately not added:* the C23 macros (`*_IS_IEC_60559`,
    `*_NORM_MAX`, `*_SNAN`). phcc claims C11, and neither oracle in
    this environment (gcc 13.3.0, clang 18.1.3) defines them
    either; gnulib's own test wrapper supplies them when a suite
    needs them. `*_SNAN` in particular cannot be written truthfully
    as a header constant in C11 (no literal denotes a NaN; the
    oracles use `__builtin_nansf`, which phcc does not implement).
  - *Evidence:* (1) the PQ-5 reproducer (`repro/gnulib-float-h/
    repro-1.c`) failed before with `'FLT_EVAL_METHOD' undeclared`
    and now compiles and runs, returning 0 on x86-64; via the
    preprocessor the value reads 2 under i386-tcc and 0 under
    x86-64 tcc. (2) A differential probe printing every
    §5.2.4.2.2 macro (integers directly; float constants as raw bit
    patterns and `%a`) is **byte-identical under phcc, gcc 13.3.0
    and clang 18.1.3** — including `FLT_TRUE_MIN` = bits 0x00000001
    and `DBL_TRUE_MIN` = 0x1, so the literal parser rounds the long
    decimal spellings to the true subnormals. (3) Fresh phcc builds
    of sed 4.10 and grep 3.12 with the benchmark recipes
    (`./configure CC=phcc`, `make -j8`): `make check` now exits 0
    for both. sed: main suite 64 pass / 0 fail / 11 skip (unchanged)
    and gnulib-tests, previously aborted at test-float-h, completes
    222 pass / 0 fail / 65 skip of 287; grep: main suite 107 pass /
    0 fail / 19 skip / 2 XFAIL (unchanged) and gnulib-tests
    completes 257 pass / 0 fail / 58 skip of 315. `test-float-h`
    itself: PASS in both, binary exits 0. (4) Upstream `make test`
    ALL TESTS PASSED. Note for the phext: this entry changes the
    Source scroll of `include/float.h`, a shipped header (not one
    of the §A.3 machine files), so no machine binding moves; its
    Design view goes STALE on the next phext refresh until
    regenerated, as with any source change.
- **F9 — tccasm.c / tcctok.h: the assembler accepts the CFI directive
  family (2026-11-07).** PQ-2 of the benchmark patch queue.
  - *Files:* `tccasm.c` (+127), `tcctok.h` (+22).
  - *Change:* 22 `DEF_ASMDIR` tokens (`cfi_startproc`, `cfi_endproc`,
    `cfi_sections`, `cfi_def_cfa`, `cfi_def_cfa_offset`,
    `cfi_def_cfa_register`, `cfi_offset`, `cfi_rel_offset`,
    `cfi_adjust_cfa_offset`, `cfi_register`, `cfi_restore`,
    `cfi_undefined`, `cfi_same_value`, `cfi_return_column`,
    `cfi_negate_ra_state`, `cfi_personality`, `cfi_lsda`,
    `cfi_signal_frame`, `cfi_remember_state`, `cfi_restore_state`,
    `cfi_escape`, `cfi_label`) and matching cases in
    `asm_parse_directive`, with two operand helpers (`asm_cfi_reg`,
    `asm_cfi_name`). Before this change every CFI directive was
    `error: unknown opcode '.cfi_startproc'` — the first blocker in
    all 42 of OpenSSL's perlasm files.
  - *Semantics chosen — accept and ignore, stated plainly:* operands
    are parsed and shape-validated, then the unwind data is
    **dropped**; no `.eh_frame` content is emitted for assembler
    input. TCC builds `.eh_frame` only from its own C-level debug
    info (`tccdbg.c`), and that path is unaffected — C-level unwind
    behaviour is unchanged. Emitting real FDEs from directives was
    rejected: it needs a CFA state machine plus an `.eh_frame`
    writer inside the assembler, a large and error-prone surface
    producing data no TCC consumer reads. Consequence, also plainly:
    exception unwinding *through hand-written assembler frames*
    assembled by phcc has no CFI — the same limitation as any
    assembler input TCC accepted before, now without the hard error.
  - *Validation level:* operand kind (register = `[%]name` or DWARF
    number; offsets are full asm integer expressions, signs
    included), operand count, comma placement and end-of-line are
    all enforced; `.cfi_escape` operands must fit a byte;
    `.cfi_startproc` admits only the bare form or `simple`.
    Register names are checked for kind, not for existence on the
    target — the value is not emitted, so a misspelt name in a
    dropped annotation cannot corrupt output. A CFI directive TCC
    does not implement (e.g. `.cfi_def_cfa_expression`) still errors
    as an unknown opcode; nothing is silently misparsed.
  - *Evidence:* the PQ-2 reproducer (perlasm-shaped, from
    `~/workspace/phcc-bench/repro/openssl/repro-1.s`) and a torture
    file exercising every implemented directive: both assemble under
    phcc with `.text` bytes **identical to GAS**, link under both
    TCC's linker and GNU ld, and run with identical output
    (`repro=0 torture=7 simple=3`). Eight malformed-input cases
    (bad `simple` operand, missing register, missing comma,
    out-of-range `.cfi_escape` byte, missing operand, truncated
    `.cfi_personality`, unimplemented directive, trailing junk) all
    error with precise messages. Upstream `make test` ALL TESTS
    PASSED; conformance corpus spot re-run unchanged (328/333,
    diverge set `[a_pp_018, b_gnu_009, b_gnu_015, b_gnu_016,
    b_gnu_020]`, 0 oracle splits). OpenSSL 4.1.0 (benchmark recipe,
    `Configure linux-x86_64 no-tests`, `make -j8 build_sw`): the
    CFI blocker is eliminated in all 42 perlasm files — each file
    now advances to its *next* blocker, classified with verified
    minimal reproducers in `~/workspace/phcc-pq2/repro-next/`:
    `.section …, #alloc` flag syntax (22 files, first error),
    the PQ-8 SSE opcode/register cluster (`movdqu`, `movdqa`,
    `pinsrw`, `xorps`, `pshufd`; `%xmm8`–`%xmm15` missing from the
    register table), `.comm` unimplemented (x86_64cpuid.s), and
    the base-less SIB operand `(,reg,scale)` (x86_64-gf2m.s).
    Full OpenSSL completion remains bounded by those items and by
    PQ-3 (`--version-script`). Note for the phext: this entry
    changes the Source scrolls of `tccasm.c` and `tcctok.h`, so on
    the next phext refresh those files' Volume 3 segmentations and
    Design views go STALE until regenerated; neither file is bound
    by a §A.3 state machine, and the libtcc1 proof receipts and
    assembly listings are untouched.
- **F10 — `--version-script` support (2026-11-07).** PQ-3 from the
  benchmark programme: the link driver rejected
  `--version-script=<file>` outright ("unsupported linker option"),
  which stopped OpenSSL's provider/libcrypto link steps. The option
  is now implemented with real GNU ld semantics, not swallowed.
  - *Grammar subset (the common subset real projects use):* named
    version nodes and the anonymous node; `global:` / `local:`
    symbol lists; literal names and glob patterns (`*`, `?`,
    `[...]` including POSIX classes); quoted names; `extern "C"` /
    `extern "C++"` language blocks (symbols join the enclosing
    list); one version dependency per node (`NODE { … } PARENT;`);
    comments (`/* */`, `//`, `#`); multiple `--version-script`
    files merge. Errors, all hard (no output file, exit 1, GNU's
    own wordings): syntax error with file:line; a pattern string
    appearing in both a global and a local list anywhere
    ("duplicate expression"); an anonymous node combined with any
    other node; a dependency on an undefined node; an unreadable
    script file; and a script requested for a non-link output
    (`-c`, `-r`, object/PE/Mach-O) — never silently ignored.
  - *Matching precedence* (each rule established against GNU ld
    empirically before implementation): (1) exact literal in a
    global list — first such node wins; (2) exact literal in any
    local list — local beats wildcard global; (3) wildcard globals
    — last matching node wins; (4) wildcard local in any node —
    local; (5) otherwise plain global (versym 1). Symbols are not
    implicitly localized.
  - *Application, composed with machine #3 (LINKER RESOLUTION):*
    `set_elf_sym`'s branch order is untouched. The script is parsed
    at the top of `elf_output_file`; localization is a demote pass
    over the output symtab after `resolve_common_syms` and before
    `build_got`, demoting binding to STB_LOCAL in `.symtab` (so
    linker-created symbols added later stay exempt, as with GNU
    ld); version verdicts are recorded at the two existing export
    points (`export_global_syms` for DLLs, `bind_libs_dynsyms` for
    executables), keyed by dynsym index; the ABS version symbols
    for named nodes are added just before `create_gnu_hash` so the
    existing gnu-hash dynsym sort permutes their versym entries
    with everything else. Dynsym names stay plain — readelf's
    `name@@VER` rendering comes from VERSYM+VERDEF, as in GNU
    output, so no hash-table format changes. VERDEF layout matches
    GNU ld byte-for-byte on the probe corpus: entry 1 is the BASE
    definition (SONAME if given, else the output basename), named
    nodes follow in script order at indices 2, 3, … — all of them,
    even with zero matching symbols — a dependency becomes an extra
    verdaux, and `vd_hash` is the SysV elf_hash of the node name.
    The versym index space is shared with VERNEED, definitions
    allocated first; `version_add` was adjusted to allocate needed
    versions after them, to never overwrite a definition's versym
    entry, and to generate `.gnu.version_r` only when a needed
    version was actually allocated (an empty verneed section with
    a DT_VERNEED tag is rejected by glibc's loader — the guard
    counts from the post-definition baseline, not from 2).
  - *Evidence:* a 15-case probe corpus (named nodes with
    dependency, wildcard assignment and ordering, literal-vs-
    wildcard precedence both directions, local `*` inside a named
    node, empty nodes, extern blocks, anonymous node, merged
    scripts, a symbol named in a `global:` list but undefined,
    executables with named scripts with and without
    `--export-dynamic`) compared **byte-for-byte** against GNU ld
    (dynsym bindings/types/version assignment, the full VERDEF
    table, the DT tag set): all match; the only tolerated
    differences are pre-existing tcc traits outside the version
    observables (crt/UND surface, `name@plt` dynsym pseudo-entries,
    NOTYPE on undefined imports). A consumer programme linked
    against a phcc-built versioned library — by gcc and by phcc —
    runs: direct versioned references resolve, the localized symbol
    is absent from `dlsym`, `dlvsym` finds the symbol under its
    node and not under the sibling node. OpenSSL 4.1.0 (benchmark
    tree, verbatim recipe `linux-x86_64 no-tests no-asm no-shared`,
    CC = this build): the previous failure point,
    `providers/legacy.so` with `-Wl,--version-script=providers/
    legacy.ld`, now links, exporting exactly `OSSL_provider_init`
    as the script directs (gcc's legacy.so exports the same single
    symbol); the build then stops at `apps/openssl` with
    unresolved references to libcrypto functions — reproduced
    identically with the pre-F10 baseline compiler, a separate
    pre-existing archive-resolution limitation, not this change.
    With `no-asm` and shared libraries the same tree builds
    **completely**: `libcrypto.so.4`'s VERDEF is byte-identical to
    the gcc build's (BASE + OPENSSL_4.0.0 + OPENSSL_4.1.0 with
    parent), 5,693 OPENSSL-versioned defined exports in both,
    zero defined-global leaks past `libcrypto.ld`'s lists, and the
    resulting `apps/openssl` runs (SHA-256 digest verified against
    the system tool). Upstream `make test` ALL TESTS PASSED;
    conformance spot re-run unchanged at 328/333 with the same five
    documented class-(b) divergences. Note for the phext: this
    entry changes the Source scrolls of `tccelf.c`, `tcc.h` and
    `libtcc.c`, so on the next phext refresh the binding for
    machine #3 (tccelf.c — its documented resolution order is
    unchanged; the demote pass and the export-point recording
    compose after it and must be added to the machine's
    description), the `tccelf.c` Design view, and the gate verdict
    go STALE until regenerated; machines #1, #2 and #4 are
    untouched.
- **F11 — designated initializers continue correctly across
  anonymous struct/union members (2026-11-07).** Found by the
  benchmark programme's patch queue (PQ-9): FFmpeg's
  libswscale/format.c:977,
  `*swiz = (SwsSwizzleOp) {{ .x = tmp[0], tmp[1], tmp[2], tmp[3] }}`,
  was rejected with "too many initializers". A designator naming
  a member of an anonymous struct/union sets the initializer
  cursor to that leaf field (C11 6.7.9 with 6.7.2.1p13: the
  members of an anonymous aggregate are members of the containing
  aggregate), and the positional initializers that follow must
  walk the leaf's own aggregate and then pop back out to the
  containing one. The inherited machinery did neither, in two
  places:
  - *Cursor advance* (`decl_initializer`'s list loop): after each
    element a union container reset the cursor to NULL and a
    struct container advanced it within the leaf's own sibling
    list only — so the first continuation element after a
    designator into an anonymous struct inside a union already
    failed, and the element after an anonymous aggregate's last
    member always failed.
  - *Offset accounting* (`decl_designator`'s no-designator path):
    a continuation element was addressed at the cursor's own `c`,
    the leaf's offset within its anonymous aggregate, instead of
    its cumulative offset within the container — silently wrong
    code whenever the anonymous aggregate sits at a nonzero
    offset (`struct { int pad; struct { int a, b; }; } s =
    { .a = 1, 2 }` stored the 2 over `a`). No diagnostic pointed
    here; differential probing found it, not the FFmpeg failure.
  Fix, all in *tccgen.c*, two helpers beside `decl_designator`:
  `decl_cumofs()` accumulates a field's offset through anonymous
  members (the walk `find_field` does by name, done by identity),
  and `decl_next_field()` computes the continuation cursor —
  walk the anonymous aggregate's remaining members, pop out to
  the member following it when they run out, and treat a union
  as exhausted once the member through which the cursor was
  reached is spent (a union never continues into another
  member). For a direct field both reduce to the previous
  behaviour exactly (offset `f->c`; advance `f->next`, NULL for
  unions). The no-designator path now addresses continuation
  elements at the cursor's `decl_cumofs()`; the list loop
  advances with `decl_next_field()`.
  - *Evidence:* the FFmpeg reproducer compiles and runs with
    the oracles' result (exit 0 under gcc, clang and phcc). A
    14-case differential probe family around the defect —
    anonymous union only, anonymous struct only, two-level
    nesting, designator-then-positional, positional-then-
    designator, arrays inside anonymous members, anonymous
    aggregates at nonzero offsets, file-scope initializers, the
    chained `.u.x` form — is byte-identical under phcc,
    gcc 13.3.0 and clang 18.1.3 (14/14); the unfixed compiler
    rejected 11 of the 14 with "too many initializers" and
    silently miscompiled a twelfth (the offset case), passing
    only the two no-designator guard cases. Under the benchmark's
    FFmpeg 9.0.2 recipe, libswscale/format.o now compiles.
    Upstream `make test` ALL TESTS PASSED; conformance spot
    re-run unchanged (328/333 three-way, the same five
    documented class-(b) divergences). Deliberately unchanged:
    excess initializers beyond a container's capacity remain a
    hard error where the oracles warn and discard — that
    behaviour predates this fix, applies to plain aggregates
    with no anonymous members and no designators, and is a
    separate divergence. Note for the phext: this entry changes
    the Source scroll of `tccgen.c`, so on the next phext refresh
    the bindings for machines #2 and #4 (tccgen.c) and that
    file's Design view go STALE until regenerated; machines #1
    and #3, the libtcc1 proof receipts and the assembly listings
- **F12 — assembler completion cluster (2026-11-07).** The x86
  assembler learned the surface the benchmark corpora (OpenSSL 4.1.0
  perlasm, FFmpeg 9.0.2 inline asm) actually use. Nine files:
  `tccasm.c`, `tcctok.h`, `tcc.h`, `i386-asm.c`, `i386-tok.h`,
  `i386-asm.h`, `x86_64-asm.h`, `i386-gen.c`, `x86_64-gen.c`
  (+592 / −39). GAS is the oracle throughout: every encoding added
  is byte-compared against GAS-assembled `.text` on probe files.
  - **(a) `.section` full option grammar** (`tccasm.c`): GAS form
    `name[, "flags"[, @type[, entsize[, group[, comdat]]]]]`.
    Flag letters a/w/x/M/S/T/G/e map onto SHF_*; `o` accepted as a
    no-op (SHF_OS_NONCONFORMING has no per-section state here);
    an unknown flag letter is an error, as in GAS. Types
    progbits/nobits/note/init_array/fini_array/preinit_array map
    onto SHT_*; an explicit entsize lands on `sh_entsize`;
    init/fini/preinit arrays take GAS's natural entsize
    (PTR_SIZE) when none is given, and a section named `.note` or
    `.note.*` defaults to SHT_NOTE. Group+comdat operands are
    parsed and shape-validated but no SHT_GROUP section is
    emitted (documented limitation; no corpus file needs one).
    Flags apply only to a section this directive creates —
    pre-existing sections are never re-flagged. Two measured
    divergences from GAS, both deliberate: (1) an option-less
    `.section name` keeps TCC's longstanding SHF_ALLOC default
    where GAS gives a novel section no flags — TCC's own test
    suite is the evidence this is load-bearing (tcctest's
    `.pushsection .data.ignore` block relies on the section being
    allocated; with GAS's rule `make test` fails in `-run` mode
    with out-of-range relocations). A flags string, when present
    (even empty), replaces the default from zero exactly as GAS.
    (2) The perlasm `#alloc` tail: on x86-64 ELF GAS treats `#`
    as a comment character, so `.section .note.gnu.property,
    #alloc` yields a NOTE section with *no* SHF_ALLOC (readelf-
    verified against the F9 reproducer, whose comment claims the
    opposite — the claim holds only on targets where `#` is not
    the comment char). TCC's tokenizer likewise eats `#…` as a
    line comment in asm files, so the form is accepted with the
    option-less defaults above; the resulting section differs
    from GAS's in exactly the ALLOC cell of (1).
  - **(b) Label differences in data directives** (`tccasm.c`,
    hooks in `i386-asm.c`): perlasm note tails emit
    `.long 1f - 0f` (126 occurrences across the corpus), which
    the eager folder rejected ("invalid operation with label")
    because the forward label is undefined at parse time.
    Same-section asm-label differences in non-PC-relative
    contexts are now deferred: the expression carries a synthetic
    diff symbol, emission writes a placeholder, and patches are
    applied at the end of `tcc_assemble_internal` once both
    labels are defined (undefined or cross-section →
    `tcc_error`). Cross-section and `.`-relative differences
    keep the pre-existing PC-relative relocation path untouched
    (tcctest's `__bug_table` and `661b - .` cases exercise it);
    a diff symbol used as a jump displacement is an error.
  - **(c) `.comm`** (`tcctok.h`, `tccasm.c`): GAS semantics —
    symbol, size, optional alignment (power of two, else error);
    default alignment is min(16, smallest power of two ≥ size),
    measured against GAS for sizes 1…1000. Definitions are
    recorded per assembly unit and materialised at unit end,
    which is what makes repeated `.comm` merge correctly (max
    size, max alignment) in both modes: with `-fcommon` the
    symbol lands in SHN_COMMON with the alignment as its value;
    with `-fno-common` (TCC's default) it is allocated in `.bss`,
    mirroring how TCC's C tentative definitions materialise.
    Type is forced to STT_OBJECT; a `.comm` for a symbol already
    defined in a real section is an error. Verified symbol-for-
    symbol against GAS in both modes.
  - **(d) Base-less SIB operands** (`i386-asm.c`): `(,reg,scale)`
    and `disp(,reg,scale)` parse — the operand parser now accepts
    `,` where it previously required `%`. Encoding path is the
    existing one (base −1 → mod 0, SIB base 5, disp32). Five-form
    probe byte-identical to GAS; witness file x86_64-gf2m.s
    unblocked.
  - **(e) Register table: %xmm8–%xmm15** (`i386-tok.h`,
    `i386-asm.c`): tokens added *outside* the contiguous register
    block (insertion inside it would shift the cr/tr/db class
    arithmetic in the operand parser) with an explicit range
    branch in `parse_operand`; the encoder needed no change
    (REX.R/REX.B already handled reg ≥ 8 for OP_SSE). ymm/zmm
    deliberately not added: no VEX/EVEX encoding exists to back
    them. Probe byte-identical to GAS, %xmm0–7 regression-free.
  - **(f) SSE/MMX/SSE2/SSSE3 opcode coverage** (`i386-asm.c`,
    both asm tables): new `OPC_0F38` table flag for the 0F 38
    map (stored opcode is prefix byte + final map byte, as with
    the existing prefix idiom). Added, each byte-verified:
    movdqa, movdqu, movapd, movupd (66 0F 10/11 — GAS corrected
    an initial F3 guess), movsd (SSE scalar form; the string
    instruction of the same name never worked in TCC and is not
    regressed), movhlps, andps (i386 table), andnps, orps,
    xorps, shufps, paddq, pshufd, pshuflw, pshufhw, pshufw,
    pinsrw, pslldq (modrm group **7**), psrldq (group **3** —
    both corrected against GAS during verification; an early
    draft had them swapped with other groups), movntq, movntdq,
    punpcklqdq, punpckhqdq, the packed-double arithmetic family
    (addpd/subpd/mulpd/divpd, addsd/subsd/mulsd/divsd), the
    SSSE3 0F 38 family (pshufb, pabsb/w/d, psignb/w/d,
    pmaddubsw, pmulhrsw — final byte 0x0B per GAS, not 0xF5),
    adcx/adox (0F 38 F6 with 66/F3, including bare `adcxq`/`adoxq`
    tokens and the suffix-less 64-bit forms), movbe (0F 38
    F0/F1), and `pushfl`/`popfl` aliases in the x86-64 table
    (32-bit templates use them; GAS-64 itself rejects the
    suffix, TCC accepts — leniency noted). The MMX forms of
    `pavgb`/`pavgw` were widened from SSE-only operand masks to
    the MMXSSE idiom (FFmpeg uses `%mm` forms). Two pre-existing
    defects found and fixed en route: the movaps/movups table
    entries rejected a register source (`OPT_EA|OPT_REG32`
    where the source may be an SSE register — baseline fails
    `movaps %xmm1, %xmm2` identically), mask widened to
    `OPT_EA|OPT_SSE`; and SSSE3 entries initially double-emitted
    the 66 prefix (stored prefix byte plus the MMXSSE p66
    mechanism) — stored prefix removed, p66 supplies it.
  - **(g) Inline-asm SSE clobbers** (`i386-asm.c`, `tccasm.c`,
    `i386-gen.c`, `x86_64-gen.c`): clobber lists accept `xmm0`–
    `xmm15` (x86-64) / `xmm0`–`xmm7` (i386), with or without the
    `%` prefix — the prefix is now stripped for *all* register
    clobbers (`"%rax"` also failed at baseline). `mm0`–`mm7`
    are accepted as recorded no-ops, the same honesty class as
    the existing `"cc"`/`"flags"` handling; `xmm16`, `ymm0`,
    and other unknown names still error. Clobbered xmm slots
    are recorded in the existing `clobber_regs` mechanism
    (`NB_ASM_REGS` grown past the GP prefix in both backends)
    and are permanently marked allocated in constraint solving
    so the 'r' allocator can never select one. Faithfulness
    note: TCC's allocator never assigns xmm registers to C
    values (no 'x'/'v' constraints exist) and floating-point
    register state is not live across statements, so no
    save/restore obligation arises — recording is the same
    treatment GP clobbers get, not parse-only acceptance. Also
    in `tccasm.c`: the clobber-list parser now concatenates
    adjacent string literals, as C requires — FFmpeg's
    `"%"FF_REG_a` idiom previously reached the parser as a bare
    `"%"` and errored even at baseline.
  - *Corpus evidence (OpenSSL):* of the 42 perlasm files
    (measured on CFI-stripped copies; the sibling F9 entry covers
    the `.cfi` lines, which are the first blocker in all 42
    unstripped files), **12 assemble completely**: aes, aesni,
    bsaes, cmll, gf2m, keccak1600, md5, rc4, rc4-md5, vpaes, wp,
    x86_64cpuid. Their `.text` differs from GAS only in four
    pre-existing TCC policy classes, each reproduced byte-for-
    byte with the pristine baseline assembler on a policy probe
    (so none is F12 damage): (A) no jump relaxation (rel32 where
    GAS shortens to rel8), (B) `.align` filled with 0x90 where
    GAS uses multi-byte NOPs, (C) shift-by-one emitted in the
    C1 /ib form where GAS uses D1, (D) same-section branch
    targets carried in a RELA addend (field zero) where GAS
    resolves inline — TCC's documented always-relocate branch
    policy. The remaining 30 files are blocked solely by
    instruction encodings TCC does not implement at all, in
    three classes: **BMI2 `mulxq`** (5 files: ecp_nistz256,
    rsaz-x86_64, x25519, x86_64-mont, x86_64-mont5 — `adcx`/
    `adox` from the same files now assemble), **VEX 128-bit
    only** (4 files: aesni-gcm, aesni-mb, aesni-sha1, ghash —
    the smallest future VEX subset), and **VEX with 256-bit or
    EVEX forms** (21 files, incl. all AVX-512 files using
    %zmm/%k/xmm16+). Adding `vzeroupper`/`vzeroall` as special
    cases was measured and rejected: in every file where one is
    the first blocker it is followed by 294–5,881 other VEX
    lines, so the special case would complete zero files while
    misrepresenting coverage. VEX/EVEX support is a design item
    (prefix state machine), not table entries; it is recorded
    here as the assembler's one remaining coverage frontier.
  - *Corpus evidence (FFmpeg):* full build under the benchmark
    recipe — every translation unit that was blocked on
    assembler coverage now compiles, including the XMM_CLOBBERS
    files (FFmpeg's own configure probe now reports
    `HAVE_XMM_CLOBBERS 1`) and the pavgw/movapd/mulpd TUs found
    during the run. The build's remaining failures are exactly
    the out-of-scope items: 223 × the `mathops.h` 'i'-constraint
    error (PQ-6, honest `__builtin_constant_p`), one
    `sys/sysctl.h` configure-detection failure (known non-
    compiler item), one excess-initializers error (PQ-11), and
    one C11 char-literal error in libavformat/shared.c (F7's
    territory). *Suites:* upstream `make test` ALL TESTS PASSED
    (including the cross builds); the 333-probe conformance spot
    re-run is unchanged — 328/333 with the same five documented
    class-(b) divergences (`a_pp_018`, `b_gnu_009`, `b_gnu_015`,
    `b_gnu_016`, `b_gnu_020`), oracle split 0. The i386 cross
    compiler was rebuilt with the new tables and its probes
    byte-match GAS --32. Note for the phext: this entry changes
    the Source scrolls of `tccasm.c`, `tcctok.h`, `tcc.h`,
    `i386-asm.c`, `i386-tok.h`, `i386-asm.h`, `x86_64-asm.h`,
    `i386-gen.c`, and `x86_64-gen.c`, so on the next phext
    refresh those files' Source scrolls, their Vol 3
    segmentations and Design views, and the gate verdict go
    STALE until regenerated; no §A.3 state-machine file is
    edited (the assembler's operand and section handling is not
    one of the four machines), and the libtcc1 proof receipts
    are untouched.
- **F13 — `__builtin_constant_p` honesty + dead-code asm constraints
  (2026-11-07).**
  - *Files:* `tccgen.c` (+11, the `TOK_builtin_constant_p` case in
    `unary()`), `tccasm.c` (+22 / −1, `asm_instr()`).
  - *Change (tccgen.c):* the pre-existing test — the parsed argument
    must sit on the value stack as `VT_CONST` and not be an
    addrtaken symbol — is kept; one case is added. A pointer value
    that merely *names* an object or a function (array decay, a
    function designator: a named symbol, `TOK_IDENT <= v <
    SYM_FIRST_ANOM`, under a pointer or function type) is an
    address, not a folded constant, and now answers 0. String
    literals keep their anonymous symbol and still answer 1.
  - *Change (tccasm.c):* `asm_instr()` still parses its operands in
    full (token consumption and value-stack accounting unchanged,
    including the trailing `next()` past the `;` that callers rely
    on), but when the statement sits in code that will not be
    emitted (`nocode_wanted`: the dead arm of a constant-folded
    `if` / `?:` / `&&` / `||`, a `sizeof` operand, a discarded
    `__builtin_choose_expr` arm) it now skips `save_regs()`,
    constraint computation, operand substitution and assembly.
    Constraint satisfaction is a property of emitted code. In live
    code nothing changes: an unsatisfiable `"i"` operand there is
    still a hard error (negative-control probe in the evidence).
  - *Reason:* FFmpeg's `libavcodec/x86/mathops.h` idiom —
    `if (__builtin_constant_p(s)) asm (… "i" …) else asm (… "c" …)`
    inside a `static inline` helper (~190 TUs). phcc does not
    inline, so inside the helper `s` is a parameter and the honest
    answer is 0 — the pre-fix builtin already answered 0 there —
    but the dead `"i"` arm was still constraint-checked while being
    parsed under `nocode_wanted`, and the compile died with
    `asm constraint 1 ('i') could not be satisfied`. gcc folds the
    dead arm away before constraint checking. Making the constraint
    checker swallow unsatisfiable `"i"` operands instead was
    rejected: in live code that error is the only guard against a
    silent miscompile. On the builtin itself: gcc's answer is
    optimizer-dependent (at -O2, after inlining and value
    propagation, gcc answers 1 for locals, parameters at constant
    call sites, even `(1,2)`); a compiler without an optimizer
    cannot promise those, and code that branches on the answer
    stays correct with 0 — it merely takes the general path. The
    reference semantics is therefore gcc -O0: the compiler's own
    folder view at the point of the call.
  - *Evidence:* differential probe tables vs gcc 13.3.0 (files in
    `~/workspace/phcc-pq6/probes/`): 45 printed cases across three
    probe programs (literals, folded expressions, enum, `sizeof`,
    float/char literals, string literals incl. `+ 0` and indexing,
    named arrays bare / `+ 0` / indexed, globals by value and by
    address, locals, `const` locals, parameters by value and by
    address, function designators, side-effecting arguments —
    counters prove the argument's side effects are never evaluated,
    in `?:`, in `if`, and in static initializers) — the fixed
    phcc's output is **byte-identical to gcc -O0 on all 45**; the
    base phcc diverged on exactly 4 (named array bare, named array
    `+ 0`, named const-char array, isolated function designator).
    gcc -O2 recorded for the same tables: it diverges from its own
    -O0 on the 8 optimizer-knowledge cases named above, as
    expected. The mathops reproducer now compiles and runs with
    gcc's exit code; a live-code unsatisfiable `"i"` still errors;
    an unsatisfiable `"i"` inside a `sizeof` statement expression
    compiles, matching gcc. FFmpeg 9.0.2 (bench recipe, `make -k`,
    this fix on the 229ad47c base): 1,981 of 1,998 TUs built,
    **zero** `could not be satisfied` errors anywhere; the 15
    remaining failing files are all previously classified queue
    items — SSE clobbers ×5 and SSE/MMX opcodes ×8 (PQ-7 / PQ-8),
    `shared.c` (PQ-4, fixed by F7 on its own branch), `format.c`
    (PQ-9, fixed by F11 on its own branch), `libavutil/cpu.c`
    (`sys/sysctl.h` configure item). `make test` ALL TESTS PASSED;
    the 333-probe conformance corpus is unchanged (328/333, the
    same five documented class-(b) divergences, 0 unclassified);
    sed 4.10 and grep 3.12 rebuild cleanly under the fixed compiler
    and run (glibc-header regression smoke). Note for the phext:
    `tccgen.c` and `tccasm.c` Source scrolls change — machine #2
    and machine #4 bindings (tccgen.c) and the tccgen.c Design view
    go STALE at the next refresh; `tccasm.c` is bound by no §A.3
    machine; machine #1, machine #3, the libtcc1 proof receipts and
    the assembly listings are untouched.
- **F14 — libtcc.c: `-l` library search is directory-major, matching
  GNU ld (2026-11-07).**
  - *File:* `libtcc.c`, `tcc_add_library()` (+18/−8).
  - *Change:* swap the two search loops. For each directory of
    `s->library_paths`, in order, every library form is now tried
    (`libNAME.so`, then `libNAME.a`; the PE/Mach-O/OpenBSD form
    lists likewise) before the search moves to the next directory.
    The `static_link` form subset (archive only) and the
    `:`-prefixed exact-name path are unchanged.
  - *Reason:* the old form-major order tried `libNAME.so` in
    *every* directory before `libNAME.a` in *any*, inverting GNU
    ld's per-directory search — and `-L` directories precede the
    system directories in `library_paths`, so the inversion is
    observable whenever an early directory holds only an archive
    and a later one holds a shared library of the same name. That
    is PQ-10: linking OpenSSL 4.1.0's `apps/openssl` with
    `-L. -lssl -lcrypto` against a no-shared build tree never
    opened `./libssl.a`/`./libcrypto.a` at all (strace-verified);
    the search found the system's OpenSSL 3.x shared libraries
    and bound against them, leaving exactly 128 "unresolved
    references" — every one of them a symbol present in the local
    4.1 archives and absent from the system 3.x dynsyms (verified
    by set difference; GNU ld resolves all 128 from the identical
    objects and archives). The archive loader was exonerated
    first: `tcc_load_alacarte` already rescans each archive's
    index to a fixed point, and the same link with explicit
    archive paths resolved every symbol under the unfixed
    compiler. The inversion also silently binds the *wrong*
    library when no symbol goes missing (see the reproducer:
    archive answers 42, shared library answers 7; the old search
    printed 7, GNU ld 42).
  - *Evidence:* minimal reproducer (near directory archive-only,
    far directory shared-only) in both its unresolved-symbol and
    silent-wrong-library forms: fails under the old search,
    matches GNU ld exactly after the fix; forward-chain,
    within-archive-circular and backward-cross-archive controls
    unchanged. OpenSSL 4.1.0, verbatim F10 recipe
    (`linux-x86_64 no-tests no-asm no-shared`): `apps/openssl`
    now links and runs — `OpenSSL 4.1.0`, SHA-256 of "abc" equal
    to the system tool's — with **zero** unresolved references;
    `build_sw`'s only remaining stop is `providers/legacy.so`'s
    `--version-script`, which is F10's territory and absent from
    this change's base by construction. The shared configuration
    (`no-asm`, shared) shows 0 unresolved references and stops at
    the same pre-F10 `--version-script=libcrypto.ld` boundary as
    the unfixed base — no regression. Upstream `make test` ALL
    TESTS PASSED; conformance spot re-run unchanged at 328/333
    with the same five documented class-(b) divergences
    (`a_pp_018`, `b_gnu_009`, `b_gnu_015`, `b_gnu_016`,
    `b_gnu_020`); zlib 1.4 (`--static`, `make test` OK) and git
    2.56.0 (benchmark recipe) build and run under the fixed
    compiler; the fixed sources also self-host (built by the
    fixed compiler, `make test` ALL TESTS PASSED) and timing is
    unchanged: self-host build medians of 3 are 0.09 s for both
    the unfixed and fixed drivers, and the archive-heavy
    `apps/openssl` link (explicit archive paths, both drivers)
    medians 0.055 s for both over 5 reps — no rescan was added;
    the change only reorders the probes of a single `-l` lookup.
    Note for the phext: this entry changes only the Source scroll
    of `libtcc.c` (and its Design view), which go STALE at the
    next refresh. Machine #3 (LINKER RESOLUTION, Design
    1.1.1/3.2.5/1.2.2) needs **no** change: its events are
    tccelf.c's, no state, transition, invariant or note in the
    scroll describes `-l` search order, and extraction from an
    archive already chosen (ev_load_archive; invariant I10, note
    N7) behaves exactly as before.
  - *Related finding, deliberately not fixed here:* archive
    extraction still triggers only on SHN_UNDEF entries, where
    GNU ld also extracts a member whose definition satisfies a
    standing COMMON (reproducer: object with `int shared;` as a
    common + archive member defining `int shared = 42;` — ld
    prints 42, phcc prints 0). That is a value-correctness
    divergence in `tcc_load_alacarte`'s extraction criterion
    (machine #3 note N7 states tcc's rule), not an
    unresolved-reference defect; it wants its own queue item and
    its own machine-description update if pursued.
- **F15 — excess initializers warn and discard (PQ-11)
  (2026-11-07).** Upstream errors `too many initializers` on any
  initializer element beyond the end of its container. C11
  6.7.9p2 makes the provision of a value for an object not
  contained in the entity being initialized a constraint
  violation, and both oracles turn it into a *warning* at the
  default level (it is an error only under `-pedantic-errors`,
  a mode tcc does not have): the excess element is parsed and
  discarded, the kept elements are unaffected. Recorded as a
  pre-existing plain-aggregate divergence during F11 and left
  out of F11's scope; the FFmpeg sighting that motivated it
  (`libswscale/format.c:977`, seen in F12's logs) was in fact
  F11's designated-cursor defect, not this one — F15 closes the
  divergence itself, and the stacked verification below keeps
  the attribution straight.
  - *Oracle boundary map* (measured, gcc 13.3.0 + clang 18.1.3
    on aletheia-core, 44 differential probes; `-std=c11` ≡
    default for gcc on every probe): warn + discard for
    positional excess in arrays (including after designators),
    structs/unions past the last field, empty structs,
    zero-length arrays, scalar brace lists (`int x = {1, 2};`),
    compound literals, and per-container inside nested lists —
    an inner list's excess never stops the outer containers
    from continuing. Discarded elements are fully *parsed*
    (an undeclared identifier inside one still errors; nested
    designators are validated) but are never *evaluated* (a
    side-effecting excess element's counter stays 0 in both
    oracles — the common belief that gcc evaluates them is
    false), never conversion-checked (a string literal for an
    `int` slot warns only), and never constant-checked (a
    function call in a static excess element warns only).
    Still errors in both oracles, and still errors here:
    designated index out of bounds, range-designator overrun,
    unknown field designator; the flexible-array-member growth
    case warns in neither oracle and does not warn here
    (the check reads the bound after `decl_design_flex`).
  - *Mechanism* (`tccgen.c`, +94/−10): a new `DIF_DISCARD`
    flag and a `decl_excess()` helper at the two exhaustion
    points of `decl_designator` (array `index >= s->c`;
    struct/union with the field cursor exhausted) and in the
    scalar brace branch of `decl_initializer`. The helper
    warns once per excess element (`tcc_warning("excess
    elements in %s initializer", kind)` — gcc's exact text;
    the `DIF_SIZE_ONLY` sizing pass does not warn, the real
    pass does) and parses the element against its would-be
    type with `nocode_wanted` raised and `DIF_DISCARD` set:
    `one_elem` parses the expression as `EXPR_ANY` (so no
    constantness or conversion check fires) and drops it;
    container elements recurse through the same machinery, so
    excess surfaces at every nesting level; the four store
    paths (relocation deletion, range copy, array string
    store, `init_putz`) are suppressed under the flag. The
    string-initializer length rule is a different rule and is
    untouched. The list loop's field advance is NULL-guarded:
    after an excess element the cursor stays exhausted.
  - *Oracle splits, gcc followed both times:* (1) a brace
    group as the excess element of an exhausted struct/union
    is a hard error in gcc (`extra brace group at end of
    initializer`) and only a warning in clang — phcc errors;
    arrays warn in both. (2) gcc validates designators inside
    a discarded brace group against the would-be element type
    (an unknown-field designator inside one errors); clang
    does not — phcc's recursive parse validates, like gcc.
    Warning *counts*: phcc matches gcc exactly (once per
    excess element, including inside discarded groups), except
    on scalar-brace probes where gcc's higher count includes
    its separate "braces around scalar initializer" warning —
    a class tcc has never emitted, pre-existing and outside
    PQ-11 — and on the extra-brace-group probes, where phcc
    errors directly without gcc's preceding redundant excess
    warning (same accept/reject outcome).
  - *Evidence:* the 44-probe differential family passes in
    full against the fixed compiler — exit status, error
    presence, warning presence, run output and stored values
    identical to the oracle consensus on every probe (the base
    compiler errored on all but the two no-warning cases).
    `make test`: one expectation legitimately changed —
    `tests/tests2/60_errors_and_warnings.expect`,
    `test_conflicting_array_definition` (`extern int array[2];
    int array[] = {1, 2, 3};`) expected the old hard error;
    both oracles emit the new warning text verbatim and
    accept, so the expectation was updated in this commit —
    after which ALL TESTS PASSED. `tcctest.c` carries no
    initializer-error expectation (its only "too many" is a
    diagnostic-name string). Conformance spot re-run (333
    probes): **unchanged, 328/333 three-way**, the diverging
    set exactly the documented baseline five — no conformance
    probe covered excess initializers, so no classification
    moved. FFmpeg: on an F11+F15 stack (F11's `5fe697aa`
    cherry-picked onto this base, F15 applied over it; the
    three overlap hunks resolve by keeping both helpers,
    putting F15's exhaustion branch ahead of F11's
    `decl_cumofs` accounting, and keeping F11's
    `decl_next_field` advance, which maps NULL to NULL),
    `libswscale/format.o` builds under the benchmark recipe
    (configure rc=0, make rc=0); F11's designated-anonymous
    reproducer exits 0 with correct values, F11's 14 probes
    pass 14/14, and F15's 44 probes pass unchanged on the
    stack — the two fixes compose. Note for the phext: this
    entry changes the Source scroll of `tccgen.c` and its
    Volume 3 segmentation (new member `decl_excess`), so on
    the next phext refresh the bindings for machines #2 and
    #4 (tccgen.c), the `tccgen.c` Design view, and the gate
    verdict go STALE until regenerated; machines #1 and #3,
    the libtcc1 proof receipts, the assembly listings, and the
    Library-10000 binary region are untouched.
- **F16 — archive extraction satisfies standing commons, by GNU ld's
  rule (2026-11-07).** PQ-12: `int shared;` (a common) in the main
  object plus an archive member defining `int shared = 42;` printed
  0 under phcc and 42 under GNU ld — `tcc_load_alacarte` extracted
  members only for SHN_UNDEF entries, so a definition that existed
  solely to satisfy a common was never pulled. The extraction rule
  was established empirically against GNU ld (gcc 13.3.0's ld) over
  a 17-case probe matrix before implementing; it is a two-sided
  rule (standing entry × member definition):

  standing UNDEF (global) pulls for a strong, weak, or common
  definition in the member; standing UNDEF (weak) never pulls;
  standing COMMON pulls only for a strong definition (a member's
  common or weak definition satisfies an undefined, but for a
  standing common it neither displaces nor merges, so it does not
  pull); ABSENT and DEFINED entries never pull, and the decision
  is made when the archive is encountered (an archive placed
  before the object carrying the common pulls nothing — ld and
  phcc agree). All 17 cells now match ld.

  - *tccelf.c, `tcc_load_alacarte`:* the criterion is now
    UNDEF-and-not-weak, or COMMON; for a COMMON, the new helper
    `member_def_is_strong` inspects the candidate member's own
    symtab (ELF relocatable only; it answers "load" for anything
    unparseable, so the loader remains the judge) and the member
    is skipped unless its definition of the name is a strong one
    (STB_GLOBAL/STB_GNU_UNIQUE, defined, not SHN_COMMON).
  - *tccelf.c, `set_elf_sym`:* the brief's premise — "a strong
    definition displaces the common once the member is loaded" —
    verified in the code before relying on it, and it held only
    for PROGBITS definitions: `IS_BSS()` lumps SHN_COMMON with
    SHT_NOBITS sections, so a pulled member's *bss* definition
    (the normal shape from any -fno-common-built library) lost
    to the standing common, which also made the fixed-point
    rescan pull the same member again and error on its other
    symbols. One branch inserted ahead of the IS_BSS rows: an
    entry whose st_shndx is SHN_COMMON is patched by any
    definition in a real section (data or bss). Only that one
    cell changes: common × common still keeps the first common
    (machine note N6, measured again here: two commons of 4 and
    32 bytes merge to 4 under phcc, 32 under ld — a documented
    divergence F16 deliberately leaves alone), bss × data and
    the weak rows are byte-for-byte the old behaviour, and the
    dynsym harvest path is unreachable for the new branch (the
    SHF_DYNSYM accept row precedes it).
  - *Evidence:* the probe matrix (R5 anchor 0 → 42; commons of
    4+32 displaced by an archive definition of 16 — value and
    output size both; a bss definition of 64 displacing a common
    of 4 — size 64; extraction side-effect parity: a pulled
    member's colliding duplicate now errors "defined twice"
    exactly where ld errors; --whole-archive unaffected, 42 on
    both). Upstream `make test` ALL TESTS PASSED in the gcc-built
    tree and in the self-hosted tree (self-host build rc=0; the
    self-host suite linked by gcc fails identically on the
    unpatched base — that is PQ-1's overlapping-FDE rejection of
    tcc-built libtcc.a by GNU ld, not an F16 effect).
    Conformance spot re-run unchanged: 328/333, diverge set
    exactly the five documented class-(b) items, 0 oracle
    splits. Project builds: git 2.56.0 full build + init/commit/
    log smoke; zlib 1.4 --static build + `*** zlib test OK ***`
    (the default shared build still stops at GNU ld's
    overlapping-FDE rejection — PQ-1, present in this base and
    untouched by F16); OpenSSL 4.1.0 (no-asm, no-shared) failure
    signature byte-identical to the unpatched base — 128
    unresolved references at apps/openssl with the identical
    symbol set, plus the providers/legacy.so stop; those are
    F14's -l search order and F10's --version-script, separate
    entries on their own branches, and F16 changes neither.
  - *Machine #3 text this entry invalidates* (Design
    1.1.1/3.2.5/1.2.2; proposed replacements, to be applied at
    the next phext refresh — F16 does not edit the phext):
    the ABSENT state entry's last sentence becomes "Archives
    are not searched for ABSENT names; UNDEF entries (except
    weak ones) and COMMON entries trigger extraction — a
    COMMON only when the member strongly defines the name
    (invariant I10, note N7)." Note N7 becomes: "N7 ABSENT
    versus UNDEF is load-bearing. Archive extraction
    (tcc_load_alacarte) and the ld script GROUP rescan
    (ev_undef_scan) key on entries that exist: an UNDEF entry
    triggers unless it is weak (a weak undefined never pulls,
    GNU ld's rule), and a COMMON entry triggers when the
    member's definition of the name is a strong one — a common
    or weak definition in the member satisfies an UNDEF but
    does not pull for a standing COMMON, and once pulled, a
    definition in a real section (data or bss) displaces the
    common in ev_set. A name that was never referenced
    extracts nothing. That asymmetry is what makes archive
    linking order-insensitive for referenced symbols and
    inert for unreferenced ones." Invariant I10 gains one
    clause before its final sentence: "On the load side, the
    extraction that feeds ev_resolve obeys the dual rule:
    weak UNDEF entries never extract, and COMMON entries
    extract only against a member's strong definition — a
    COMMON is either displaced by a real definition before
    ev_resolve or allocated by ev_common exactly as if the
    archive had not been consulted for it."
  - *Phext bindings made STALE:* machine #3's binding **and
    its description** (extraction criterion, per the replacement
    text above), the `tccelf.c` Design view, the gate verdict,
    and `tccelf.c`'s Source scroll. Machines #1/#2/#4, the
    libtcc1 proof receipts, the assembly listings and the
    Library-10000 region are untouched.

## Maintenance rule

Every future phcc change lands as: (1) a commit, (2) a row or edit in
this file in the same commit, (3) on upstream sync, a rebase (never a
merge) with conflicts resolved under the R1–R7 principle and logged here.
