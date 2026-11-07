/* ----------------------------------------------------------------------------------------------------------
 * phext.h - Phext Buffer Library for C
 *
 * The C counterpart of libphext-rs (v0.4.1), the reference implementation of
 * phext in Rust. Every public capability of the Rust crate has a counterpart
 * here; the full mapping, including the handful of places where C idiom
 * forces a different shape (never different defined behaviour), lives in
 * PARITY.md and in the phext/ directory notes.
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

/* ----------------------------------------------------------------------------------------------------------
 * status codes (Rust: Result<_, PhextParseError> and panics, mapped to codes)
 * ---------------------------------------------------------------------------------------------------------- */
typedef enum phext_status {
    PHEXT_OK = 0,      /* success */
    PHEXT_ENOMEM,      /* an allocation failed; outputs are left empty */
    PHEXT_EFORMAT,     /* address does not have the 3x3 segment shape (Rust: Err(PhextParseError)) */
    PHEXT_ENUMBER      /* address component is not a number, or overflows size_t
                          (Rust: the strict parser PANICS here via expect(); C returns this) */
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

/* Rust: Vec<PositionedScroll>, and HashMap<Coordinate, String> in sorted form */
typedef struct phext_scrolls {
    phext_positioned_scroll *items;
    size_t len;
    size_t cap;
} phext_scrolls;

void phext_scrolls_init(phext_scrolls *list);
void phext_scrolls_free(phext_scrolls *list);
void phext_scrolls_reset(phext_scrolls *list);
/* C idiom support: append a copy of (coord, scroll) to the list. */
phext_status phext_scrolls_push(phext_scrolls *list, phext_coordinate coord,
                                const unsigned char *scroll, size_t scroll_len);
/* C idiom support for Rust's HashMap operations: the list is kept sorted
 * by coordinate; get returns NULL when absent, insert replaces or adds. */
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
/* Rust: explode - phokenize into a coordinate -> scroll map (sorted here). */
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

#ifdef __cplusplus
}
#endif

#endif /* PHEXT_H */
