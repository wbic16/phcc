# phcc ↔ libphext-rs API Parity Matrix

Task 41.10.7/11.11.14/11.10.15 — Will: "make sure phcc has every capability
libphext-rs has, so developers can quickly handle phext data."

**Reference:** libphext-rs **v0.5.0**, the published crates.io package
(the `.crate` artefact, SHA-256
`c8f8df75a786bc56bc7261e068e26cfa089341a26feb7d0c2a299ef2a6b4da8c`,
matching the crates.io index checksum), read from the extracted package
source: `src/phext.rs` (1404 lines), `src/binary.rs`, `src/seal.rs`,
`src/lib.rs`; tests in `src/test_lib.rs`, `src/test_phokenize.rs`,
`src/regressions.rs`, `src/test_binary.rs`, `src/test_seal.rs`. Every
row below was derived from that source, not from memory of older
versions. (The 0.4.1 audit read a local checkout; 0.5.0 is audited
against the canonical release artefact Will published.)

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
| `Result<T, PhextParseError>` | `phext_status` return code: `PHEXT_OK`, `PHEXT_EFORMAT` (wrong segment counts), `PHEXT_ENUMBER` (non-numeric / overflowing component), `PHEXT_ENOMEM`. Rust 0.4.1 **panicked** on the ENUMBER cases via `.expect()`; the merged parse-never-panics fix (in-tree 0.4.2) and 0.5.0 return `Err` there too — C keeps the two-way split where Rust has the one error value (D-2). |
| `Option<Vec<u8>>` (0.5.0 `decode_scroll`) | `phext_status`: `PHEXT_OK` + payload, or `PHEXT_ENONE` for Rust's `None`. |
| `io::Result<Vec<u8>>` (0.5.0 seal module) | `phext_status`: `PHEXT_OK`, `PHEXT_EINVAL` (invalid / trailing-data / truncated stream; `unseal_string` non-UTF-8), `PHEXT_ENOSEAL` (seal not compiled into this build). Divergence D-8. |
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

## 1. Constants — 28 of 28 have counterparts

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
| `BINARY_SCROLL_HEADER` (0.5.0, `binary`) | `"phext-binary:1:base64"` | `PHEXT_BINARY_SCROLL_HEADER` |
| `SEAL_PRESET` (0.5.0, `seal`) | 6 | `PHEXT_SEAL_PRESET` |

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
| `TryFrom<&str>` | `phext_coordinate_parse()` | Strict: exactly 3 macro parts × 3 micro parts, else `PHEXT_EFORMAT`. Non-numeric or `usize`-overflowing components: `PHEXT_ENUMBER`. Rust 0.4.1 panicked there (`.expect()`); 0.5.0 returns `Err` — the remaining difference is only that C splits the error in two where Rust has one error value (D-2). |
| `to_coordinate()` (free fn) | `phext_to_coordinate()` | The *lenient* parser, ported literally: separators `.` `/` `;` assign components in order, extra separators ignored, missing components stay 1, **0 components are preserved** (and then fail validation), digit accumulation in `uint64_t` **saturates** at `u64::MAX` on overflow — 0.5.0 switched Rust to `saturating_mul`/`saturating_add` (0.4.1 wrapped in release, panicked in debug); C saturates identically in all build modes (D-6, resolved). |
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

## 5. Binary scrolls (0.5.0, module `binary`, cargo feature `binary`) — 10 of 10 have counterparts

The canonical binary scroll format: a scroll whose content is the header
line `phext-binary:1:base64`, one line break, then the payload in
RFC 4648 base64 (standard alphabet, padding required, no line wrapping)
carries binary payload; an empty payload is the header line alone. The
ingestion rule (Will, canonical for all ports): *when non-UTF-8 data is
observed in an incoming scroll update, it is encoded with base64
verbatim.*

| libphext-rs | C counterpart | Behaviour notes |
|---|---|---|
| `is_binary_scroll` | `phext_is_binary_scroll()` | Prefix test: content begins with the header + line break. A bare header without the break is **not** a binary scroll. Returns `int` (Rust `bool`). |
| `encode_scroll` | `phext_encode_scroll()` | Header line + base64 of the payload. |
| `decode_scroll` | `phext_decode_scroll()` | `PHEXT_OK` + payload, else `PHEXT_ENONE` (Rust `None`): not a binary scroll, or body not strict base64. Strictness is the `base64` crate's STANDARD engine, probed against the published library on 22 verdict cases: length a multiple of 4, canonical padding (1–2 `=` at the very end), no whitespace or foreign bytes, non-zero trailing bits in a padded quantum rejected (`Zh==`, `Zm9=` → None). |
| `fetch_binary` | `phext_fetch_binary()` | Total: a well-formed binary scroll decodes; **any** other scroll — plain text, a malformed binary scroll, an unoccupied coordinate — yields the scroll's own bytes verbatim (empty when unoccupied). Fails only on allocation failure. |
| `insert_binary` | `phext_insert_binary()` | Stores the payload as a binary scroll unconditionally (even valid-UTF-8 payloads). |
| `replace_binary` | `phext_replace_binary()` | Same, via `replace`. |
| `insert_bytes` | `phext_insert_bytes()` | The ingestion rule: valid-UTF-8 payloads are stored as ordinary text; anything else as a binary scroll holding the base64 of the exact bytes. |
| `replace_bytes` | `phext_replace_bytes()` | Same, via `replace`. |
| `phokenize_bytes` | `phext_phokenize_bytes()` | Rust's function is a byte-level transcription of `phokenize`'s loop (same nine structural breaks), differing only in that `phokenize` requires UTF-8 input. The C API is byte-oriented throughout (D-3), so the one C walker serves both and the outputs coincide on every input; the differential fuzz (op 32) verifies the equivalence against Rust on arbitrary byte streams. |
| `ingest` | `phext_ingest()` | Byte-stream ingestion: phokenize as bytes; each valid-UTF-8 scroll passes through verbatim, each other scroll is stored as a binary scroll of its exact bytes; result is the canonical serialization (`implode` of the exploded map, duplicates resolved last-wins by document order, as in Rust). Never fails on content. |

## 6. The xz seal (0.5.0, module `seal`, cargo feature `xz`) — 4 of 4 have counterparts

Compression is a seal, not a working format: `seal` xz-compresses a
finished document as a whole (liblzma via the `xz2` crate, preset
`SEAL_PRESET` = 6, CRC64 check); `unseal` restores the exact original
bytes. Available in C when built with `PHEXT_WITH_XZ` (D-7).

| libphext-rs | C counterpart | Behaviour notes |
|---|---|---|
| `seal` | `phext_seal()` | On the text's bytes; identical to `seal_bytes` — the two Rust entry points differ only in input type (`&str` vs `&[u8]`), which the byte-oriented C API does not distinguish. Byte-identical output to Rust (both wrap the same liblzma; verified on payloads from 0 B to 5 MiB and on this repo's own `phcc.phext`). |
| `seal_bytes` | `phext_seal_bytes()` | The one implementation serving both Rust rows (the `phext_insert` owned-`String` precedent). |
| `unseal` | `phext_unseal()` | Accepts any valid xz stream (any preset/check — the repo's own `phcc.phext.xz`, sealed at preset 9-extreme by the refresh tooling, unseals byte-identically). The stream must be the **whole** input: Rust errors on any trailing bytes after the stream end (junk, zero padding, a second concatenated stream — all probed), on truncation, and on non-xz data; C returns `PHEXT_EINVAL` for each (D-8). |
| `unseal_string` | `phext_unseal_string()` | `unseal` + UTF-8 validation; non-UTF-8 content → `PHEXT_EINVAL` (Rust: `InvalidData`). For content that may carry non-UTF-8 scrolls, use `phext_unseal` + `phext_ingest`. |

## 7. Divergences (complete list)

- **D-2 — strict parse errors:** As found against 0.4.1, Rust `TryFrom`
  *panicked* on a non-numeric or overflowing component
  (`.expect("Library missing")` etc.) and only returned `Err` for wrong
  segment counts, while C returned `PHEXT_EFORMAT` / `PHEXT_ENUMBER`.
  **RESOLVED in two steps:** libphext-rs PR #8 (parse-never-panics,
  merged 2026-11-07; in-tree 0.4.2) made the strict parse return
  `Err(PhextParseError)` on malformed components, and the published
  **0.5.0 carries that behaviour** — verified against the release
  artefact: the 0.5.0 differential fuzz's op-20 class shows **zero**
  Rust panics (0.4.1 showed 173 + 166 across the two seeds). What
  remains is a spelling difference, not a behavioural one: Rust has
  the single `PhextParseError` value for every strict-parse failure,
  while C splits it into `PHEXT_EFORMAT` (segment shape) and
  `PHEXT_ENUMBER` (component not a number / overflows). Every input's
  accept/reject verdict is identical.
- **D-3 — UTF-8:** Rust functions take `&str` and `expect` valid UTF-8
  results. The C API is byte-oriented and imposes no UTF-8 requirement.
  On all inputs that are valid UTF-8, results are byte-identical.
- **D-4 — map order:** Rust `explode` returns an unordered `HashMap`;
  C returns a coordinate-sorted array. Observable behaviour (`implode`,
  lookup) is identical.
  **SUPERSEDED (2026-11-07, F4):** on Will's ruling ("phcc should use
  the hashmap interface to speedup compilation, don't worry about
  working directly on the buffer most of the time"), the C map's
  lookup store is now a coordinate hash table, the reference's shape:
  `phext_map_get` probes a lazily built open-addressing index
  (splitmix64 chained over the nine components; load ≤ 0.7; probe
  hits verified by coordinate equality), invalidated by any edit it
  cannot track exactly. What remains of D-4 is only the
  materialization: the C items array is still coordinate-sorted — so
  iteration over `.items` is deterministic, a safe superset of the
  reference's unordered HashMap iteration — and the canonical
  ordering lives at `implode`, whose emit path clones and sorts, so
  implode output was and remains byte-identical. Conformance under
  F4: the ported suite passes 163,831 checks / 0 failures under gcc
  and under phcc itself; the differential fuzz (40,000 cases, two
  seeds) shows 0 divergences on defined behaviour, and the new C
  driver's outputs are byte-identical to the pre-F4 driver's on both
  corpora. Benchmark (aletheia-core, medians of 7 runs, this repo's
  phcc.phext at 49,209,925 bytes → 52,262 scrolls): 200k mixed
  lookups 21.6 ms → 8.5 ms (2.5×); full sequential pass 2.6 ms →
  1.9 ms; explode 42.0 ms → 47.9 ms (no explode-path logic changed;
  attributed to code layout); shuffled-`map_insert` store build
  unchanged (539.7 ms → 540.6 ms — the sorted materialization's
  memmove dominates both); one-time index build 1.5 ms at first
  lookup. Full record in PATCHES.md (F4).
- **D-5 — `PositionedScroll` display:** Rust panics when the scroll is
  shorter than 4 bytes; C prints what exists. Identical whenever Rust
  returns normally.
- **D-6 — lenient parse overflow:** `to_coordinate` accumulates into a
  `u64`. In 0.4.1 Rust release builds wrapped (debug panicked) and C
  wrapped with them. **RESOLVED (0.5.0):** Rust switched the
  accumulation to `saturating_mul`/`saturating_add` — an over-long
  component now saturates at `u64::MAX` — and the C port saturates
  identically (PATCHES.md F45). Found by the 0.5.0 differential fuzz:
  the 20,000-case regression corpus showed exactly 40 divergences, all
  op-21 components above `u64::MAX`; after the fix, 0. Saturating
  arithmetic does not panic in debug builds either, so C now matches
  both Rust build profiles. Only reachable with >19-digit components.
- **D-7 — feature gating (0.5.0):** Rust gates `binary` and `xz`
  behind opt-in cargo features (`default = []`) because they pull
  dependencies (`base64`, `xz2`). Cargo features have no C analogue;
  the honest mapping is: the `binary` module is compiled into the C
  library **unconditionally** — its base64 is self-contained in
  `phext.c`, so there is no dependency to gate — while the seal
  genuinely needs liblzma and maps to the build-time option
  **`PHEXT_WITH_XZ`** (compile `phext.c` with `-DPHEXT_WITH_XZ`, link
  `-llzma`). In a build without it, the four seal functions return
  `PHEXT_ENOSEAL` and `phext_seal_compiled()` returns 0 (a C-idiom
  support predicate; not a capability row). Capability parity is
  claimed for the all-features-on configuration — the configuration
  the Rust reference driver is built with — with this gating
  difference recorded rather than papered over.
- **D-8 — seal error surface (0.5.0):** Rust's seal functions return
  `io::Result`, whose error is an opaque `io::Error`; the API does not
  enumerate kinds. C maps the observable cases: not-a-stream,
  truncated, and any-trailing-bytes inputs, and `unseal_string`'s
  non-UTF-8 result, all → `PHEXT_EINVAL`; seal-called-in-a-no-seal
  build → `PHEXT_ENOSEAL` (which has no Rust analogue at all — a
  no-feature Rust build has no seal symbols; see D-7). Accept/reject
  verdicts are identical; only the error vocabulary differs, as with
  D-2.

No capability is missing. **93 capability rows: 28 constants, 7 types,
17 Coordinate-surface items (incl. sub-coordinate Display impls), 27
core free functions, 10 binary functions, 4 seal functions — 93 with
C counterparts, 0 without.**

## 8. What phcc already had, and how the library relates

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

## 9. Conformance plan (Phase C)

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
(D-1 was an audit-stage note, resolved during implementation;
D-2 was resolved upstream on 2026-11-07, and D-4 was superseded the
same day by F4 — see §7 for both).

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

## Outcome — 0.5.0 (2026-11-08, PATCHES.md F45)

The 0.5.0 delta was 16 capabilities — the whole `binary` module (2
constants' worth of format + 10 functions) and the whole `seal` module
(1 constant + 4 functions) — plus one core behaviour change found by
re-audit: the lenient parser's saturating accumulation (D-6). The C
library now stands at **93 capabilities audited, 93 with counterparts,
0 gaps**; divergences D-7/D-8 record the feature-gating mapping and the
seal error vocabulary, and D-2's remaining content is the EFORMAT/
ENUMBER spelling split. The F3 follow-on named above has since landed
(the preprocessor's counters are wired to the library); F4's hash index
is the only other post-0.4.1 change, and the 0.5.0 work sits on top of
both unchanged.

One Rust-side packaging note from the audit: `test_seal.rs` reads
`../unit-test.phext` via `include_str!`, but the published `.crate`
package does not ship that file, so the crate's own seal corpus test
cannot build from the package alone. The C port seals the helios
regression fixture in the same role (a real, multi-scroll phext from
this repo's own test corpus).

Conformance, all on rock-mountain, base phcc `f65e68cc` (the D9 tip
`611b763e` plus the h8 receipt-port commit, which landed after this
wave's clone and was fast-forwarded to before work began):

- The ported suite, extended with `test_binary.rs` (9 tests),
  `test_seal.rs` (5 tests), a 22-case base64 strictness table, the
  trailing-data unseal verdicts, and the saturation test:
  **163,955 checks, 0 failures under gcc** (plain build) and
  **163,987 checks, 0 failures under gcc with `PHEXT_WITH_XZ`**;
  **163,955 / 163,987, 0 failures under phcc itself** (the tree's
  freshly built `tcc`, both variants — the dogfood receipt). The
  plain build's lower count is the seal tests replaced by the
  `PHEXT_ENOSEAL` stub test (D-7).
- Differential fuzz vs a Rust reference driver built against the
  **published 0.5.0 package** (features `binary` + `xz`): the 0.4.1
  regression corpus (20,000 cases, ops 0–23) shows **0 divergences and
  0 Rust panics** — the op-20 panic class is gone in 0.5.0, as D-2
  records — after the saturation fix (40 op-21 divergences before it).
  The new corpus (40,000 cases, ops 24–38: binary payloads incl.
  random non-UTF-8 through `ingest`/`fetch_binary` round-trips,
  malformed-header mutations, empty payloads, seal/unseal
  cross-checks in both directions) shows **0 divergences, 0 panics**.
- Seal cross-checks against this repo's own artefacts: C `unseal` of
  the shipped `phcc.phext.xz` reproduces `phcc.phext` byte-identically;
  C `seal` is byte-identical to the Rust library's seal (and to
  Python `lzma` preset 6 / CRC64). The shipped repo seal itself is
  produced by the refresh tooling at preset 9-extreme (`xz -9e`) — a
  different encoder setting for the same stream format; it unseals
  identically in Rust, C, and Python, and is not the library seal's
  business to match byte-for-byte.
- Tree receipts on the final tree: `make test` **ALL TESTS PASSED**;
  conformance spot **332/333** (diverge set exactly `[a_pp_018]`, 0
  oracle splits); static gate cells **3/3** (static hello + repaired
  IRELATIVE bounds, static Lua byte-identical, static phccbox awk
  prints 42).
