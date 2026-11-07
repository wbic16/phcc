/* ----------------------------------------------------------------------------------------------------------
 * phext.c - Phext Buffer Library for C
 *
 * A literal port of libphext-rs v0.4.1 (src/phext.rs), the reference
 * implementation of phext in Rust. Function by function, the algorithms
 * below follow the Rust source - including its quirks - so that defined
 * behaviour is byte-identical. The mapping and the divergences (all of
 * them cases where Rust panics and C must not) are recorded in PARITY.md.
 *
 * The checksum is xxh3-128 with the default secret, ported from the
 * scalar const implementation in xxhash-rust 0.8.x (the crate
 * libphext-rs depends on), covering every length class.
 *
 * License: MIT
 * ---------------------------------------------------------------------------------------------------------- */

#include "phext.h"

#include <stdlib.h>
#include <string.h>

/* ----------------------------------------------------------------------------------------------------------
 * internal buffer plumbing
 * ---------------------------------------------------------------------------------------------------------- */

void phext_buffer_init(phext_buffer *buf) {
    buf->data = NULL;
    buf->len = 0;
    buf->cap = 0;
}

void phext_buffer_free(phext_buffer *buf) {
    free(buf->data);
    phext_buffer_init(buf);
}

void phext_buffer_reset(phext_buffer *buf) {
    buf->len = 0;
    if (buf->data != NULL) {
        buf->data[0] = 0;
    }
}

/* ensure room for at least `need` content bytes (plus the NUL) */
static phext_status buf_reserve(phext_buffer *buf, size_t need) {
    size_t cap;
    unsigned char *next;
    if (need <= buf->cap) {
        return PHEXT_OK;
    }
    cap = buf->cap != 0 ? buf->cap : 64;
    while (cap < need) {
        if (cap > ((size_t)-1) / 2) {
            cap = need;
            break;
        }
        cap *= 2;
    }
    next = (unsigned char *)realloc(buf->data, cap + 1);
    if (next == NULL) {
        return PHEXT_ENOMEM;
    }
    buf->data = next;
    buf->cap = cap;
    buf->data[buf->len] = 0;
    return PHEXT_OK;
}

static phext_status buf_append(phext_buffer *buf, const unsigned char *bytes, size_t count) {
    phext_status status;
    if (count == 0) {
        return PHEXT_OK;
    }
    status = buf_reserve(buf, buf->len + count);
    if (status != PHEXT_OK) {
        return status;
    }
    memcpy(buf->data + buf->len, bytes, count);
    buf->len += count;
    buf->data[buf->len] = 0;
    return PHEXT_OK;
}

static phext_status buf_append_byte(phext_buffer *buf, unsigned char byte) {
    return buf_append(buf, &byte, 1);
}

static phext_status buf_set(phext_buffer *buf, const unsigned char *bytes, size_t count) {
    phext_buffer_reset(buf);
    return buf_append(buf, bytes, count);
}

/* append the decimal form of `value` (Rust: format!("{}", value)) */
static phext_status buf_append_usize(phext_buffer *buf, size_t value) {
    char digits[32];
    size_t pos = sizeof(digits);
    if (value == 0) {
        return buf_append_byte(buf, (unsigned char)'0');
    }
    while (value > 0) {
        digits[--pos] = (char)('0' + (value % 10));
        value /= 10;
    }
    return buf_append(buf, (const unsigned char *)digits + pos, sizeof(digits) - pos);
}

/* ----------------------------------------------------------------------------------------------------------
 * positioned scroll lists
 * ---------------------------------------------------------------------------------------------------------- */

void phext_scrolls_init(phext_scrolls *list) {
    list->items = NULL;
    list->len = 0;
    list->cap = 0;
}

void phext_scrolls_reset(phext_scrolls *list) {
    size_t i;
    for (i = 0; i < list->len; i++) {
        phext_buffer_free(&list->items[i].scroll);
    }
    list->len = 0;
}

void phext_scrolls_free(phext_scrolls *list) {
    phext_scrolls_reset(list);
    free(list->items);
    phext_scrolls_init(list);
}

static phext_status scrolls_reserve(phext_scrolls *list, size_t need) {
    size_t cap;
    phext_positioned_scroll *next;
    if (need <= list->cap) {
        return PHEXT_OK;
    }
    cap = list->cap != 0 ? list->cap : 16;
    while (cap < need) {
        cap *= 2;
    }
    next = (phext_positioned_scroll *)realloc(list->items, cap * sizeof(phext_positioned_scroll));
    if (next == NULL) {
        return PHEXT_ENOMEM;
    }
    list->items = next;
    list->cap = cap;
    return PHEXT_OK;
}

phext_status phext_scrolls_push(phext_scrolls *list, phext_coordinate coord,
                                const unsigned char *scroll, size_t scroll_len) {
    phext_status status = scrolls_reserve(list, list->len + 1);
    phext_positioned_scroll *slot;
    if (status != PHEXT_OK) {
        return status;
    }
    slot = &list->items[list->len];
    slot->coord = coord;
    phext_buffer_init(&slot->scroll);
    status = buf_set(&slot->scroll, scroll, scroll_len);
    if (status != PHEXT_OK) {
        return status;
    }
    list->len += 1;
    return PHEXT_OK;
}

/* binary search: index of `coord`, or the insertion point; *found set on a hit */
static size_t map_locate(const phext_scrolls *map, phext_coordinate coord, int *found) {
    size_t lo = 0;
    size_t hi = map->len;
    *found = 0;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = phext_coordinate_compare(map->items[mid].coord, coord);
        if (cmp == 0) {
            *found = 1;
            return mid;
        } else if (cmp < 0) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo;
}

const phext_buffer *phext_map_get(const phext_scrolls *map, phext_coordinate coord) {
    int found;
    size_t at = map_locate(map, coord, &found);
    if (!found) {
        return NULL;
    }
    return &map->items[at].scroll;
}

phext_status phext_map_insert(phext_scrolls *map, phext_coordinate coord,
                              const unsigned char *scroll, size_t scroll_len) {
    int found;
    size_t at = map_locate(map, coord, &found);
    phext_status status;
    if (found) {
        return buf_set(&map->items[at].scroll, scroll, scroll_len);
    }
    status = scrolls_reserve(map, map->len + 1);
    if (status != PHEXT_OK) {
        return status;
    }
    if (at < map->len) {
        memmove(&map->items[at + 1], &map->items[at],
                (map->len - at) * sizeof(phext_positioned_scroll));
    }
    map->items[at].coord = coord;
    phext_buffer_init(&map->items[at].scroll);
    status = buf_set(&map->items[at].scroll, scroll, scroll_len);
    if (status != PHEXT_OK) {
        return status;
    }
    map->len += 1;
    return PHEXT_OK;
}

static phext_status scrolls_clone(const phext_scrolls *from, phext_scrolls *to) {
    size_t i;
    phext_scrolls_reset(to);
    for (i = 0; i < from->len; i++) {
        phext_status status = phext_scrolls_push(to, from->items[i].coord,
                                                 from->items[i].scroll.data,
                                                 from->items[i].scroll.len);
        if (status != PHEXT_OK) {
            return status;
        }
    }
    return PHEXT_OK;
}

static int positioned_scroll_qsort_cmp(const void *a, const void *b) {
    return phext_positioned_scroll_compare((const phext_positioned_scroll *)a,
                                           (const phext_positioned_scroll *)b);
}

static void scrolls_sort(phext_scrolls *list) {
    if (list->len > 1) {
        qsort(list->items, list->len, sizeof(phext_positioned_scroll),
              positioned_scroll_qsort_cmp);
    }
}

/* ----------------------------------------------------------------------------------------------------------
 * coordinates
 * ---------------------------------------------------------------------------------------------------------- */

phext_zcoordinate phext_zcoordinate_new(void) {
    phext_zcoordinate coord;
    coord.library = 1;
    coord.shelf = 1;
    coord.series = 1;
    return coord;
}

phext_ycoordinate phext_ycoordinate_new(void) {
    phext_ycoordinate coord;
    coord.collection = 1;
    coord.volume = 1;
    coord.book = 1;
    return coord;
}

phext_xcoordinate phext_xcoordinate_new(void) {
    phext_xcoordinate coord;
    coord.chapter = 1;
    coord.section = 1;
    coord.scroll = 1;
    return coord;
}

phext_coordinate phext_coordinate_new(void) {
    phext_coordinate coord;
    coord.z = phext_zcoordinate_new();
    coord.y = phext_ycoordinate_new();
    coord.x = phext_xcoordinate_new();
    return coord;
}

phext_coordinate phext_default_coordinate(void) {
    return phext_coordinate_new();
}

phext_range phext_range_new(void) {
    phext_range range;
    range.start = phext_coordinate_new();
    range.end = phext_coordinate_new();
    return range;
}

phext_positioned_scroll phext_positioned_scroll_new(void) {
    phext_positioned_scroll ps;
    ps.coord = phext_coordinate_new();
    phext_buffer_init(&ps.scroll);
    return ps;
}

static int validate_dimension_index(size_t index) {
    return index >= PHEXT_COORDINATE_MINIMUM;
}

int phext_coordinate_validate(phext_coordinate coord) {
    return validate_dimension_index(coord.z.library) &&
           validate_dimension_index(coord.z.shelf) &&
           validate_dimension_index(coord.z.series) &&
           validate_dimension_index(coord.y.collection) &&
           validate_dimension_index(coord.y.volume) &&
           validate_dimension_index(coord.y.book) &&
           validate_dimension_index(coord.x.chapter) &&
           validate_dimension_index(coord.x.section) &&
           validate_dimension_index(coord.x.scroll);
}

static int cmp_size(size_t a, size_t b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

int phext_coordinate_compare(phext_coordinate a, phext_coordinate b) {
    int cmp;
    if ((cmp = cmp_size(a.z.library, b.z.library)) != 0) return cmp;
    if ((cmp = cmp_size(a.z.shelf, b.z.shelf)) != 0) return cmp;
    if ((cmp = cmp_size(a.z.series, b.z.series)) != 0) return cmp;
    if ((cmp = cmp_size(a.y.collection, b.y.collection)) != 0) return cmp;
    if ((cmp = cmp_size(a.y.volume, b.y.volume)) != 0) return cmp;
    if ((cmp = cmp_size(a.y.book, b.y.book)) != 0) return cmp;
    if ((cmp = cmp_size(a.x.chapter, b.x.chapter)) != 0) return cmp;
    if ((cmp = cmp_size(a.x.section, b.x.section)) != 0) return cmp;
    return cmp_size(a.x.scroll, b.x.scroll);
}

int phext_coordinate_equal(phext_coordinate a, phext_coordinate b) {
    return phext_coordinate_compare(a, b) == 0;
}

int phext_positioned_scroll_compare(const phext_positioned_scroll *a,
                                    const phext_positioned_scroll *b) {
    return phext_coordinate_compare(a->coord, b->coord);
}

uint64_t phext_coordinate_hash(phext_coordinate coord) {
    /* FNV-1a over the nine components - a C-side utility (see phext.h) */
    uint64_t hash = (uint64_t)0xcbf29ce484222325ULL;
    size_t parts[9];
    size_t i;
    parts[0] = coord.z.library; parts[1] = coord.z.shelf; parts[2] = coord.z.series;
    parts[3] = coord.y.collection; parts[4] = coord.y.volume; parts[5] = coord.y.book;
    parts[6] = coord.x.chapter; parts[7] = coord.x.section; parts[8] = coord.x.scroll;
    for (i = 0; i < 9; i++) {
        uint64_t value = (uint64_t)parts[i];
        int byte;
        for (byte = 0; byte < 8; byte++) {
            hash ^= (value >> (byte * 8)) & 0xff;
            hash *= (uint64_t)0x100000001b3ULL;
        }
    }
    return hash;
}

/* "{a}.{b}.{c}" for one arm - Display semantics (unconditional) */
static phext_status format_arm(phext_buffer *out, size_t a, size_t b, size_t c) {
    phext_status status;
    phext_buffer_reset(out);
    if ((status = buf_append_usize(out, a)) != PHEXT_OK) return status;
    if ((status = buf_append_byte(out, PHEXT_ADDRESS_MICRO_BREAK)) != PHEXT_OK) return status;
    if ((status = buf_append_usize(out, b)) != PHEXT_OK) return status;
    if ((status = buf_append_byte(out, PHEXT_ADDRESS_MICRO_BREAK)) != PHEXT_OK) return status;
    return buf_append_usize(out, c);
}

/* "{z}{sep}{y}{sep}{x}" where sep is '/' (canonical) or ';' (urlencoded) */
static phext_status format_coordinate(phext_buffer *out, phext_coordinate coord,
                                      unsigned char sep, int validate) {
    phext_buffer z, y, x;
    phext_status status = PHEXT_OK;
    phext_buffer_init(&z);
    phext_buffer_init(&y);
    phext_buffer_init(&x);
    phext_buffer_reset(out);
    if (validate && !phext_coordinate_validate(coord)) {
        goto done; /* invalid: the empty string, as in Rust */
    }
    if ((status = format_arm(&z, coord.z.library, coord.z.shelf, coord.z.series)) != PHEXT_OK) goto done;
    if ((status = format_arm(&y, coord.y.collection, coord.y.volume, coord.y.book)) != PHEXT_OK) goto done;
    if ((status = format_arm(&x, coord.x.chapter, coord.x.section, coord.x.scroll)) != PHEXT_OK) goto done;
    if ((status = buf_append(out, z.data, z.len)) != PHEXT_OK) goto done;
    if ((status = buf_append_byte(out, sep)) != PHEXT_OK) goto done;
    if ((status = buf_append(out, y.data, y.len)) != PHEXT_OK) goto done;
    if ((status = buf_append_byte(out, sep)) != PHEXT_OK) goto done;
    status = buf_append(out, x.data, x.len);
done:
    phext_buffer_free(&z);
    phext_buffer_free(&y);
    phext_buffer_free(&x);
    return status;
}

phext_status phext_coordinate_to_string(phext_coordinate coord, phext_buffer *out) {
    return format_coordinate(out, coord, PHEXT_ADDRESS_MACRO_BREAK, 1);
}

phext_status phext_coordinate_to_urlencoded(phext_coordinate coord, phext_buffer *out) {
    return format_coordinate(out, coord, PHEXT_ADDRESS_MACRO_ALT, 1);
}

phext_status phext_coordinate_display(phext_coordinate coord, phext_buffer *out) {
    return format_coordinate(out, coord, PHEXT_ADDRESS_MACRO_BREAK, 0);
}

phext_status phext_zcoordinate_display(phext_zcoordinate coord, phext_buffer *out) {
    return format_arm(out, coord.library, coord.shelf, coord.series);
}

phext_status phext_ycoordinate_display(phext_ycoordinate coord, phext_buffer *out) {
    return format_arm(out, coord.collection, coord.volume, coord.book);
}

phext_status phext_xcoordinate_display(phext_xcoordinate coord, phext_buffer *out) {
    return format_arm(out, coord.chapter, coord.section, coord.scroll);
}

phext_status phext_range_display(phext_range range, phext_buffer *out) {
    phext_buffer left, right;
    phext_status status = PHEXT_OK;
    phext_buffer_init(&left);
    phext_buffer_init(&right);
    phext_buffer_reset(out);
    if ((status = phext_coordinate_display(range.start, &left)) != PHEXT_OK) goto done;
    if ((status = phext_coordinate_display(range.end, &right)) != PHEXT_OK) goto done;
    if ((status = buf_append(out, left.data, left.len)) != PHEXT_OK) goto done;
    if ((status = buf_append_byte(out, (unsigned char)'-')) != PHEXT_OK) goto done;
    status = buf_append(out, right.data, right.len);
done:
    phext_buffer_free(&left);
    phext_buffer_free(&right);
    return status;
}

phext_status phext_positioned_scroll_display(const phext_positioned_scroll *ps, phext_buffer *out) {
    phext_buffer head;
    phext_status status;
    size_t take;
    phext_buffer_init(&head);
    phext_buffer_reset(out);
    status = phext_coordinate_to_string(ps->coord, &head);
    if (status == PHEXT_OK) {
        status = buf_append(out, head.data, head.len);
    }
    if (status == PHEXT_OK) {
        status = buf_append(out, (const unsigned char *)": ", 2);
    }
    if (status == PHEXT_OK) {
        /* Rust slices scroll[..4] and panics when that is not a whole,
         * valid prefix; C prints up to 4 bytes and stops (PARITY.md D-5). */
        take = ps->scroll.len < 4 ? ps->scroll.len : 4;
        status = buf_append(out, ps->scroll.data, take);
    }
    phext_buffer_free(&head);
    return status;
}

const char *phext_parse_error_message(void) {
    return "Phext addresses are of the form LB.SF.SR/CN.VM.BK/CH.SN.SC";
}

/* parse one component with Rust's usize::from_str semantics:
 * optional leading '+', then one or more ASCII digits, value must fit.
 * returns 1 on success */
static int parse_usize_segment(const char *text, size_t len, size_t *out) {
    size_t i = 0;
    size_t value = 0;
    if (len == 0) {
        return 0;
    }
    if (text[0] == '+') {
        i = 1;
        if (len == 1) {
            return 0;
        }
    }
    for (; i < len; i++) {
        unsigned digit;
        if (text[i] < '0' || text[i] > '9') {
            return 0;
        }
        digit = (unsigned)(text[i] - '0');
        if (value > (((size_t)-1) - digit) / 10) {
            return 0; /* overflow: Rust's parse fails and TryFrom panics */
        }
        value = value * 10 + digit;
    }
    *out = value;
    return 1;
}

phext_status phext_coordinate_parse(const char *address, phext_coordinate *out) {
    /* Rust: split_on(address, '/') must give 3 parts, each split_on('.')
     * must give 3 segments, each segment must parse as usize. */
    const char *macro[3];
    size_t macro_len[3];
    size_t values[9];
    size_t length = strlen(address);
    size_t start = 0;
    size_t part = 0;
    size_t i;
    int value_index = 0;

    for (i = 0; i <= length; i++) {
        if (i == length || address[i] == '/') {
            if (part >= 3) {
                return PHEXT_EFORMAT;
            }
            macro[part] = address + start;
            macro_len[part] = i - start;
            part += 1;
            start = i + 1;
        }
    }
    if (part != 3) {
        return PHEXT_EFORMAT;
    }

    for (part = 0; part < 3; part++) {
        const char *text = macro[part];
        size_t part_len = macro_len[part];
        size_t seg_start = 0;
        size_t seg = 0;
        for (i = 0; i <= part_len; i++) {
            if (i == part_len || text[i] == '.') {
                if (seg >= 3) {
                    return PHEXT_EFORMAT;
                }
                if (!parse_usize_segment(text + seg_start, i - seg_start, &values[value_index])) {
                    return PHEXT_ENUMBER;
                }
                value_index += 1;
                seg += 1;
                seg_start = i + 1;
            }
        }
        if (seg != 3) {
            return PHEXT_EFORMAT;
        }
    }

    out->z.library = values[0];
    out->z.shelf = values[1];
    out->z.series = values[2];
    out->y.collection = values[3];
    out->y.volume = values[4];
    out->y.book = values[5];
    out->x.chapter = values[6];
    out->x.section = values[7];
    out->x.scroll = values[8];
    return PHEXT_OK;
}

phext_coordinate phext_to_coordinate(const char *address) {
    /* the lenient parser, ported literally from phext.rs::to_coordinate */
    phext_coordinate result = phext_default_coordinate();
    unsigned int index = 0;
    uint64_t value = 0;
    const uint64_t exp = 10;
    const unsigned char *p;

    for (p = (const unsigned char *)address; *p != 0; p++) {
        unsigned char byte = *p;
        if (byte == PHEXT_ADDRESS_MICRO_BREAK ||
            byte == PHEXT_ADDRESS_MACRO_BREAK ||
            byte == PHEXT_ADDRESS_MACRO_ALT) {
            switch (index) {
                case 1: result.z.library = (size_t)value; index += 1; break;
                case 2: result.z.shelf = (size_t)value; index += 1; break;
                case 3: result.z.series = (size_t)value; index += 1; break;
                case 4: result.y.collection = (size_t)value; index += 1; break;
                case 5: result.y.volume = (size_t)value; index += 1; break;
                case 6: result.y.book = (size_t)value; index += 1; break;
                case 7: result.x.chapter = (size_t)value; index += 1; break;
                case 8: result.x.section = (size_t)value; index += 1; break;
                default: break;
            }
            value = 0;
        }
        if (byte >= 0x30 && byte <= 0x39) {
            value = exp * value + (uint64_t)(byte - 0x30);
            if (index == 0) {
                index = 1;
            }
        }
    }

    if (index > 0) {
        result.x.scroll = (size_t)value;
    }
    return result;
}

/* ----------------------------------------------------------------------------------------------------------
 * coordinate movement (Rust: Coordinate::*_break; advance is a plain +1,
 * unbounded since 0.4.0 - wrapping at size_t overflow matches Rust's
 * release-build usize semantics)
 * ---------------------------------------------------------------------------------------------------------- */

void phext_coordinate_scroll_break(phext_coordinate *coord) {
    coord->x.scroll += 1;
}

void phext_coordinate_section_break(phext_coordinate *coord) {
    coord->x.section += 1;
    coord->x.scroll = 1;
}

void phext_coordinate_chapter_break(phext_coordinate *coord) {
    coord->x.chapter += 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_book_break(phext_coordinate *coord) {
    coord->y.book += 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_volume_break(phext_coordinate *coord) {
    coord->y.volume += 1;
    coord->y.book = 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_collection_break(phext_coordinate *coord) {
    coord->y.collection += 1;
    coord->y.volume = 1;
    coord->y.book = 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_series_break(phext_coordinate *coord) {
    coord->z.series += 1;
    coord->y.collection = 1;
    coord->y.volume = 1;
    coord->y.book = 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_shelf_break(phext_coordinate *coord) {
    coord->z.shelf += 1;
    coord->z.series = 1;
    coord->y.collection = 1;
    coord->y.volume = 1;
    coord->y.book = 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

void phext_coordinate_library_break(phext_coordinate *coord) {
    coord->z.library += 1;
    coord->z.shelf = 1;
    coord->z.series = 1;
    coord->y.collection = 1;
    coord->y.volume = 1;
    coord->y.book = 1;
    coord->x.chapter = 1;
    coord->x.section = 1;
    coord->x.scroll = 1;
}

/* ----------------------------------------------------------------------------------------------------------
 * byte classification
 * ---------------------------------------------------------------------------------------------------------- */

int phext_is_dimension_break(unsigned char byte) {
    return byte == PHEXT_SCROLL_BREAK ||
           byte == PHEXT_SECTION_BREAK ||
           byte == PHEXT_CHAPTER_BREAK ||
           byte == PHEXT_BOOK_BREAK ||
           byte == PHEXT_VOLUME_BREAK ||
           byte == PHEXT_COLLECTION_BREAK ||
           byte == PHEXT_SERIES_BREAK ||
           byte == PHEXT_SHELF_BREAK ||
           byte == PHEXT_LIBRARY_BREAK;
}

int phext_is_phext_break(unsigned char byte) {
    return byte == PHEXT_LINE_BREAK || phext_is_dimension_break(byte);
}

int phext_check_for_cowbell(const unsigned char *input, size_t len) {
    size_t i;
    for (i = 0; i < len; i++) {
        if (input[i] == PHEXT_MORE_COWBELL) {
            return 1;
        }
    }
    return 0;
}

/* advance `location` across one dimension break (Rust: apply_break) */
static void apply_break(phext_coordinate *location, unsigned char byte) {
    if (byte == PHEXT_SCROLL_BREAK)     phext_coordinate_scroll_break(location);
    if (byte == PHEXT_SECTION_BREAK)    phext_coordinate_section_break(location);
    if (byte == PHEXT_CHAPTER_BREAK)    phext_coordinate_chapter_break(location);
    if (byte == PHEXT_BOOK_BREAK)       phext_coordinate_book_break(location);
    if (byte == PHEXT_VOLUME_BREAK)     phext_coordinate_volume_break(location);
    if (byte == PHEXT_COLLECTION_BREAK) phext_coordinate_collection_break(location);
    if (byte == PHEXT_SERIES_BREAK)     phext_coordinate_series_break(location);
    if (byte == PHEXT_SHELF_BREAK)      phext_coordinate_shelf_break(location);
    if (byte == PHEXT_LIBRARY_BREAK)    phext_coordinate_library_break(location);
}

/* ----------------------------------------------------------------------------------------------------------
 * the walker (Rust: get_subspace_coordinates) - ported literally
 * ---------------------------------------------------------------------------------------------------------- */

void phext_get_subspace_coordinates(const unsigned char *subspace, size_t len,
                                    phext_coordinate target,
                                    size_t *out_start, size_t *out_end,
                                    phext_coordinate *out_best) {
    phext_coordinate walker = phext_default_coordinate();
    phext_coordinate best = phext_default_coordinate();
    int found = 0;
    size_t found_at = 0;
    const size_t max = len;
    size_t position = 0;
    int moved = 1;

    for (;;) {
        /* `walker` is the coordinate in effect at `position` */
        if (moved && !found) {
            if (phext_coordinate_equal(walker, target)) {
                found = 1;
                found_at = position;
                best = walker;
            } else if (phext_coordinate_compare(walker, target) < 0) {
                best = walker;
            } else {
                /* before the first scroll: target sorts ahead of the default */
                *out_start = position;
                *out_end = position;
                *out_best = best;
                return;
            }
            moved = 0;
        }
        if (position == max) {
            break;
        }

        {
            unsigned char next = subspace[position];
            if (phext_is_dimension_break(next)) {
                apply_break(&walker, next);
                moved = 1;
                if (phext_coordinate_compare(walker, target) > 0) {
                    if (found) {
                        *out_start = found_at;
                        *out_end = position;
                        *out_best = best;
                    } else {
                        *out_start = position;
                        *out_end = position;
                        *out_best = best;
                    }
                    return;
                }
                /* defensive, as in Rust: a break that does not move the
                 * walker would leave the scroll text after the break */
                if (found && found_at == position) {
                    found_at = position + 1;
                }
            }
        }
        position += 1;
    }

    if (found) {
        *out_start = found_at;
        *out_end = max;
        *out_best = best;
    } else {
        *out_start = max;
        *out_end = max;
        *out_best = best;
    }
}

/* ----------------------------------------------------------------------------------------------------------
 * xxh3-128 (Rust: xxhash_rust::xxh3::xxh3_128, used by phext::checksum)
 *
 * Scalar port of the const implementation in xxhash-rust 0.8.x
 * (const_xxh3.rs), seed 0 with the default secret - the only form
 * libphext uses. 64x64->128 multiplication is done with 32-bit halves
 * so the code does not need __int128 (which phcc does not provide).
 * ---------------------------------------------------------------------------------------------------------- */

#define XXH_PRIME32_1 ((uint64_t)0x9E3779B1ULL)
#define XXH_PRIME32_2 ((uint64_t)0x85EBCA77ULL)
#define XXH_PRIME32_3 ((uint64_t)0xC2B2AE3DULL)
#define XXH_PRIME64_1 ((uint64_t)0x9E3779B185EBCA87ULL)
#define XXH_PRIME64_2 ((uint64_t)0xC2B2AE3D27D4EB4FULL)
#define XXH_PRIME64_3 ((uint64_t)0x165667B19E3779F9ULL)
#define XXH_PRIME64_4 ((uint64_t)0x85EBCA77C2B2AE63ULL)
#define XXH_PRIME64_5 ((uint64_t)0x27D4EB2F165667C5ULL)

#define XXH3_SECRET_SIZE_MIN 136
#define XXH3_MID_SIZE_MAX 240
#define XXH3_STRIPE_LEN 64
#define XXH3_ACC_NB 8
#define XXH3_SECRET_CONSUME_RATE 8
#define XXH3_SECRET_MERGEACCS_START 11
#define XXH3_SECRET_LASTACC_START 7

static const unsigned char xxh3_default_secret[192] = {
    0xb8, 0xfe, 0x6c, 0x39, 0x23, 0xa4, 0x4b, 0xbe, 0x7c, 0x01, 0x81, 0x2c, 0xf7, 0x21, 0xad, 0x1c,
    0xde, 0xd4, 0x6d, 0xe9, 0x83, 0x90, 0x97, 0xdb, 0x72, 0x40, 0xa4, 0xa4, 0xb7, 0xb3, 0x67, 0x1f,
    0xcb, 0x79, 0xe6, 0x4e, 0xcc, 0xc0, 0xe5, 0x78, 0x82, 0x5a, 0xd0, 0x7d, 0xcc, 0xff, 0x72, 0x21,
    0xb8, 0x08, 0x46, 0x74, 0xf7, 0x43, 0x24, 0x8e, 0xe0, 0x35, 0x90, 0xe6, 0x81, 0x3a, 0x26, 0x4c,
    0x3c, 0x28, 0x52, 0xbb, 0x91, 0xc3, 0x00, 0xcb, 0x88, 0xd0, 0x65, 0x8b, 0x1b, 0x53, 0x2e, 0xa3,
    0x71, 0x64, 0x48, 0x97, 0xa2, 0x0d, 0xf9, 0x4e, 0x38, 0x19, 0xef, 0x46, 0xa9, 0xde, 0xac, 0xd8,
    0xa8, 0xfa, 0x76, 0x3f, 0xe3, 0x9c, 0x34, 0x3f, 0xf9, 0xdc, 0xbb, 0xc7, 0xc7, 0x0b, 0x4f, 0x1d,
    0x8a, 0x51, 0xe0, 0x4b, 0xcd, 0xb4, 0x59, 0x31, 0xc8, 0x9f, 0x7e, 0xc9, 0xd9, 0x78, 0x73, 0x64,
    0xea, 0xc5, 0xac, 0x83, 0x34, 0xd3, 0xeb, 0xc3, 0xc5, 0x81, 0xa0, 0xff, 0xfa, 0x13, 0x63, 0xeb,
    0x17, 0x0d, 0xdd, 0x51, 0xb7, 0xf0, 0xda, 0x49, 0xd3, 0x16, 0x55, 0x26, 0x29, 0xd4, 0x68, 0x9e,
    0x2b, 0x16, 0xbe, 0x58, 0x7d, 0x47, 0xa1, 0xfc, 0x8f, 0xf8, 0xb8, 0xd1, 0x7a, 0xd0, 0x31, 0xce,
    0x45, 0xcb, 0x3a, 0x8f, 0x95, 0x16, 0x04, 0x28, 0xaf, 0xd7, 0xfb, 0xca, 0xbb, 0x4b, 0x40, 0x7e
};

static uint32_t xxh_read32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint64_t xxh_read64(const unsigned char *p) {
    return (uint64_t)xxh_read32(p) | ((uint64_t)xxh_read32(p + 4) << 32);
}

static uint64_t xxh_swap64(uint64_t value) {
    return ((value & (uint64_t)0x00000000000000ffULL) << 56) |
           ((value & (uint64_t)0x000000000000ff00ULL) << 40) |
           ((value & (uint64_t)0x0000000000ff0000ULL) << 24) |
           ((value & (uint64_t)0x00000000ff000000ULL) << 8) |
           ((value & (uint64_t)0x000000ff00000000ULL) >> 8) |
           ((value & (uint64_t)0x0000ff0000000000ULL) >> 24) |
           ((value & (uint64_t)0x00ff000000000000ULL) >> 40) |
           ((value & (uint64_t)0xff00000000000000ULL) >> 56);
}

static uint32_t xxh_swap32(uint32_t value) {
    return ((value & 0x000000ffU) << 24) | ((value & 0x0000ff00U) << 8) |
           ((value & 0x00ff0000U) >> 8) | ((value & 0xff000000U) >> 24);
}

/* full 64x64 -> 128 product via 32-bit halves (no __int128 needed) */
static void xxh_mul64_to128(uint64_t left, uint64_t right, uint64_t *out_lo, uint64_t *out_hi) {
    uint64_t lo_lo = (uint64_t)(uint32_t)left * (uint32_t)right;
    uint64_t lo_hi = (uint64_t)(uint32_t)left * (right >> 32);
    uint64_t hi_lo = (uint64_t)(left >> 32) * (uint32_t)right;
    uint64_t hi_hi = (uint64_t)(left >> 32) * (right >> 32);
    /* cross gathers the middle terms; it cannot overflow (each term is
     * bounded so the sum stays below 2^64), and its high half is exactly
     * the carry chain of the textbook 32-bit-half multiplication */
    uint64_t cross = (lo_lo >> 32) + (lo_hi & (uint64_t)0xffffffffULL) + hi_lo;
    *out_lo = left * right; /* the wrapping low half is exact */
    *out_hi = hi_hi + (lo_hi >> 32) + (cross >> 32);
}

static uint64_t xxh_mul128_fold64(uint64_t left, uint64_t right) {
    uint64_t lo, hi;
    xxh_mul64_to128(left, right, &lo, &hi);
    return lo ^ hi;
}

static uint64_t xxh_xorshift64(uint64_t value, unsigned shift) {
    return value ^ (value >> shift);
}

/* XXH3 avalanche */
static uint64_t xxh3_avalanche(uint64_t value) {
    value = xxh_xorshift64(value, 37);
    value *= (uint64_t)0x165667919E3779F9ULL;
    return xxh_xorshift64(value, 32);
}

/* XXH64 avalanche */
static uint64_t xxh64_avalanche(uint64_t value) {
    value ^= value >> 33;
    value *= XXH_PRIME64_2;
    value ^= value >> 29;
    value *= XXH_PRIME64_3;
    value ^= value >> 32;
    return value;
}

static uint64_t xxh_mix16b(const unsigned char *input, size_t input_offset,
                           const unsigned char *secret, size_t secret_offset,
                           uint64_t seed) {
    uint64_t input_lo = xxh_read64(input + input_offset) ^
                        (xxh_read64(secret + secret_offset) + seed);
    uint64_t input_hi = xxh_read64(input + input_offset + 8) ^
                        (xxh_read64(secret + secret_offset + 8) - seed);
    return xxh_mul128_fold64(input_lo, input_hi);
}

typedef struct xxh_acc2 {
    uint64_t a0;
    uint64_t a1;
} xxh_acc2;

static xxh_acc2 xxh_mix32b(xxh_acc2 acc,
                           const unsigned char *input1, size_t input1_off,
                           const unsigned char *input2, size_t input2_off,
                           const unsigned char *secret, size_t secret_offset,
                           uint64_t seed) {
    acc.a0 += xxh_mix16b(input1, input1_off, secret, secret_offset, seed);
    acc.a0 ^= xxh_read64(input2 + input2_off) + xxh_read64(input2 + input2_off + 8);
    acc.a1 += xxh_mix16b(input2, input2_off, secret, secret_offset + 16, seed);
    acc.a1 ^= xxh_read64(input1 + input1_off) + xxh_read64(input1 + input1_off + 8);
    return acc;
}

typedef struct xxh_u128 {
    uint64_t lo;
    uint64_t hi;
} xxh_u128;

static xxh_u128 xxh3_128_1to3(const unsigned char *input, size_t len) {
    uint32_t c1 = input[0];
    uint32_t c2 = input[len >> 1];
    uint32_t c3 = input[len - 1];
    uint32_t input_lo = (c1 << 16) | (c2 << 24) | c3 | ((uint32_t)len << 8);
    uint32_t swapped = xxh_swap32(input_lo);
    uint32_t input_hi = (swapped << 13) | (swapped >> 19); /* rotate_left(13) */
    uint64_t flip_lo = (uint64_t)(xxh_read32(xxh3_default_secret + 0) ^
                                  xxh_read32(xxh3_default_secret + 4));
    uint64_t flip_hi = (uint64_t)(xxh_read32(xxh3_default_secret + 8) ^
                                  xxh_read32(xxh3_default_secret + 12));
    xxh_u128 result;
    result.lo = xxh64_avalanche((uint64_t)input_lo ^ flip_lo);
    result.hi = xxh64_avalanche((uint64_t)input_hi ^ flip_hi);
    return result;
}

static xxh_u128 xxh3_128_4to8(const unsigned char *input, size_t len) {
    uint32_t lo32 = xxh_read32(input);
    uint32_t hi32 = xxh_read32(input + len - 4);
    uint64_t input64 = (uint64_t)lo32 + ((uint64_t)hi32 << 32);
    uint64_t flip = xxh_read64(xxh3_default_secret + 16) ^ xxh_read64(xxh3_default_secret + 24);
    uint64_t keyed = input64 ^ flip;
    uint64_t mlo, mhi;
    xxh_u128 result;
    xxh_mul64_to128(keyed, XXH_PRIME64_1 + ((uint64_t)len << 2), &mlo, &mhi);
    mhi += mlo << 1;
    mlo ^= mhi >> 3;
    mlo = xxh_xorshift64(mlo, 35) * (uint64_t)0x9FB21C651E98DF25ULL;
    mlo = xxh_xorshift64(mlo, 28);
    mhi = xxh3_avalanche(mhi);
    result.lo = mlo;
    result.hi = mhi;
    return result;
}

static xxh_u128 xxh3_128_9to16(const unsigned char *input, size_t len) {
    uint64_t flip_lo = xxh_read64(xxh3_default_secret + 32) ^ xxh_read64(xxh3_default_secret + 40);
    uint64_t flip_hi = xxh_read64(xxh3_default_secret + 48) ^ xxh_read64(xxh3_default_secret + 56);
    uint64_t input_lo = xxh_read64(input);
    uint64_t input_hi = xxh_read64(input + len - 8);
    uint64_t mul_low, mul_high;
    uint64_t result_low, result_hi;
    xxh_u128 result;
    xxh_mul64_to128(input_lo ^ input_hi ^ flip_lo, XXH_PRIME64_1, &mul_low, &mul_high);
    mul_low += ((uint64_t)len - 1) << 54;
    input_hi ^= flip_hi;
    mul_high += input_hi + (uint64_t)(uint32_t)input_hi * (XXH_PRIME32_2 - 1);
    mul_low ^= xxh_swap64(mul_high);
    xxh_mul64_to128(mul_low, XXH_PRIME64_2, &result_low, &result_hi);
    result_hi += mul_high * XXH_PRIME64_2;
    result.lo = xxh3_avalanche(result_low);
    result.hi = xxh3_avalanche(result_hi);
    return result;
}

static xxh_u128 xxh3_128_0to16(const unsigned char *input, size_t len) {
    if (len > 8) {
        return xxh3_128_9to16(input, len);
    }
    if (len >= 4) {
        return xxh3_128_4to8(input, len);
    }
    if (len > 0) {
        return xxh3_128_1to3(input, len);
    }
    {
        uint64_t flip_lo = xxh_read64(xxh3_default_secret + 64) ^ xxh_read64(xxh3_default_secret + 72);
        uint64_t flip_hi = xxh_read64(xxh3_default_secret + 80) ^ xxh_read64(xxh3_default_secret + 88);
        xxh_u128 result;
        result.lo = xxh64_avalanche(flip_lo);
        result.hi = xxh64_avalanche(flip_hi);
        return result;
    }
}

static xxh_u128 xxh3_128_17to128(const unsigned char *input, size_t len) {
    xxh_acc2 acc;
    uint64_t result_lo, result_hi;
    xxh_u128 result;
    acc.a0 = (uint64_t)len * XXH_PRIME64_1;
    acc.a1 = 0;
    if (len > 32) {
        if (len > 64) {
            if (len > 96) {
                acc = xxh_mix32b(acc, input, 48, input, len - 64, xxh3_default_secret, 96, 0);
            }
            acc = xxh_mix32b(acc, input, 32, input, len - 48, xxh3_default_secret, 64, 0);
        }
        acc = xxh_mix32b(acc, input, 16, input, len - 32, xxh3_default_secret, 32, 0);
    }
    acc = xxh_mix32b(acc, input, 0, input, len - 16, xxh3_default_secret, 0, 0);
    result_lo = acc.a0 + acc.a1;
    result_hi = acc.a0 * XXH_PRIME64_1 + acc.a1 * XXH_PRIME64_4 + (uint64_t)len * XXH_PRIME64_2;
    result.lo = xxh3_avalanche(result_lo);
    result.hi = 0 - xxh3_avalanche(result_hi);
    return result;
}

static xxh_u128 xxh3_128_129to240(const unsigned char *input, size_t len) {
    const size_t start_offset = 3;
    size_t nb_rounds = len / 32;
    xxh_acc2 acc;
    uint64_t result_lo, result_hi;
    xxh_u128 result;
    size_t idx;
    acc.a0 = (uint64_t)len * XXH_PRIME64_1;
    acc.a1 = 0;
    for (idx = 0; idx < 4; idx++) {
        acc = xxh_mix32b(acc, input, 32 * idx, input, 32 * idx + 16,
                         xxh3_default_secret, 32 * idx, 0);
    }
    acc.a0 = xxh3_avalanche(acc.a0);
    acc.a1 = xxh3_avalanche(acc.a1);
    for (; idx < nb_rounds; idx++) {
        acc = xxh_mix32b(acc, input, 32 * idx, input, 32 * idx + 16,
                         xxh3_default_secret, start_offset + 32 * (idx - 4), 0);
    }
    /* last bytes, with seed negated in Rust (0 - seed == 0 here) */
    acc = xxh_mix32b(acc, input, len - 16, input, len - 32,
                     xxh3_default_secret, XXH3_SECRET_SIZE_MIN - 17 - 16, 0);
    result_lo = acc.a0 + acc.a1;
    result_hi = acc.a0 * XXH_PRIME64_1 + acc.a1 * XXH_PRIME64_4 + (uint64_t)len * XXH_PRIME64_2;
    result.lo = xxh3_avalanche(result_lo);
    result.hi = 0 - xxh3_avalanche(result_hi);
    return result;
}

static void xxh_accumulate_512(uint64_t acc[XXH3_ACC_NB],
                               const unsigned char *input, size_t input_offset,
                               const unsigned char *secret, size_t secret_offset) {
    int idx;
    for (idx = 0; idx < XXH3_ACC_NB; idx++) {
        uint64_t data_val = xxh_read64(input + input_offset + 8 * (size_t)idx);
        uint64_t data_key = data_val ^ xxh_read64(secret + secret_offset + 8 * (size_t)idx);
        acc[idx ^ 1] += data_val;
        acc[idx] += (uint64_t)(uint32_t)data_key * (uint64_t)(uint32_t)(data_key >> 32);
    }
}

static void xxh_scramble_acc(uint64_t acc[XXH3_ACC_NB],
                             const unsigned char *secret, size_t secret_offset) {
    int idx;
    for (idx = 0; idx < XXH3_ACC_NB; idx++) {
        uint64_t key = xxh_read64(secret + secret_offset + 8 * (size_t)idx);
        uint64_t value = xxh_xorshift64(acc[idx], 47);
        value ^= key;
        acc[idx] = value * XXH_PRIME32_1;
    }
}

static uint64_t xxh_merge_accs(const uint64_t acc[XXH3_ACC_NB],
                               const unsigned char *secret, size_t secret_offset,
                               uint64_t result) {
    int idx;
    for (idx = 0; idx < 4; idx++) {
        result += xxh_mul128_fold64(acc[idx * 2] ^ xxh_read64(secret + secret_offset + (size_t)idx * 16),
                                    acc[idx * 2 + 1] ^ xxh_read64(secret + secret_offset + (size_t)idx * 16 + 8));
    }
    return xxh3_avalanche(result);
}

static xxh_u128 xxh3_128_long(const unsigned char *input, size_t len) {
    static const uint64_t initial_acc[XXH3_ACC_NB] = {
        XXH_PRIME32_3, XXH_PRIME64_1, XXH_PRIME64_2, XXH_PRIME64_3,
        XXH_PRIME64_4, XXH_PRIME32_2, XXH_PRIME64_5, XXH_PRIME32_1
    };
    uint64_t acc[XXH3_ACC_NB];
    const size_t nb_stripes_per_block = (192 - XXH3_STRIPE_LEN) / XXH3_SECRET_CONSUME_RATE; /* 16 */
    const size_t block_len = XXH3_STRIPE_LEN * nb_stripes_per_block;                        /* 1024 */
    size_t nb_blocks = (len - 1) / block_len;
    size_t block, stripe, nb_stripes;
    xxh_u128 result;

    memcpy(acc, initial_acc, sizeof(acc));
    for (block = 0; block < nb_blocks; block++) {
        for (stripe = 0; stripe < nb_stripes_per_block; stripe++) {
            xxh_accumulate_512(acc, input, block * block_len + stripe * XXH3_STRIPE_LEN,
                               xxh3_default_secret, stripe * XXH3_SECRET_CONSUME_RATE);
        }
        xxh_scramble_acc(acc, xxh3_default_secret, 192 - XXH3_STRIPE_LEN);
    }
    nb_stripes = ((len - 1) - block_len * nb_blocks) / XXH3_STRIPE_LEN;
    for (stripe = 0; stripe < nb_stripes; stripe++) {
        xxh_accumulate_512(acc, input, nb_blocks * block_len + stripe * XXH3_STRIPE_LEN,
                           xxh3_default_secret, stripe * XXH3_SECRET_CONSUME_RATE);
    }
    /* last stripe: the final 64 bytes, wherever the stripes stopped */
    xxh_accumulate_512(acc, input, len - XXH3_STRIPE_LEN,
                       xxh3_default_secret, 192 - XXH3_STRIPE_LEN - XXH3_SECRET_LASTACC_START);

    result.lo = xxh_merge_accs(acc, xxh3_default_secret, XXH3_SECRET_MERGEACCS_START,
                               (uint64_t)len * XXH_PRIME64_1);
    result.hi = xxh_merge_accs(acc, xxh3_default_secret,
                               192 - XXH3_ACC_NB * 8 - XXH3_SECRET_MERGEACCS_START,
                               ~((uint64_t)len * XXH_PRIME64_2));
    return result;
}

static xxh_u128 xxh3_128(const unsigned char *input, size_t len) {
    if (len <= 16) {
        return xxh3_128_0to16(input, len);
    }
    if (len <= 128) {
        return xxh3_128_17to128(input, len);
    }
    if (len <= XXH3_MID_SIZE_MAX) {
        return xxh3_128_129to240(input, len);
    }
    return xxh3_128_long(input, len);
}

phext_status phext_checksum(const unsigned char *input, size_t len, char out_hex[33]) {
    static const char hexdigits[] = "0123456789abcdef";
    xxh_u128 hash = xxh3_128(input, len);
    uint64_t halves[2];
    int h, nibble;
    halves[0] = hash.hi;
    halves[1] = hash.lo;
    for (h = 0; h < 2; h++) {
        for (nibble = 0; nibble < 16; nibble++) {
            out_hex[h * 16 + nibble] = hexdigits[(halves[h] >> (60 - 4 * nibble)) & 0xf];
        }
    }
    out_hex[32] = 0;
    return PHEXT_OK;
}

/* ----------------------------------------------------------------------------------------------------------
 * document operations - each a literal port of its phext.rs counterpart
 * ---------------------------------------------------------------------------------------------------------- */

phext_status phext_fetch(const unsigned char *input, size_t len,
                         phext_coordinate target, phext_buffer *out) {
    size_t start, end;
    phext_coordinate best;
    phext_get_subspace_coordinates(input, len, target, &start, &end, &best);
    phext_buffer_reset(out);
    if (end > start) {
        return buf_append(out, input + start, end - start);
    }
    return PHEXT_OK;
}

/* the fixup-break sequence shared by replace and insert: breaks that
 * walk `from` up to `location`, emitted exactly as phext.rs emits them */
static phext_status build_fixup(phext_buffer *fixup, phext_coordinate from,
                                phext_coordinate location) {
    phext_coordinate at = from;
    phext_status status;
    phext_buffer_reset(fixup);
    while (at.z.library < location.z.library) {
        if ((status = buf_append_byte(fixup, PHEXT_LIBRARY_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_library_break(&at);
    }
    while (at.z.shelf < location.z.shelf) {
        if ((status = buf_append_byte(fixup, PHEXT_SHELF_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_shelf_break(&at);
    }
    while (at.z.series < location.z.series) {
        if ((status = buf_append_byte(fixup, PHEXT_SERIES_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_series_break(&at);
    }
    while (at.y.collection < location.y.collection) {
        if ((status = buf_append_byte(fixup, PHEXT_COLLECTION_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_collection_break(&at);
    }
    while (at.y.volume < location.y.volume) {
        if ((status = buf_append_byte(fixup, PHEXT_VOLUME_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_volume_break(&at);
    }
    while (at.y.book < location.y.book) {
        if ((status = buf_append_byte(fixup, PHEXT_BOOK_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_book_break(&at);
    }
    while (at.x.chapter < location.x.chapter) {
        if ((status = buf_append_byte(fixup, PHEXT_CHAPTER_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_chapter_break(&at);
    }
    while (at.x.section < location.x.section) {
        if ((status = buf_append_byte(fixup, PHEXT_SECTION_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_section_break(&at);
    }
    while (at.x.scroll < location.x.scroll) {
        if ((status = buf_append_byte(fixup, PHEXT_SCROLL_BREAK)) != PHEXT_OK) return status;
        phext_coordinate_scroll_break(&at);
    }
    return PHEXT_OK;
}

phext_status phext_replace(const unsigned char *input, size_t len,
                           phext_coordinate location,
                           const unsigned char *scroll, size_t scroll_len,
                           phext_buffer *out) {
    size_t start, end;
    phext_coordinate best;
    phext_buffer fixup;
    phext_status status;
    phext_get_subspace_coordinates(input, len, location, &start, &end, &best);
    if (end > len) {
        end = len;
    }
    phext_buffer_init(&fixup);
    status = build_fixup(&fixup, best, location);
    if (status == PHEXT_OK) {
        phext_buffer_reset(out);
        if ((status = buf_append(out, input, start)) == PHEXT_OK &&
            (status = buf_append(out, fixup.data, fixup.len)) == PHEXT_OK &&
            (status = buf_append(out, scroll, scroll_len)) == PHEXT_OK) {
            status = buf_append(out, input + end, len - end);
        }
    }
    phext_buffer_free(&fixup);
    return status;
}

phext_status phext_insert(const unsigned char *input, size_t len,
                          phext_coordinate location,
                          const unsigned char *scroll, size_t scroll_len,
                          phext_buffer *out) {
    size_t start, end;
    phext_coordinate best;
    phext_buffer fixup;
    phext_status status;
    phext_get_subspace_coordinates(input, len, location, &start, &end, &best);
    (void)start;
    phext_buffer_init(&fixup);
    status = build_fixup(&fixup, best, location);
    if (status == PHEXT_OK) {
        phext_buffer_reset(out);
        if ((status = buf_append(out, input, end)) == PHEXT_OK &&
            (status = buf_append(out, fixup.data, fixup.len)) == PHEXT_OK &&
            (status = buf_append(out, scroll, scroll_len)) == PHEXT_OK) {
            status = buf_append(out, input + end, len - end);
        }
    }
    phext_buffer_free(&fixup);
    return status;
}

phext_status phext_remove(const unsigned char *input, size_t len,
                          phext_coordinate location, phext_buffer *out) {
    /* Rust: remove = replace with "", then normalize */
    phext_buffer phase1;
    phext_status status;
    phext_buffer_init(&phase1);
    status = phext_replace(input, len, location, (const unsigned char *)"", 0, &phase1);
    if (status == PHEXT_OK) {
        status = phext_normalize(phase1.data, phase1.len, out);
    }
    phext_buffer_free(&phase1);
    return status;
}

phext_status phext_range_replace(const unsigned char *input, size_t len,
                                 phext_range range,
                                 const unsigned char *scroll, size_t scroll_len,
                                 phext_buffer *out) {
    size_t start, end, scratch_end;
    phext_coordinate scratch_best;
    phext_status status;
    phext_get_subspace_coordinates(input, len, range.start, &start, &scratch_end, &scratch_best);
    phext_get_subspace_coordinates(input, len, range.end, &scratch_end, &end, &scratch_best);
    if (end > len) {
        end = len;
    }
    phext_buffer_reset(out);
    if ((status = buf_append(out, input, start)) == PHEXT_OK &&
        (status = buf_append(out, scroll, scroll_len)) == PHEXT_OK) {
        status = buf_append(out, input + end, len - end);
    }
    return status;
}

phext_status phext_next_scroll(const unsigned char *input, size_t len,
                               phext_coordinate start,
                               phext_positioned_scroll *out_scroll,
                               phext_coordinate *out_next,
                               phext_buffer *out_remaining) {
    phext_coordinate location = start;
    phext_coordinate begin = start;
    phext_buffer output;
    size_t pi = 0;
    phext_status status = PHEXT_OK;
    phext_buffer_init(&output);

    while (pi < len) {
        int dimension_break = 0;
        unsigned char byte = input[pi];
        if (byte == PHEXT_SCROLL_BREAK)     { phext_coordinate_scroll_break(&location);     dimension_break = 1; }
        if (byte == PHEXT_SECTION_BREAK)    { phext_coordinate_section_break(&location);    dimension_break = 1; }
        if (byte == PHEXT_CHAPTER_BREAK)    { phext_coordinate_chapter_break(&location);    dimension_break = 1; }
        if (byte == PHEXT_BOOK_BREAK)       { phext_coordinate_book_break(&location);       dimension_break = 1; }
        if (byte == PHEXT_VOLUME_BREAK)     { phext_coordinate_volume_break(&location);     dimension_break = 1; }
        if (byte == PHEXT_COLLECTION_BREAK) { phext_coordinate_collection_break(&location); dimension_break = 1; }
        if (byte == PHEXT_SERIES_BREAK)     { phext_coordinate_series_break(&location);     dimension_break = 1; }
        if (byte == PHEXT_SHELF_BREAK)      { phext_coordinate_shelf_break(&location);      dimension_break = 1; }
        if (byte == PHEXT_LIBRARY_BREAK)    { phext_coordinate_library_break(&location);    dimension_break = 1; }

        if (dimension_break) {
            if (output.len > 0) {
                pi += 1;
                break;
            }
        } else {
            begin = location;
            status = buf_append_byte(&output, byte);
            if (status != PHEXT_OK) {
                phext_buffer_free(&output);
                return status;
            }
        }
        pi += 1;
    }

    out_scroll->coord = begin;
    phext_buffer_reset(&out_scroll->scroll);
    status = buf_append(&out_scroll->scroll, output.data, output.len);
    phext_buffer_free(&output);
    if (status != PHEXT_OK) {
        return status;
    }
    *out_next = location;
    phext_buffer_reset(out_remaining);
    if (pi < len) {
        status = buf_append(out_remaining, input + pi, len - pi);
    }
    return status;
}

phext_status phext_phokenize(const unsigned char *input, size_t len, phext_scrolls *out) {
    /* one pass, ported from phext.rs::phokenize (each step agrees with a
     * call to next_scroll; the Rust tests prove that on 5,000 documents) */
    phext_coordinate coord = phext_default_coordinate();
    size_t pi = 0;
    phext_scrolls_reset(out);
    for (;;) {
        phext_coordinate begin = coord;
        int have_text = 0;
        size_t text_start = 0;
        size_t text_end = len;
        phext_status status;
        while (pi < len) {
            unsigned char byte = input[pi];
            if (phext_is_dimension_break(byte)) {
                apply_break(&coord, byte);
                if (have_text) {
                    text_end = pi;
                    pi += 1;
                    break;
                }
            } else if (!have_text) {
                have_text = 1;
                text_start = pi;
                begin = coord;
            }
            pi += 1;
        }
        if (have_text) {
            status = phext_scrolls_push(out, begin, input + text_start, text_end - text_start);
        } else {
            status = phext_scrolls_push(out, begin, (const unsigned char *)"", 0);
        }
        if (status != PHEXT_OK) {
            return status;
        }
        if (pi >= len) {
            break;
        }
    }
    return PHEXT_OK;
}

/* Rust: append_scroll - emit the breaks from `coord` up to the token's
 * coordinate, then the token's text */
static phext_status append_scroll(phext_buffer *out, const phext_positioned_scroll *token,
                                  phext_coordinate coord) {
    phext_status status;
    while (phext_coordinate_compare(coord, token->coord) < 0) {
        if (coord.z.library < token->coord.z.library) {
            if ((status = buf_append_byte(out, PHEXT_LIBRARY_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_library_break(&coord);
            continue;
        }
        if (coord.z.shelf < token->coord.z.shelf) {
            if ((status = buf_append_byte(out, PHEXT_SHELF_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_shelf_break(&coord);
            continue;
        }
        if (coord.z.series < token->coord.z.series) {
            if ((status = buf_append_byte(out, PHEXT_SERIES_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_series_break(&coord);
            continue;
        }
        if (coord.y.collection < token->coord.y.collection) {
            if ((status = buf_append_byte(out, PHEXT_COLLECTION_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_collection_break(&coord);
            continue;
        }
        if (coord.y.volume < token->coord.y.volume) {
            if ((status = buf_append_byte(out, PHEXT_VOLUME_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_volume_break(&coord);
            continue;
        }
        if (coord.y.book < token->coord.y.book) {
            if ((status = buf_append_byte(out, PHEXT_BOOK_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_book_break(&coord);
            continue;
        }
        if (coord.x.chapter < token->coord.x.chapter) {
            if ((status = buf_append_byte(out, PHEXT_CHAPTER_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_chapter_break(&coord);
            continue;
        }
        if (coord.x.section < token->coord.x.section) {
            if ((status = buf_append_byte(out, PHEXT_SECTION_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_section_break(&coord);
            continue;
        }
        if (coord.x.scroll < token->coord.x.scroll) {
            if ((status = buf_append_byte(out, PHEXT_SCROLL_BREAK)) != PHEXT_OK) return status;
            phext_coordinate_scroll_break(&coord);
            continue;
        }
    }
    return buf_append(out, token->scroll.data, token->scroll.len);
}

/* Rust: dephokenize - serialize positioned scrolls; empty scrolls emit
 * no text but still advance the working coordinate */
static phext_status dephokenize(const phext_scrolls *tokens, phext_buffer *out) {
    phext_coordinate coord = phext_default_coordinate();
    size_t i;
    phext_buffer_reset(out);
    for (i = 0; i < tokens->len; i++) {
        phext_status status;
        if (tokens->items[i].scroll.len > 0) {
            status = append_scroll(out, &tokens->items[i], coord);
            if (status != PHEXT_OK) {
                return status;
            }
        }
        coord = tokens->items[i].coord;
    }
    return PHEXT_OK;
}

phext_status phext_explode(const unsigned char *input, size_t len, phext_scrolls *out_map) {
    phext_status status = phext_phokenize(input, len, out_map);
    if (status != PHEXT_OK) {
        return status;
    }
    scrolls_sort(out_map);
    return PHEXT_OK;
}

phext_status phext_implode(const phext_scrolls *map, phext_buffer *out) {
    phext_scrolls sorted;
    phext_status status;
    phext_scrolls_init(&sorted);
    status = scrolls_clone(map, &sorted);
    if (status == PHEXT_OK) {
        scrolls_sort(&sorted);
        status = dephokenize(&sorted, out);
    }
    phext_scrolls_free(&sorted);
    return status;
}

phext_status phext_merge(const unsigned char *left, size_t left_len,
                         const unsigned char *right, size_t right_len,
                         phext_buffer *out) {
    phext_scrolls tl, tr;
    phext_status status;
    size_t tli = 0, tri = 0;
    phext_coordinate coord;
    phext_scrolls_init(&tl);
    phext_scrolls_init(&tr);
    phext_buffer_reset(out);
    status = phext_phokenize(left, left_len, &tl);
    if (status == PHEXT_OK) {
        status = phext_phokenize(right, right_len, &tr);
    }
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tl);
        phext_scrolls_free(&tr);
        return status;
    }
    coord = phext_default_coordinate();
    for (;;) {
        int have_left = tli < tl.len;
        int have_right = tri < tr.len;
        int pick_left = have_left && (!have_right ||
                        phext_coordinate_compare(tl.items[tli].coord, tr.items[tri].coord) <= 0);
        int pick_right = have_right && (!have_left ||
                        phext_coordinate_compare(tr.items[tri].coord, tl.items[tli].coord) <= 0);
        if (pick_left) {
            status = append_scroll(out, &tl.items[tli], coord);
            if (status != PHEXT_OK) break;
            coord = tl.items[tli].coord;
            tli += 1;
        }
        if (pick_right) {
            status = append_scroll(out, &tr.items[tri], coord);
            if (status != PHEXT_OK) break;
            coord = tr.items[tri].coord;
            tri += 1;
        }
        if (!pick_left && !pick_right) {
            break;
        }
    }
    phext_scrolls_free(&tl);
    phext_scrolls_free(&tr);
    return status;
}

phext_status phext_subtract(const unsigned char *left, size_t left_len,
                            const unsigned char *right, size_t right_len,
                            phext_buffer *out) {
    phext_scrolls pl, pr;
    phext_status status;
    size_t i, pri = 0;
    phext_coordinate coord;
    phext_scrolls_init(&pl);
    phext_scrolls_init(&pr);
    phext_buffer_reset(out);
    status = phext_phokenize(left, left_len, &pl);
    if (status == PHEXT_OK) {
        status = phext_phokenize(right, right_len, &pr);
    }
    if (status != PHEXT_OK) {
        phext_scrolls_free(&pl);
        phext_scrolls_free(&pr);
        return status;
    }
    coord = phext_default_coordinate();
    for (i = 0; i < pl.len; i++) {
        const phext_positioned_scroll *token = &pl.items[i];
        int masked;
        if (token->scroll.len == 0) {
            continue;
        }
        while (pri < pr.len && phext_coordinate_compare(pr.items[pri].coord, token->coord) < 0) {
            pri += 1;
        }
        masked = pri < pr.len &&
                 phext_coordinate_equal(pr.items[pri].coord, token->coord) &&
                 pr.items[pri].scroll.len > 0;
        if (!masked) {
            status = append_scroll(out, token, coord);
            if (status != PHEXT_OK) {
                phext_scrolls_free(&pl);
                phext_scrolls_free(&pr);
                return status;
            }
            coord = token->coord;
        }
    }
    phext_scrolls_free(&pl);
    phext_scrolls_free(&pr);
    return PHEXT_OK;
}

phext_status phext_expand(const unsigned char *input, size_t len, phext_buffer *out) {
    size_t i;
    phext_status status = buf_set(out, input, len);
    if (status != PHEXT_OK) {
        return status;
    }
    for (i = 0; i < len; i++) {
        unsigned char byte = out->data[i];
        if (byte == PHEXT_LINE_BREAK)            out->data[i] = PHEXT_SCROLL_BREAK;
        else if (byte == PHEXT_SCROLL_BREAK)     out->data[i] = PHEXT_SECTION_BREAK;
        else if (byte == PHEXT_SECTION_BREAK)    out->data[i] = PHEXT_CHAPTER_BREAK;
        else if (byte == PHEXT_CHAPTER_BREAK)    out->data[i] = PHEXT_BOOK_BREAK;
        else if (byte == PHEXT_BOOK_BREAK)       out->data[i] = PHEXT_VOLUME_BREAK;
        else if (byte == PHEXT_VOLUME_BREAK)     out->data[i] = PHEXT_COLLECTION_BREAK;
        else if (byte == PHEXT_COLLECTION_BREAK) out->data[i] = PHEXT_SERIES_BREAK;
        else if (byte == PHEXT_SERIES_BREAK)     out->data[i] = PHEXT_SHELF_BREAK;
        else if (byte == PHEXT_SHELF_BREAK)      out->data[i] = PHEXT_LIBRARY_BREAK;
    }
    return PHEXT_OK;
}

phext_status phext_contract(const unsigned char *input, size_t len, phext_buffer *out) {
    size_t i;
    phext_status status = buf_set(out, input, len);
    if (status != PHEXT_OK) {
        return status;
    }
    for (i = 0; i < len; i++) {
        unsigned char byte = out->data[i];
        if (byte == PHEXT_LIBRARY_BREAK)         out->data[i] = PHEXT_SHELF_BREAK;
        else if (byte == PHEXT_SHELF_BREAK)      out->data[i] = PHEXT_SERIES_BREAK;
        else if (byte == PHEXT_SERIES_BREAK)     out->data[i] = PHEXT_COLLECTION_BREAK;
        else if (byte == PHEXT_COLLECTION_BREAK) out->data[i] = PHEXT_VOLUME_BREAK;
        else if (byte == PHEXT_VOLUME_BREAK)     out->data[i] = PHEXT_BOOK_BREAK;
        else if (byte == PHEXT_BOOK_BREAK)       out->data[i] = PHEXT_CHAPTER_BREAK;
        else if (byte == PHEXT_CHAPTER_BREAK)    out->data[i] = PHEXT_SECTION_BREAK;
        else if (byte == PHEXT_SECTION_BREAK)    out->data[i] = PHEXT_SCROLL_BREAK;
        else if (byte == PHEXT_SCROLL_BREAK)     out->data[i] = PHEXT_LINE_BREAK;
    }
    return PHEXT_OK;
}

phext_status phext_normalize(const unsigned char *input, size_t len, phext_buffer *out) {
    phext_scrolls tokens;
    phext_status status;
    phext_scrolls_init(&tokens);
    status = phext_phokenize(input, len, &tokens);
    if (status == PHEXT_OK) {
        status = dephokenize(&tokens, out);
    }
    phext_scrolls_free(&tokens);
    return status;
}

phext_status phext_create_summary(const unsigned char *input, size_t len, phext_buffer *out) {
    /* scan bytes, not chars: every break is an ASCII byte below 0x20,
     * and UTF-8 multibyte sequences never contain bytes below 0x80 */
    size_t end = 0;
    phext_status status;
    while (end < len) {
        if (phext_is_phext_break(input[end])) {
            break;
        }
        end += 1;
    }
    phext_buffer_reset(out);
    status = buf_append(out, input, end);
    if (status == PHEXT_OK && end < len) {
        status = buf_append(out, (const unsigned char *)"...", 3);
    }
    return status;
}

phext_status phext_textmap(const unsigned char *input, size_t len, phext_buffer *out) {
    phext_scrolls tokens;
    phext_status status;
    size_t i;
    phext_scrolls_init(&tokens);
    phext_buffer_reset(out);
    status = phext_phokenize(input, len, &tokens);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tokens);
        return status;
    }
    for (i = 0; i < tokens.len && status == PHEXT_OK; i++) {
        phext_buffer coord_text, summary;
        phext_buffer_init(&coord_text);
        phext_buffer_init(&summary);
        if ((status = phext_coordinate_to_string(tokens.items[i].coord, &coord_text)) == PHEXT_OK &&
            (status = phext_create_summary(tokens.items[i].scroll.data,
                                            tokens.items[i].scroll.len, &summary)) == PHEXT_OK &&
            (status = buf_append(out, (const unsigned char *)"* ", 2)) == PHEXT_OK &&
            (status = buf_append(out, coord_text.data, coord_text.len)) == PHEXT_OK &&
            (status = buf_append(out, (const unsigned char *)": ", 2)) == PHEXT_OK &&
            (status = buf_append(out, summary.data, summary.len)) == PHEXT_OK) {
            status = buf_append_byte(out, (unsigned char)'\n');
        }
        phext_buffer_free(&coord_text);
        phext_buffer_free(&summary);
    }
    phext_scrolls_free(&tokens);
    return status;
}

phext_status phext_navmap(const char *urlbase, const unsigned char *input, size_t len,
                          phext_buffer *out) {
    phext_scrolls tokens;
    phext_status status;
    size_t i;
    phext_scrolls_init(&tokens);
    phext_buffer_reset(out);
    status = phext_phokenize(input, len, &tokens);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tokens);
        return status;
    }
    if (tokens.len > 0) {
        status = buf_append(out, (const unsigned char *)"<ul>\n", 5);
    }
    for (i = 0; i < tokens.len && status == PHEXT_OK; i++) {
        phext_buffer encoded, coord_text, summary;
        phext_buffer_init(&encoded);
        phext_buffer_init(&coord_text);
        phext_buffer_init(&summary);
        if ((status = phext_coordinate_to_urlencoded(tokens.items[i].coord, &encoded)) == PHEXT_OK &&
            (status = phext_coordinate_to_string(tokens.items[i].coord, &coord_text)) == PHEXT_OK &&
            (status = phext_create_summary(tokens.items[i].scroll.data,
                                            tokens.items[i].scroll.len, &summary)) == PHEXT_OK &&
            (status = buf_append(out, (const unsigned char *)"<li><a href=\"", 13)) == PHEXT_OK &&
            (status = buf_append(out, (const unsigned char *)urlbase, strlen(urlbase))) == PHEXT_OK &&
            (status = buf_append(out, encoded.data, encoded.len)) == PHEXT_OK &&
            (status = buf_append(out, (const unsigned char *)"\">", 2)) == PHEXT_OK &&
            (status = buf_append(out, coord_text.data, coord_text.len)) == PHEXT_OK &&
            (status = buf_append_byte(out, (unsigned char)' ')) == PHEXT_OK &&
            (status = buf_append(out, summary.data, summary.len)) == PHEXT_OK) {
            status = buf_append(out, (const unsigned char *)"</a></li>\n", 10);
        }
        phext_buffer_free(&encoded);
        phext_buffer_free(&coord_text);
        phext_buffer_free(&summary);
    }
    if (status == PHEXT_OK && tokens.len > 0) {
        status = buf_append(out, (const unsigned char *)"</ul>\n", 6);
    }
    phext_scrolls_free(&tokens);
    return status;
}

phext_status phext_manifest(const unsigned char *input, size_t len, phext_buffer *out) {
    phext_scrolls tokens;
    phext_status status;
    size_t i;
    phext_scrolls_init(&tokens);
    status = phext_phokenize(input, len, &tokens);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tokens);
        return status;
    }
    for (i = 0; i < tokens.len; i++) {
        char hex[33];
        phext_checksum(tokens.items[i].scroll.data, tokens.items[i].scroll.len, hex);
        status = buf_set(&tokens.items[i].scroll, (const unsigned char *)hex, 32);
        if (status != PHEXT_OK) {
            phext_scrolls_free(&tokens);
            return status;
        }
    }
    status = dephokenize(&tokens, out);
    phext_scrolls_free(&tokens);
    return status;
}

static int byte_in(unsigned char byte, const char *set, size_t set_len) {
    size_t i;
    for (i = 0; i < set_len; i++) {
        if (byte == (unsigned char)set[i]) {
            return 1;
        }
    }
    return 0;
}

/* Rust: soundex_internal */
static phext_status soundex_internal(const unsigned char *input, size_t len, phext_buffer *out) {
    size_t value = 1; /* 1-100ish, as in Rust */
    size_t i;
    for (i = 0; i < len; i++) {
        unsigned char byte = input[i];
        if (byte_in(byte, "bpfv", 4))          { value += 1; continue; }
        if (byte_in(byte, "cskgjqxz", 8))      { value += 2; continue; }
        if (byte_in(byte, "dt", 2))            { value += 3; continue; }
        if (byte_in(byte, "l", 1))             { value += 4; continue; }
        if (byte_in(byte, "mn", 2))            { value += 5; continue; }
        if (byte_in(byte, "r", 1))             { value += 6; continue; }
    }
    phext_buffer_reset(out);
    return buf_append_usize(out, value % 99);
}

phext_status phext_soundex_v1(const unsigned char *input, size_t len, phext_buffer *out) {
    phext_scrolls tokens;
    phext_status status;
    size_t i;
    phext_scrolls_init(&tokens);
    status = phext_phokenize(input, len, &tokens);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tokens);
        return status;
    }
    for (i = 0; i < tokens.len; i++) {
        phext_buffer scored;
        phext_buffer_init(&scored);
        status = soundex_internal(tokens.items[i].scroll.data,
                                  tokens.items[i].scroll.len, &scored);
        if (status == PHEXT_OK) {
            status = buf_set(&tokens.items[i].scroll, scored.data, scored.len);
        }
        phext_buffer_free(&scored);
        if (status != PHEXT_OK) {
            phext_scrolls_free(&tokens);
            return status;
        }
    }
    status = dephokenize(&tokens, out);
    phext_scrolls_free(&tokens);
    return status;
}

/* Rust: index_phokens - each scroll paired with its byte offset */
static phext_status index_phokens(const unsigned char *input, size_t len, phext_scrolls *out) {
    phext_scrolls tokens;
    phext_status status;
    size_t i;
    size_t offset = 0;
    phext_coordinate coord;
    phext_scrolls_init(&tokens);
    phext_scrolls_reset(out);
    status = phext_phokenize(input, len, &tokens);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&tokens);
        return status;
    }
    coord = phext_default_coordinate();
    for (i = 0; i < tokens.len; i++) {
        phext_coordinate reference = tokens.items[i].coord;
        phext_buffer offset_text;
        while (coord.z.library < reference.z.library) { phext_coordinate_library_break(&coord); offset += 1; }
        while (coord.z.shelf < reference.z.shelf)     { phext_coordinate_shelf_break(&coord);     offset += 1; }
        while (coord.z.series < reference.z.series)   { phext_coordinate_series_break(&coord);    offset += 1; }
        while (coord.y.collection < reference.y.collection) { phext_coordinate_collection_break(&coord); offset += 1; }
        while (coord.y.volume < reference.y.volume)   { phext_coordinate_volume_break(&coord);    offset += 1; }
        while (coord.y.book < reference.y.book)       { phext_coordinate_book_break(&coord);      offset += 1; }
        while (coord.x.chapter < reference.x.chapter) { phext_coordinate_chapter_break(&coord);   offset += 1; }
        while (coord.x.section < reference.x.section) { phext_coordinate_section_break(&coord);   offset += 1; }
        while (coord.x.scroll < reference.x.scroll)   { phext_coordinate_scroll_break(&coord);    offset += 1; }

        phext_buffer_init(&offset_text);
        status = buf_append_usize(&offset_text, offset);
        if (status == PHEXT_OK) {
            status = phext_scrolls_push(out, coord, offset_text.data, offset_text.len);
        }
        phext_buffer_free(&offset_text);
        if (status != PHEXT_OK) {
            phext_scrolls_free(&tokens);
            return status;
        }
        offset += tokens.items[i].scroll.len;
    }
    phext_scrolls_free(&tokens);
    return PHEXT_OK;
}

phext_status phext_index(const unsigned char *input, size_t len, phext_buffer *out) {
    phext_scrolls indexed;
    phext_status status;
    phext_scrolls_init(&indexed);
    status = index_phokens(input, len, &indexed);
    if (status == PHEXT_OK) {
        status = dephokenize(&indexed, out);
    }
    phext_scrolls_free(&indexed);
    return status;
}

phext_status phext_offset(const unsigned char *input, size_t len,
                          phext_coordinate coord, size_t *out_offset) {
    phext_scrolls indexed;
    phext_status status;
    size_t i;
    size_t result = 0;
    phext_scrolls_init(&indexed);
    status = index_phokens(input, len, &indexed);
    if (status != PHEXT_OK) {
        phext_scrolls_free(&indexed);
        return status;
    }
    for (i = 0; i < indexed.len; i++) {
        size_t value = 0;
        size_t j;
        if (phext_coordinate_compare(indexed.items[i].coord, coord) > 0) {
            break;
        }
        /* the offset strings are generated by us and always parse;
         * Rust: parse::<usize>().unwrap_or(result) */
        for (j = 0; j < indexed.items[i].scroll.len; j++) {
            unsigned char digit = indexed.items[i].scroll.data[j];
            if (digit < '0' || digit > '9') {
                break;
            }
            value = value * 10 + (size_t)(digit - '0');
        }
        if (j == indexed.items[i].scroll.len && j > 0) {
            result = value;
        }
    }
    phext_scrolls_free(&indexed);
    *out_offset = result;
    return PHEXT_OK;
}
