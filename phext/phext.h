/* ----------------------------------------------------------------------------------------------------------
 * phext.h - Phext Buffer Library for C
 *
 * The C counterpart of libphext-rs (v0.5.0), the reference implementation of
 * phext in Rust. Every public capability of the Rust crate has a counterpart
 * here; the full mapping, including the handful of places where C idiom
 * forces a different shape (never different defined behaviour), lives in
 * PARITY.md and in the phext/ directory notes.
 *
 * The 0.5.0 additions are the binary-scroll module (canonical base64
 * armouring for non-text payloads, plus the byte-oriented update entry
 * points that apply the ingestion rule) and the xz seal. In Rust both
 * modules are cargo features (`binary`, `xz`); the mapping to C is:
 *   - binary scrolls are always available here: the C implementation is
 *     self-contained (its own base64), so there is no dependency to gate;
 *   - the seal needs liblzma, so it is a build-time option: compile
 *     phext.c with PHEXT_WITH_XZ defined and link -llzma to enable it.
 *     Without it, the seal functions return PHEXT_ENOSEAL and
 *     phext_seal_compiled() returns 0.
 * See PARITY.md, divergence D-7.
 *
 * Copyright: (c) 2024-2026 Will Bickford (Phext, Inc.)
 * License: MIT
 *
 * Overview
 * --------
 * Phext is composable, relational text: layers upon layers of plain text
 * (scrolls) addressed by 9-dimensional coordinates of the form
 *
 *     library.shelf.series/collection.volume.book/chapter.section.scroll
 *
 * Dimensions are separated by ASCII control bytes that fell out of common
 * use (scroll break 0x17 up to library break 0x01); line breaks (0x0A)
 * stay inside a scroll. All text is stored in subspace: a traditional
 * buffer of UTF-8 text. You orient yourself in it by dead reckoning -
 * the same process text editors have used for columns and lines since
 * the dawn of the information age, extended from 2D to 11D.
 *
 * Coordinate rules (libphext 0.4.x):
 *   - components are 1-based: the minimum valid component is 1
 *     (PHEXT_COORDINATE_MINIMUM);
 *   - components are UNBOUNDED above: the 999 cap was removed in 0.4.0,
 *     and advancing a component never saturates;
 *   - a component of 0 makes a coordinate invalid (validation fails and
 *     the string forms come back empty), but such coordinates can still
 *     be constructed, compared, and parsed - exactly as in Rust.
 *
 * API conventions
 * ---------------
 *   - Documents and scrolls are byte strings: every function takes an
 *     explicit (pointer, length) pair. Embedded NUL bytes are ordinary
 *     bytes. The library never validates UTF-8 (Rust's &str API gets
 *     validity from the type system and panics if an edit would break
 *     it; C has no panic, so it does not check - on valid UTF-8 input
 *     every result is byte-identical to the Rust result).
 *   - Functions that produce a document or scroll fill a caller-owned
 *     phext_buffer (or phext_scrolls) and return a phext_status.
 *     Output parameters are reset on entry; free them with
 *     phext_buffer_free / phext_scrolls_free when done.
 *   - Nothing in this library panics, aborts, or invokes undefined
 *     behaviour on bad input. Failures are status codes. Where the Rust
 *     implementation panics (strict-parse of a non-numeric component,
 *     PositionedScroll display of a scroll shorter than 4 bytes), the C
 *     counterpart returns an error code or a shorter string instead;
 *     see PARITY.md, divergences D-2 and D-5.
 *
 * This header is C99-clean and safe to include from C++.
 * ---------------------------------------------------------------------------------------------------------- */

#ifndef PHEXT_H
#define PHEXT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ----------------------------------------------------------------------------------------------------------
 * phext constants (libphext-rs: phext.rs constants)
 *
 * In Rust each break exists as a char constant and a u8 twin; in C the
 * constants are bytes, so one constant serves both roles.
 * ---------------------------------------------------------------------------------------------------------- */
#define PHEXT_COORDINATE_MINIMUM ((size_t)1) /* human numbering - we start at 1, not 0 */

#define PHEXT_LIBRARY_BREAK    ((unsigned char)0x01) /* 11th dimension - replaces start of header */
#define PHEXT_MORE_COWBELL     ((unsigned char)0x07) /* i've got a fever, and the only prescription... */
#define PHEXT_LINE_BREAK       ((unsigned char)0x0A) /* same as plain text */
#define PHEXT_SCROLL_BREAK     ((unsigned char)0x17) /* 3D break - replaces End Transmission Block */
#define PHEXT_SECTION_BREAK    ((unsigned char)0x18) /* 4D break - replaces Cancel Block */
#define PHEXT_CHAPTER_BREAK    ((unsigned char)0x19) /* 5D break - replaces End of Tape */
#define PHEXT_BOOK_BREAK       ((unsigned char)0x1A) /* 6D break - replaces Substitute */
#define PHEXT_VOLUME_BREAK     ((unsigned char)0x1C) /* 7D break - replaces file separator */
#define PHEXT_COLLECTION_BREAK ((unsigned char)0x1D) /* 8D break - replaces group separator */
#define PHEXT_SERIES_BREAK     ((unsigned char)0x1E) /* 9D break - replaces record separator */
#define PHEXT_SHELF_BREAK      ((unsigned char)0x1F) /* 10D break - replaces unit separator */

#define PHEXT_ADDRESS_MICRO_BREAK ((unsigned char)'.') /* delimiter for micro-coordinates */
#define PHEXT_ADDRESS_MACRO_BREAK ((unsigned char)'/') /* delimiter for macro-coordinates */
#define PHEXT_ADDRESS_MACRO_ALT   ((unsigned char)';') /* also allowed, for url encoding */

/* libphext-rs 0.5.0 additions: the binary-scroll header line (binary.rs
 * BINARY_SCROLL_HEADER) and the seal preset (seal.rs SEAL_PRESET). A binary
 * scroll's content is this line, a single 0x0A, then the RFC 4648 base64
 * body (padding required, no line wrapping); an empty payload is the
 * header line alone. */
#define PHEXT_BINARY_SCROLL_HEADER "phext-binary:1:base64"
#define PHEXT_SEAL_PRESET 6 /* the xz preset the seal encodes with; an encoder
                               choice, not a format requirement - unsealing
                               accepts any valid xz stream */

/* ----------------------------------------------------------------------------------------------------------
 * status codes (Rust: Result<_, PhextParseError> and panics, mapped to codes)
 * ---------------------------------------------------------------------------------------------------------- */
typedef enum phext_status {
    PHEXT_OK = 0,      /* success */
    PHEXT_ENOMEM,      /* an allocation failed; outputs are left empty */
    PHEXT_EFORMAT,     /* address does not have the 3x3 segment shape (Rust: Err(PhextParseError)) */
    PHEXT_ENUMBER,     /* address component is not a number, or overflows size_t
                          (Rust 0.4.1: the strict parser PANICS here via expect(); C returns this.
                           Rust 0.5.0 returns Err there too - see PARITY.md D-2) */
    PHEXT_ENONE,       /* Rust: an Option-returning function returned None
                          (phext_decode_scroll on a non-binary or malformed scroll) */
    PHEXT_EINVAL,      /* Rust: an io::Error from the seal module - the data is
                          not a valid xz stream, has trailing bytes after the
                          stream end, or (unseal_string) is not valid UTF-8 */
    PHEXT_ENOSEAL      /* the seal functions were called in a build without
                          seal support (phext.c compiled without PHEXT_WITH_XZ) */
} phext_status;

/* The exact Display text of Rust's PhextParseError. */
const char *phext_parse_error_message(void);

/* ----------------------------------------------------------------------------------------------------------
 * buffers (Rust: String / Vec<PositionedScroll>)
 *
 * phext_buffer is an owned byte string. `data` is always NUL-terminated
 * (data[len] == 0) so it can be handed to C string functions when the
 * content is known to be text without embedded NULs, but `len` is the
 * authoritative length.
 * ---------------------------------------------------------------------------------------------------------- */
typedef struct phext_buffer {
    unsigned char *data;
    size_t len;
    size_t cap;
} phext_buffer;

void phext_buffer_init(phext_buffer *buf);
void phext_buffer_free(phext_buffer *buf);
void phext_buffer_reset(phext_buffer *buf); /* keep the allocation, drop the content */

/* ----------------------------------------------------------------------------------------------------------
 * coordinates (Rust: ZCoordinate / YCoordinate / XCoordinate / Coordinate)
 *
 * Field layout mirrors Rust exactly: coord.z.library reads the same in
 * both languages. Components are size_t, 1-based, unbounded above.
 * ---------------------------------------------------------------------------------------------------------- */
typedef struct phext_zcoordinate { /* the Z arm: library.shelf.series */
    size_t library;
    size_t shelf;
    size_t series;
} phext_zcoordinate;

typedef struct phext_ycoordinate { /* the Y arm: collection.volume.book */
    size_t collection;
    size_t volume;
    size_t book;
} phext_ycoordinate;

typedef struct phext_xcoordinate { /* the X arm: chapter.section.scroll */
    size_t chapter;
    size_t section;
    size_t scroll;
} phext_xcoordinate;

typedef struct phext_coordinate {
    phext_zcoordinate z;
    phext_ycoordinate y;
    phext_xcoordinate x;
} phext_coordinate;

typedef struct phext_range { /* Rust: Range */
    phext_coordinate start;
    phext_coordinate end;
} phext_range;

/* Rust: PositionedScroll - a scroll of text at a coordinate */
typedef struct phext_positioned_scroll {
    phext_coordinate coord;
    phext_buffer scroll;
} phext_positioned_scroll;

/* Rust: Vec<PositionedScroll>, and HashMap<Coordinate, String>.
 * One C type serves both roles, as it always has in this port: `items`
 * is the materialization - document order for a phokenize list,
 * coordinate order for a map - and, since F4, a coordinate hash index
 * serves phext_map_get so map lookups are O(1) probes instead of a
 * binary search over the materialization. The index is a cache only:
 * it never changes what any function returns, only how fast
 * phext_map_get finds it. */
typedef struct phext_scrolls {
    phext_positioned_scroll *items;
    size_t len;
    size_t cap;
    /* hash index over items: slot -> item position + 1 (0 = empty).
     * Built lazily by phext_map_get, invalidated by any library edit
     * it cannot track exactly. Owned by the list; released by
     * phext_scrolls_free. */
    size_t *index;
    size_t index_cap;
    int index_fresh;
} phext_scrolls;

void phext_scrolls_init(phext_scrolls *list);
void phext_scrolls_free(phext_scrolls *list);
void phext_scrolls_reset(phext_scrolls *list);
/* C idiom support: append a copy of (coord, scroll) to the list. */
phext_status phext_scrolls_push(phext_scrolls *list, phext_coordinate coord,
                                const unsigned char *scroll, size_t scroll_len);
/* C idiom support for Rust's HashMap operations: the list's items stay
 * sorted by coordinate (the iteration order, and implode's emit order),
 * while get runs through the coordinate hash index - get returns NULL
 * when absent, insert replaces or adds. */
const phext_buffer *phext_map_get(const phext_scrolls *map, phext_coordinate coord);
phext_status phext_map_insert(phext_scrolls *map, phext_coordinate coord,
                              const unsigned char *scroll, size_t scroll_len);

/* ----------------------------------------------------------------------------------------------------------
 * coordinate construction and conversion
 * ---------------------------------------------------------------------------------------------------------- */
phext_zcoordinate phext_zcoordinate_new(void); /* 1.1.1 */
phext_ycoordinate phext_ycoordinate_new(void); /* 1.1.1 */
phext_xcoordinate phext_xcoordinate_new(void); /* 1.1.1 */
phext_coordinate phext_coordinate_new(void);   /* 1.1.1/1.1.1/1.1.1 */
phext_coordinate phext_default_coordinate(void); /* Rust: default_coordinate() - same as _new */
phext_range phext_range_new(void);             /* both ends at the default coordinate */

/* Rust: PositionedScroll::new() - coord 1.1.1/1.1.1/1.1.1, empty scroll.
 * The returned scroll owns a heap buffer; free it with phext_buffer_free
 * on its scroll member. */
phext_positioned_scroll phext_positioned_scroll_new(void);

/* Rust: Coordinate::validate_coordinate - true (1) iff every component >= 1 */
int phext_coordinate_validate(phext_coordinate coord);

/* Rust: Eq / Ord. Ordering is lexicographic in declaration order:
 * library, shelf, series, collection, volume, book, chapter, section, scroll.
 * compare returns <0, 0, >0 like strcmp. */
int phext_coordinate_equal(phext_coordinate a, phext_coordinate b);
int phext_coordinate_compare(phext_coordinate a, phext_coordinate b);
/* Rust: Ord for PositionedScroll compares by coordinate only. */
int phext_positioned_scroll_compare(const phext_positioned_scroll *a, const phext_positioned_scroll *b);
/* C idiom support for Rust's derived Hash (whose values are not portable
 * across languages): a stable FNV-1a hash of the 9 components, suitable
 * for building your own hash tables. */
uint64_t phext_coordinate_hash(phext_coordinate coord);

/* Rust: Coordinate::to_string - canonical "z/y/x" form; EMPTY buffer when
 * the coordinate is invalid. */
phext_status phext_coordinate_to_string(phext_coordinate coord, phext_buffer *out);
/* Rust: Coordinate::to_urlencoded - "z;y;x" form; EMPTY when invalid. */
phext_status phext_coordinate_to_urlencoded(phext_coordinate coord, phext_buffer *out);
/* Rust: fmt::Display for Coordinate - formats UNCONDITIONALLY (an invalid
 * coordinate still prints, unlike to_string). Same for the three arms. */
phext_status phext_coordinate_display(phext_coordinate coord, phext_buffer *out);
phext_status phext_zcoordinate_display(phext_zcoordinate coord, phext_buffer *out);
phext_status phext_ycoordinate_display(phext_ycoordinate coord, phext_buffer *out);
phext_status phext_xcoordinate_display(phext_xcoordinate coord, phext_buffer *out);
/* Rust: fmt::Display for Range - "{start}-{end}", Display semantics. */
phext_status phext_range_display(phext_range range, phext_buffer *out);
/* Rust: fmt::Display for PositionedScroll - "{coord}: " + first 4 bytes of
 * the scroll. (Rust panics on a shorter scroll or a split UTF-8 sequence;
 * C prints what exists - PARITY.md D-5.) */
phext_status phext_positioned_scroll_display(const phext_positioned_scroll *ps, phext_buffer *out);

/* Rust: TryFrom<&str> for Coordinate - the STRICT parser.
 * Exactly three '/'-separated parts of exactly three '.'-separated
 * numbers each (";" is not accepted here). Returns PHEXT_EFORMAT for a
 * wrong segment shape, PHEXT_ENUMBER for a non-numeric or overflowing
 * component (Rust panics on those - PARITY.md D-2). A leading '+' is
 * accepted, matching Rust's usize parser. Components of 0 parse fine
 * and then fail phext_coordinate_validate, as in Rust. */
phext_status phext_coordinate_parse(const char *address, phext_coordinate *out);

/* Rust: to_coordinate - the LENIENT parser. Separators '.', '/' and ';'
 * assign components in order; missing components stay 1; extra trailing
 * components overwrite the scroll component; non-digit bytes are skipped;
 * 0 components are preserved. Never fails. Address is NUL-terminated. */
phext_coordinate phext_to_coordinate(const char *address);

/* ----------------------------------------------------------------------------------------------------------
 * coordinate movement (Rust: Coordinate::*_break)
 *
 * Each advances its own component by 1 (unbounded, never saturating) and
 * resets every lower component to 1.
 * ---------------------------------------------------------------------------------------------------------- */
void phext_coordinate_scroll_break(phext_coordinate *coord);
void phext_coordinate_section_break(phext_coordinate *coord);
void phext_coordinate_chapter_break(phext_coordinate *coord);
void phext_coordinate_book_break(phext_coordinate *coord);
void phext_coordinate_volume_break(phext_coordinate *coord);
void phext_coordinate_collection_break(phext_coordinate *coord);
void phext_coordinate_series_break(phext_coordinate *coord);
void phext_coordinate_shelf_break(phext_coordinate *coord);
void phext_coordinate_library_break(phext_coordinate *coord);

/* ----------------------------------------------------------------------------------------------------------
 * byte classification (Rust: is_phext_break; is_dimension_break is private
 * in Rust and exposed here because every C walker needs it)
 * ---------------------------------------------------------------------------------------------------------- */
int phext_is_phext_break(unsigned char byte);     /* all ten breaks, line break included */
int phext_is_dimension_break(unsigned char byte); /* the nine scroll-moving breaks only */
int phext_check_for_cowbell(const unsigned char *input, size_t len); /* Rust: check_for_cowbell */

/* ----------------------------------------------------------------------------------------------------------
 * the walker (Rust: get_subspace_coordinates)
 *
 * Finds the start and end offsets of the scroll at `target`:
 *   - when the document reaches `target`, [start, end) is that scroll's
 *     text (possibly empty) and *best is `target`;
 *   - otherwise start == end is where the scroll would go - just before
 *     the break that steps past `target`, or at the end of the document -
 *     and *best is the coordinate in effect there, so writing breaks from
 *     *best up to `target` and then the text places it correctly.
 * ---------------------------------------------------------------------------------------------------------- */
void phext_get_subspace_coordinates(const unsigned char *subspace, size_t len,
                                    phext_coordinate target,
                                    size_t *out_start, size_t *out_end,
                                    phext_coordinate *out_best);

/* ----------------------------------------------------------------------------------------------------------
 * document operations (Rust free functions; &str -> bytes + length,
 * String -> phext_buffer out, in the order of phext.rs)
 * ---------------------------------------------------------------------------------------------------------- */

/* Rust: fetch - the text of the scroll at `target` (empty when absent). */
phext_status phext_fetch(const unsigned char *input, size_t len,
                         phext_coordinate target, phext_buffer *out);
/* Rust: replace - set the scroll at `location`, creating the address
 * with fixup breaks when the document does not reach it yet. */
phext_status phext_replace(const unsigned char *input, size_t len,
                           phext_coordinate location,
                           const unsigned char *scroll, size_t scroll_len,
                           phext_buffer *out);
/* Rust: insert - splice `scroll` in at the END of the scroll at
 * `location` (extending it), creating the address when needed. */
phext_status phext_insert(const unsigned char *input, size_t len,
                          phext_coordinate location,
                          const unsigned char *scroll, size_t scroll_len,
                          phext_buffer *out);
/* Rust: remove - empty the scroll at `location`, then normalize. */
phext_status phext_remove(const unsigned char *input, size_t len,
                          phext_coordinate location, phext_buffer *out);
/* Rust: range_replace - replace everything from the start of the range's
 * start scroll through the end of its end scroll with `scroll`. */
phext_status phext_range_replace(const unsigned char *input, size_t len,
                                 phext_range range,
                                 const unsigned char *scroll, size_t scroll_len,
                                 phext_buffer *out);
/* Rust: next_scroll - split the first scroll off `input`, assuming it
 * starts at coordinate `start`. Returns the scroll (with the coordinate
 * where its text begins), the coordinate after it, and the remainder. */
phext_status phext_next_scroll(const unsigned char *input, size_t len,
                               phext_coordinate start,
                               phext_positioned_scroll *out_scroll,
                               phext_coordinate *out_next,
                               phext_buffer *out_remaining);
/* Rust: phokenize - tokenize the whole document into positioned scrolls,
 * in document order. Always yields at least one (possibly empty) scroll. */
phext_status phext_phokenize(const unsigned char *input, size_t len, phext_scrolls *out);
/* Rust: explode - phokenize into a coordinate -> scroll map (items
 * sorted here; lookups hash-indexed). */
phext_status phext_explode(const unsigned char *input, size_t len, phext_scrolls *out_map);
/* Rust: implode - serialize a coordinate -> scroll map back into a
 * document. Empty scrolls emit no text but still advance the position. */
phext_status phext_implode(const phext_scrolls *map, phext_buffer *out);
/* Rust: merge - per-scroll merge of two documents; scrolls at equal
 * coordinates concatenate (left text, then right text). */
phext_status phext_merge(const unsigned char *left, size_t left_len,
                         const unsigned char *right, size_t right_len,
                         phext_buffer *out);
/* Rust: subtract - the scrolls of `left` that have no content at the
 * same coordinate in `right` (a mask). */
phext_status phext_subtract(const unsigned char *left, size_t left_len,
                            const unsigned char *right, size_t right_len,
                            phext_buffer *out);
/* Rust: expand - every break becomes the next-higher break
 * (line->scroll->...->shelf->library; library breaks stay). */
phext_status phext_expand(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: contract - every break becomes the next-lower break
 * (library->shelf->...->scroll->line; line breaks stay). */
phext_status phext_contract(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: normalize - phokenize + re-serialize: drops empty scrolls and
 * re-emits canonical breaks. */
phext_status phext_normalize(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: create_summary - the text up to the first phext break (line
 * breaks included), plus "..." when anything was cut. */
phext_status phext_create_summary(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: navmap - an HTML <ul> linking every scroll under `urlbase`
 * (NUL-terminated), each entry showing coordinate and summary. */
phext_status phext_navmap(const char *urlbase, const unsigned char *input, size_t len,
                          phext_buffer *out);
/* Rust: textmap - "* {coord}: {summary}\n" for every scroll. */
phext_status phext_textmap(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: checksum - the xxh3-128 content hash of the bytes as 32
 * lowercase hex characters (plus a NUL), written into out_hex[33]. */
phext_status phext_checksum(const unsigned char *input, size_t len, char out_hex[33]);
/* Rust: manifest - the document with every scroll replaced by its checksum. */
phext_status phext_manifest(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: soundex_v1 - the document with every scroll replaced by its
 * phext soundex value (a decimal string). */
phext_status phext_soundex_v1(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: index - the document with every scroll replaced by its byte
 * offset in the original (a decimal string). */
phext_status phext_index(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: offset - the byte offset of the scroll at `coord`, or of the
 * last scroll before it; 0 when no scroll comes at or before it. */
phext_status phext_offset(const unsigned char *input, size_t len,
                          phext_coordinate coord, size_t *out_offset);

/* ----------------------------------------------------------------------------------------------------------
 * binary scrolls (libphext-rs 0.5.0: binary.rs, cargo feature `binary`)
 *
 * A binary scroll stores arbitrary bytes as text: the header line
 * PHEXT_BINARY_SCROLL_HEADER, one line break, then the payload in
 * RFC 4648 base64 (standard alphabet, padding required, no wrapping).
 * A scroll whose content begins with that header line IS a binary scroll
 * by definition; a prefix-matching scroll whose body is not strict
 * base64 is a malformed binary scroll.
 *
 * The ingestion rule (canonical, all ports): when non-UTF-8 data is
 * observed in an incoming scroll update, it is encoded with base64
 * verbatim. The byte-oriented entry points below never fail on non-UTF-8
 * payload data: valid UTF-8 is stored as ordinary text, anything else as
 * a binary scroll holding the base64 of the exact observed bytes, so the
 * matching fetch returns the original bytes exactly.
 * ---------------------------------------------------------------------------------------------------------- */

/* Rust: is_binary_scroll - true when the scroll carries the binary
 * header line (content begins with the header + line break). Decoding
 * success is a separate question - see phext_decode_scroll. */
int phext_is_binary_scroll(const unsigned char *scroll, size_t len);
/* Rust: encode_scroll - header line + base64 of the payload. */
phext_status phext_encode_scroll(const unsigned char *payload, size_t payload_len,
                                 phext_buffer *out);
/* Rust: decode_scroll - the payload of a binary scroll. Returns
 * PHEXT_ENONE when the scroll is not a binary scroll or its body is not
 * strict base64 (Rust: None); PHEXT_OK and the payload otherwise. The
 * strictness is the base64 crate's STANDARD engine: canonical padding
 * required, no whitespace, non-zero trailing bits rejected. */
phext_status phext_decode_scroll(const unsigned char *scroll, size_t len,
                                 phext_buffer *out);
/* Rust: fetch_binary - the bytes held at `target`. A well-formed binary
 * scroll decodes to its payload; any other scroll - plain text, a
 * malformed binary scroll, or no scroll at all - yields the scroll's
 * own bytes (empty when the coordinate is unoccupied). Total: fails
 * only on allocation failure. */
phext_status phext_fetch_binary(const unsigned char *input, size_t len,
                                phext_coordinate target, phext_buffer *out);
/* Rust: insert_binary / replace_binary - store the payload at the
 * location as a binary scroll, unconditionally (even when the payload
 * happens to be valid UTF-8). Same document-edit shapes as
 * phext_insert / phext_replace. */
phext_status phext_insert_binary(const unsigned char *input, size_t len,
                                 phext_coordinate location,
                                 const unsigned char *payload, size_t payload_len,
                                 phext_buffer *out);
phext_status phext_replace_binary(const unsigned char *input, size_t len,
                                  phext_coordinate location,
                                  const unsigned char *payload, size_t payload_len,
                                  phext_buffer *out);
/* Rust: insert_bytes / replace_bytes - the byte-oriented updates: the
 * payload is stored under the ingestion rule (UTF-8 as text, non-UTF-8
 * as a base64-verbatim binary scroll). */
phext_status phext_insert_bytes(const unsigned char *input, size_t len,
                                phext_coordinate location,
                                const unsigned char *payload, size_t payload_len,
                                phext_buffer *out);
phext_status phext_replace_bytes(const unsigned char *input, size_t len,
                                 phext_coordinate location,
                                 const unsigned char *payload, size_t payload_len,
                                 phext_buffer *out);
/* Rust: phokenize_bytes - the byte-level twin of phokenize: each
 * scroll's coordinate and raw bytes, segmentation identical to
 * phext_phokenize. In Rust the two functions differ because phokenize
 * requires valid UTF-8 input; this C API is byte-oriented throughout
 * (PARITY.md D-3), so the outputs coincide on every input. */
phext_status phext_phokenize_bytes(const unsigned char *input, size_t len,
                                   phext_scrolls *out);
/* Rust: ingest - ingest an externally supplied phext byte stream:
 * every scroll is observed as raw bytes; valid UTF-8 scrolls pass
 * through verbatim, any other scroll is stored as a binary scroll
 * holding the base64 of its exact bytes, so phext_fetch_binary at its
 * coordinate returns the original bytes. The result is the canonical
 * serialization (implode of the exploded map). Never fails on content;
 * only on allocation failure. */
phext_status phext_ingest(const unsigned char *input, size_t len, phext_buffer *out);

/* ----------------------------------------------------------------------------------------------------------
 * the xz seal (libphext-rs 0.5.0: seal.rs, cargo feature `xz`)
 *
 * Compression is a seal, not a working format: a finished phext may be
 * sealed - xz-compressed as a whole - and unsealing restores the exact
 * original bytes. The seal is a standard xz stream (liblzma) at preset
 * PHEXT_SEAL_PRESET with a CRC64 check; unsealing accepts any valid xz
 * stream, but the stream must be the WHOLE input - trailing bytes after
 * the stream end (even zero padding) are an error, exactly as in Rust.
 *
 * Build-time option (PARITY.md D-7): available only when phext.c was
 * compiled with PHEXT_WITH_XZ defined and linked with -llzma;
 * phext_seal_compiled() reports which build this is. Without it, the
 * four functions return PHEXT_ENOSEAL.
 * ---------------------------------------------------------------------------------------------------------- */

/* C idiom support: 1 when this build of the library has seal support
 * (PHEXT_WITH_XZ), 0 otherwise. */
int phext_seal_compiled(void);
/* Rust: seal_bytes - xz-seal raw bytes. (Rust's seal(&str) is the same
 * function on the text's bytes; this byte-oriented API serves both.) */
phext_status phext_seal_bytes(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: seal - as phext_seal_bytes; the two Rust entry points differ
 * only in input type (&str vs &[u8]), which C does not distinguish. */
phext_status phext_seal(const unsigned char *input, size_t len, phext_buffer *out);
/* Rust: unseal - restore the exact bytes a seal was made from.
 * PHEXT_EINVAL when the input is not a valid xz stream or has any
 * trailing bytes; PHEXT_ENOSEAL in a build without seal support. */
phext_status phext_unseal(const unsigned char *data, size_t len, phext_buffer *out);
/* Rust: unseal_string - unseal, then require valid UTF-8 (for content
 * that may carry non-UTF-8 scrolls, use phext_unseal + phext_ingest).
 * PHEXT_EINVAL when the unsealed bytes are not valid UTF-8. */
phext_status phext_unseal_string(const unsigned char *data, size_t len, phext_buffer *out);

#ifdef __cplusplus
}
#endif

#endif /* PHEXT_H */
