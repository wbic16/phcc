# phcc ↔ libphext-rs API Parity Matrix

Task 41.10.7/11.11.14/11.10.15 — Will: "make sure phcc has every capability
libphext-rs has, so developers can quickly handle phext data."

**Reference:** libphext-rs **v0.4.1**, read from source at
`~/workspace/libphext-provable/libphext-rs` (`src/phext.rs`, 1377 lines;
`src/lib.rs`; tests in `src/test_lib.rs`, `src/test_phokenize.rs`,
`src/regressions.rs`). Every row below was derived from that source, not
from memory of older versions.

**Established 0.4.x facts (verified in the source):** coordinate components
are 1-based (`COORDINATE_MINIMUM = 1`); there is **no upper bound** — the
999 cap was removed in 0.4.0 and `advance_coordinate` is a plain `+1` with
the comment "components are unbounded: advancing never saturates".

**Deliverable:** a developer library inside phcc, in a new top-level
`phext/` directory (`phext.h`, `phext.c`, tests). Additive only — no
existing compiler file changes. Base commit: phcc `395f5d63` (F1).

## C API conventions (the idiom mapping)

Rust idioms do not all have C spellings; the mappings used throughout:

| Rust idiom | C counterpart in `phext.h` |
|---|---|
| `String` return | `phext_buffer` (owned, length-authoritative, NUL-terminated for convenience), filled by the callee; caller frees with `phext_buffer_free` |
| `&str` / `&[u8]` input | `const unsigned char *` + `size_t` length. Embedded NUL bytes are ordinary bytes, exactly as in Rust. Phext scrolls are text; the C API is byte-oriented and never validates UTF-8 (Rust `&str` inputs are valid UTF-8 by construction; Rust *panics* when an edit would produce invalid UTF-8 — C cannot panic, so it does not check. Divergence D-3 below.) |
| `Vec<PositionedScroll>` | `phext_scrolls`: a growable array of `phext_positioned_scroll { phext_coordinate coord; phext_buffer scroll; }`, iterated by index. Rust iterators map to index loops / the array itself. |
| `HashMap<Coordinate, String>` | `phext_scrolls` kept **sorted by coordinate** (`phext_map_get`, `phext_map_insert` provided). Divergence D-4: Rust's map is unordered; the C map's order is defined, and `implode` output is byte-identical either way because Rust's `implode` sorts before serializing. |
| `Result<T, PhextParseError>` | `phext_status` return code: `PHEXT_OK`, `PHEXT_EFORMAT` (wrong segment counts), `PHEXT_ENUMBER` (non-numeric / overflowing component — Rust **panics** there via `.expect()`; C returns an error instead. Divergence D-2), `PHEXT_ENOMEM`. |
| Panics (`expect`, indexing) | Never in C. Every failure is a status code. |
| `fmt::Display` | `phext_*_display` functions: unconditional formatting, byte-identical output to Rust's `Display` impls. Kept distinct from `to_string` where Rust keeps them distinct (see Coordinate row). |
| `#[derive(Hash)]` | `phext_coordinate_hash` (FNV-1a over the 9 components) — a C-side utility for building hash tables. **Not** value-compatible with Rust: Rust's `Hash` output via `DefaultHasher` (SipHash) is explicitly not a stable or portable value, and no libphext test pins one. Counterpart by idiom, not by value. |
| Mutable methods (`&mut self`) | Functions taking `phext_coordinate *`. |

**Coordinate representation:** nested structs mirroring Rust field-for-field,
so Rust `coord.z.library` is C `coord.z.library`:

```c
typedef struct phext_zcoordinate { size_t library, shelf, series; }     phext_zcoordinate;
typedef struct phext_ycoordinate { size_t collection, volume, book; }   phext_ycoordinate;
typedef struct phext_xcoordinate { size_t chapter, section, scroll; }   phext_xcoordinate;
typedef struct phext_coordinate  { phext_zcoordinate z; phext_ycoordinate y; phext_xcoordinate x; } phext_coordinate;
```

**Ordering** (`Ord`): Rust derives `Ord` over the struct in declaration
order, so comparison is lexicographic by
library → shelf → series → collection → volume → book → chapter → section → scroll.
`phext_coordinate_compare` implements exactly this.

## 1. Constants — 26 of 26 have counterparts

| libphext-rs | Value | C counterpart |
|---|---|---|
| `COORDINATE_MINIMUM` | 1 | `PHEXT_COORDINATE_MINIMUM` |
| `LIBRARY_BREAK` (char) | 0x01 | `PHEXT_LIBRARY_BREAK` |
| `MORE_COWBELL` | 0x07 | `PHEXT_MORE_COWBELL` |
| `LINE_BREAK` | 0x0A | `PHEXT_LINE_BREAK` |
| `SCROLL_BREAK` | 0x17 | `PHEXT_SCROLL_BREAK` |
| `SECTION_BREAK` | 0x18 | `PHEXT_SECTION_BREAK` |
| `CHAPTER_BREAK` | 0x19 | `PHEXT_CHAPTER_BREAK` |
| `BOOK_BREAK` | 0x1A | `PHEXT_BOOK_BREAK` |
| `VOLUME_BREAK` | 0x1C | `PHEXT_VOLUME_BREAK` |
| `COLLECTION_BREAK` | 0x1D | `PHEXT_COLLECTION_BREAK` |
| `SERIES_BREAK` | 0x1E | `PHEXT_SERIES_BREAK` |
| `SHELF_BREAK` | 0x1F | `PHEXT_SHELF_BREAK` |
| `LIBRARY_BREAK_U8` … `SHELF_BREAK_U8` (11 byte twins) | same bytes | In C the constants *are* bytes (`unsigned char` values); the char/u8 twin distinction does not exist. One constant serves both roles — noted, not a gap. |
| `ADDRESS_MICRO_BREAK` | `'.'` | `PHEXT_ADDRESS_MICRO_BREAK` |
| `ADDRESS_MACRO_BREAK` | `'/'` | `PHEXT_ADDRESS_MACRO_BREAK` |
| `ADDRESS_MACRO_ALT` | `';'` | `PHEXT_ADDRESS_MACRO_ALT` |

## 2. Types — 7 of 7 have counterparts

| libphext-rs type | C counterpart | Notes |
|---|---|---|
| `ZCoordinate` {library, shelf, series} | `phext_zcoordinate` | `new()`/`Default` → `phext_zcoordinate_new()` (all 1s). `Display` → `phext_zcoordinate_display()`. Eq/Ord → field compare via `phext_coordinate_compare` arms / direct field access. |
| `YCoordinate` {collection, volume, book} | `phext_ycoordinate` | Same pattern. |
| `XCoordinate` {chapter, section, scroll} | `phext_xcoordinate` | Same pattern. |
| `Coordinate` {z, y, x} | `phext_coordinate` | Methods in §3. |
| `PositionedScroll` {coord, scroll} | `phext_positioned_scroll` | `new()` → `phext_positioned_scroll_new()` (coord 1.1.1/1.1.1/1.1.1, empty scroll). Rust `Display` prints `coord: ` + the **first 4 bytes** of the scroll and *panics* if the scroll is shorter (slice indexing). C: `phext_positioned_scroll_display()` prints up to 4 bytes and stops at the scroll's end — divergence D-5 (C never panics; output identical whenever Rust does not panic). `Ord` compares by coord only — `phext_positioned_scroll_compare`. |
| `Range` {start, end} | `phext_range` | `new()` → `phext_range_new()`. `Display` (`start-end`) → `phext_range_display()`. |
| `PhextParseError` | `phext_status` codes + `phext_parse_error_message()` | Returns the exact Rust `Display` text: "Phext addresses are of the form LB.SF.SR/CN.VM.BK/CH.SN.SC". |

## 3. Coordinate surface — 14 of 14 have counterparts

| libphext-rs | C counterpart | Behaviour notes |
|---|---|---|
| `Coordinate::new()` / `Default` | `phext_coordinate_new()` | All components 1. |
| `default_coordinate()` (free fn) | `phext_default_coordinate()` | Same value; both spellings provided as in Rust. |
| `validate_coordinate()` | `phext_coordinate_validate()` | True iff every component ≥ 1. No upper bound (0.4.0). |
| `to_string()` | `phext_coordinate_to_string()` | Returns **empty** for an invalid coordinate (Rust checks validity first). |
| `Display` impl | `phext_coordinate_display()` | Formats unconditionally — differs from `to_string` for invalid coordinates, exactly as in Rust. |
| `to_urlencoded()` | `phext_coordinate_to_urlencoded()` | `;` macro separators; empty if invalid. |
| `TryFrom<&str>` | `phext_coordinate_parse()` | Strict: exactly 3 macro parts × 3 micro parts, else `PHEXT_EFORMAT`. Non-numeric or `usize`-overflowing components: Rust panics (`.expect()`); C returns `PHEXT_ENUMBER` (D-2). |
| `to_coordinate()` (free fn) | `phext_to_coordinate()` | The *lenient* parser, ported literally: separators `.` `/` `;` assign components in order, extra separators ignored, missing components stay 1, **0 components are preserved** (and then fail validation), digit accumulation in `uint64_t` wraps on overflow (Rust: `u64` wrapping in release; debug panics — C matches release. D-6). |
| `scroll_break()` | `phext_coordinate_scroll_break()` | scroll += 1. |
| `section_break()` | `phext_coordinate_section_break()` | section += 1, scroll = 1. |
| `chapter_break()` | `phext_coordinate_chapter_break()` | chapter += 1, section/section reset. |
| `book_break()` | `phext_coordinate_book_break()` | book += 1, X arm reset. |
| `volume_break()` | `phext_coordinate_volume_break()` | volume += 1, book + X reset. |
| `collection_break()` | `phext_coordinate_collection_break()` | collection += 1, volume/book + X reset. |
| `series_break()` | `phext_coordinate_series_break()` | series += 1, Y + X reset. |
| `shelf_break()` | `phext_coordinate_shelf_break()` | shelf += 1, series + Y + X reset. |
| `library_break()` | `phext_coordinate_library_break()` | library += 1, everything else reset. |

Advance overflow: Rust `usize + 1` wraps in release builds (and the 0.4.0
comment says advancing never saturates). C `size_t + 1` wraps identically.
No clamping anywhere — parity, documented in the header.

## 4. Free functions — 27 of 27 have counterparts

All take document bytes + length and, where Rust returns `String`, fill a
caller-owned `phext_buffer` and return `phext_status`.

| libphext-rs | C counterpart | Notes |
|---|---|---|
| `check_for_cowbell` | `phext_check_for_cowbell()` | Byte scan for 0x07. |
| `get_subspace_coordinates` | `phext_get_subspace_coordinates()` | The dead-reckoning walker, ported literally including the `best` semantics and the early return when the target sorts before 1.1.1/1.1.1/1.1.1 (only reachable with a 0 component). Outputs `(start, end, best)` via pointers. |
| `fetch` | `phext_fetch()` | Empty buffer when the scroll is absent/empty (`end <= start`). |
| `replace` | `phext_replace()` | Ported literally, including the fixup-break emission from `best` up to the target (the behaviour the r0a/r1c/r1d regression vectors pin). |
| `insert` | `phext_insert()` | Rust takes an owned `String`; C takes bytes+length like every other function — the ownership difference is a Rust-side detail, not a capability. Splices at the *end* offset with fixup breaks, ported literally. |
| `remove` | `phext_remove()` | `replace` with `""`, then `normalize` — same composition as Rust. |
| `range_replace` | `phext_range_replace()` | Uses start's start-offset and end's end-offset from the walker. |
| `next_scroll` | `phext_next_scroll()` | Returns `(PositionedScroll, Coordinate, String)` via out-params. Ported literally, including: leading breaks advance the returned coordinate even when no text precedes them, and `begin` is the coordinate where the text run started. |
| `phokenize` | `phext_phokenize()` | One-pass tokenizer, ported literally (not via repeated `next_scroll` — Rust 0.4.x made it linear; the ported Rust tests assert the two agree on 5,000 random documents). Always yields at least one positioned scroll, even for empty input. |
| `explode` | `phext_explode()` | Output sorted by coordinate (D-4). |
| `implode` | `phext_implode()` | Sorts a copy of the input, then dephokenizes: empty scrolls emit no text but still advance the working coordinate. |
| `merge` | `phext_merge()` | Two-pointer merge, ported literally — equal coordinates concatenate (left text then right text at the same coordinate). |
| `subtract` | `phext_subtract()` | Drops left scrolls that have non-empty content at the same coordinate on the right; empty left scrolls are skipped entirely. |
| `expand` | `phext_expand()` | Byte remap: each break becomes the next-higher break (line→scroll→…→shelf→library; library stays). |
| `contract` | `phext_contract()` | Inverse remap (library→shelf→…→scroll→line; line stays). |
| `normalize` | `phext_normalize()` | `dephokenize(phokenize(x))`: drops empty scrolls, re-emits canonical breaks. |
| `create_summary` | `phext_create_summary()` | Bytes up to the first phext break (**line break included**), plus `"..."` iff truncated. Byte-based: multibyte UTF-8 is never split because UTF-8 continuation bytes are ≥ 0x80 and all breaks are < 0x20 — the property the Rust `summaries_keep_multibyte_characters_whole` test pins. |
| `navmap` | `phext_navmap()` | HTML `<ul>` of links, `urlbase` + urlencoded coord, coord + summary as text. Byte-identical format string. |
| `textmap` | `phext_textmap()` | `"* {coord}: {summary}\n"` per scroll. |
| `checksum` | `phext_checksum()` | xxh3-128 of the bytes, 32 lowercase hex chars, zero-padded. The C implementation in `phext.c` is a scalar port of the XXH3 algorithm as implemented by xxhash-rust 0.8.x (the crate libphext-rs 0.4.1 depends on), all length classes (0–3, 4–8, 9–16, 17–128, 129–240, >240 multi-block), default secret. Pinned by the 11 vectors in Rust's `test_scroll_manifest` and by differential fuzzing against the Rust driver. |
| `manifest` | `phext_manifest()` | phokenize → replace each scroll with its checksum → dephokenize. |
| `soundex_v1` | `phext_soundex_v1()` | Per-scroll soundex: value starts at 1, adds 1–6 per byte class (bpfv/cskgjqxz/dt/l/mn/r), result is `value % 99` as decimal. Ported literally, vowel/other bytes contribute 0. |
| `index` | `phext_index()` | Each scroll replaced by its byte offset in the original document (decimal). |
| `offset` | `phext_offset()` | Offset of the last scroll at or before the target; 0 when none (Rust 0.4.x returns 0 where earlier versions panicked). Status-returning form because C must surface allocation failure. |
| `is_phext_break` | `phext_is_phext_break()` | All ten breaks, line break included. |
| *(private)* `is_dimension_break` | `phext_is_dimension_break()` | Private in Rust (the nine scroll-moving breaks, line break excluded). Exposed in C because every C walker needs it; behaviour identical. A C-side exposure of an internal, not a parity gap. |
| `default_coordinate` | listed in §3 | |

Private Rust helpers with no public counterpart in either language
(ported as `static` internals in `phext.c`): `split_on`, `soundex_internal`,
`index_phokens`, `apply_break`, `dephokenize`, `append_scroll`,
`validate_dimension_index`.

## 5. Divergences (complete list)

- **D-2 — strict parse errors:** Rust `TryFrom` *panics* on a non-numeric
  or overflowing component (`.expect("Library missing")` etc.) and only
  returns `Err` for wrong segment counts. C never panics:
  `phext_coordinate_parse` returns `PHEXT_EFORMAT` / `PHEXT_ENUMBER`.
  Defined behaviour (segment counts, valid parses) is identical.
- **D-3 — UTF-8:** Rust functions take `&str` and `expect` valid UTF-8
  results. The C API is byte-oriented and imposes no UTF-8 requirement.
  On all inputs that are valid UTF-8, results are byte-identical.
- **D-4 — map order:** Rust `explode` returns an unordered `HashMap`;
  C returns a coordinate-sorted array. Observable behaviour (`implode`,
  lookup) is identical.
- **D-5 — `PositionedScroll` display:** Rust panics when the scroll is
  shorter than 4 bytes; C prints what exists. Identical whenever Rust
  returns normally.
- **D-6 — lenient parse overflow:** `to_coordinate` accumulates into a
  `u64`; Rust release builds wrap, debug builds panic. C wraps (release
  semantics). Only reachable with >19-digit components.

No capability is missing. **77 capability rows: 26 constants, 7 types,
17 Coordinate-surface items (incl. sub-coordinate Display impls), 27 free
functions — 77 with C counterparts, 0 without.**

## 6. What phcc already had, and how the library relates

phcc's pre-existing phext surface (from the 2024 seed commits, rebased in
Slice 0; PATCHES.md R-series) is *preprocessor awareness*, not a library:

- `tcc.h`: `TOK_SCROLL_BREAK` … `TOK_LIBRARY_BREAK` token defines for the
  nine breaks; per-file counters on `BufferedFile`
  (`scroll_num` … `library_num`); per-state totals on `TCCState`
  (`total_scrolls` … `total_libraries`).
- `tccpp.c`: the preprocessor advances those counters as it lexes.

Those stay exactly as they are. The new `phext/` library is independent:
same delimiter values (its constants agree byte-for-byte with the
`TOK_*_BREAK` defines), no shared state, no compiler file modified.

**Named follow-on (not done here, not silent):** *F3-candidate — wire the
preprocessor's counters to the library*: have `tccpp.c` maintain a
`phext_coordinate` alongside the nine `int` counters (or replace them) so
the compiler's own position tracking and the developer library share one
representation. That is a compiler change, separate from this parity work,
and wants its own slice and its own PATCHES.md entry when Will directs it.

## 7. Conformance plan (Phase C)

- Port every Rust test: `test_lib.rs` (49 tests), `test_phokenize.rs`
  (8 tests), `regressions.rs` (1 test, fixtures copied) → C harness in
  `phext/tests/`, same vectors, same expected values. Perf tests keep
  their structural assertions; wall-clock assertions are reported, not
  gated (hardware differs).
- Build and run under **gcc** and under **phcc itself** (built from this
  tree) — the dogfood receipt.
- Differential fuzz: random phext byte streams + random coordinate ops,
  C library vs a Rust reference driver built against libphext-rs 0.4.1;
  0 divergences tolerated on defined behaviour.

## Outcome (2026-11-07)

Implemented as planned: **77 capabilities audited, 77 with C counterparts,
0 gaps.** No row needed a "no counterpart" verdict; every Rust idiom had a
C spelling under the mapping above. Divergences D-2…D-6 stand as recorded
(D-1 was an audit-stage note, resolved during implementation).

Conformance, all on aletheia-core:

- The ported suite (test_lib.rs 49 + test_phokenize.rs 8 + regressions.rs 1
  = 58 test functions, same vectors and expected values): **163,831 checks,
  0 failures under gcc**, and **163,831 checks, 0 failures under phcc
  itself** (the freshly built `tcc` compiling `phext.c` + the harness —
  the dogfood receipt). phcc's own `make test` also passes on the tree.
- Differential fuzz vs a Rust reference driver built against libphext-rs
  0.4.1 (release): **40,000 randomized cases across two seeds** (documents,
  coordinates, and all 24 operation classes incl. checksums of >240-byte
  scrolls for the XXH3 long path): **0 divergences** on defined behaviour.
  The only Rust panics (173 + 166) are op-20 strict-parse panics — the
  documented D-2 class, where C returns `PHEXT_EFORMAT`/`PHEXT_ENUMBER`.

Follow-on named, not done: wiring the tcc preprocessor's phext counters
(tcc.h/tccpp.c) to this library (F3-candidate). The counters stay as they
are; the library is independent.
