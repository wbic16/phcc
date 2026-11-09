/* ----------------------------------------------------------------------------------------------------------
 * test_phext.c - conformance tests for the C phext library
 *
 * A port of libphext-rs's own test suites - src/test_lib.rs,
 * src/test_phokenize.rs, src/regressions.rs (v0.4.1), plus
 * src/test_binary.rs and src/test_seal.rs (v0.5.0) - with the same
 * vectors and the same expected values. Test names match the Rust names
 * so a failure here points at the same case there. The seal tests run
 * only in the PHEXT_WITH_XZ build (make test-xz); the plain build runs
 * test_seal_not_compiled instead.
 *
 * Adaptations (no behavioural difference):
 *   - Rust HashMap iteration order is unspecified; the three-scroll
 *     fetch helper builds its sample in coordinate order.
 *   - Rust timing asserts are kept where they are generous (the perf
 *     tests) and reported with the measured time.
 *   - test_subspace_filter has no assertions in Rust (a TODO sketch);
 *     it is ported as an empty test for completeness.
 *
 * Run from this directory (the helios regression reads its fixtures by
 * relative path, exactly as the Rust test does).
 * ---------------------------------------------------------------------------------------------------------- */

#define _POSIX_C_SOURCE 199309L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "phext.h"

static int g_checks = 0;
static int g_failures = 0;
static const char *g_test = "?";

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1000000.0;
}

static void print_escaped(const unsigned char *bytes, size_t len) {
    size_t i;
    for (i = 0; i < len && i < 120; i++) {
        unsigned char b = bytes[i];
        if (b >= 0x20 && b < 0x7f && b != '\\') {
            putchar(b);
        } else {
            printf("\\x%02x", b);
        }
    }
    if (len > 120) {
        printf("...");
    }
}

#define TEST(name) do { g_test = name; } while (0)

#define CHECK(cond) do { \
    g_checks++; \
    if (!(cond)) { \
        g_failures++; \
        printf("FAIL [%s] %s (line %d)\n", g_test, #cond, __LINE__); \
    } \
} while (0)

static int buf_eq(const phext_buffer *buf, const unsigned char *want, size_t want_len) {
    return buf->len == want_len && (want_len == 0 || memcmp(buf->data, want, want_len) == 0);
}

#define LIT(s) (const unsigned char *)(s), (sizeof(s) - 1)

#define CHECK_BUF(buf, lit) do { \
    g_checks++; \
    if (!buf_eq((buf), LIT(lit))) { \
        g_failures++; \
        printf("FAIL [%s] line %d: got len %lu [", g_test, __LINE__, (unsigned long)(buf)->len); \
        print_escaped((buf)->data, (buf)->len); \
        printf("] want len %lu [", (unsigned long)(sizeof(lit) - 1)); \
        print_escaped(LIT(lit)); \
        printf("]\n"); \
    } \
} while (0)

#define CHECK_MEM(buf, arr) do { \
    g_checks++; \
    if (!buf_eq((buf), (arr), sizeof(arr))) { \
        g_failures++; \
        printf("FAIL [%s] line %d: got len %lu, want len %lu\n", g_test, __LINE__, \
               (unsigned long)(buf)->len, (unsigned long)sizeof(arr)); \
    } \
} while (0)

static phext_coordinate C(const char *address) {
    return phext_to_coordinate(address);
}

static void coord_str(phext_coordinate coord, phext_buffer *out) {
    phext_coordinate_to_string(coord, out);
}

#define CHECK_COORD_STR(coord, lit) do { \
    phext_buffer _s; phext_buffer_init(&_s); coord_str((coord), &_s); \
    CHECK_BUF(&_s, lit); phext_buffer_free(&_s); \
} while (0)

static void buf_swap(phext_buffer *a, phext_buffer *b) {
    phext_buffer tmp = *a;
    *a = *b;
    *b = tmp;
}

/* fetch into out; returns out for chaining */
static phext_buffer *fetch_lit(const unsigned char *doc, size_t len, const char *coord,
                               phext_buffer *out) {
    phext_fetch(doc, len, C(coord), out);
    return out;
}

/* ----------------------------------------------------------------------------------------------------------
 * raw-byte fixtures extracted byte-for-byte from test_lib.rs
 * ---------------------------------------------------------------------------------------------------------- */

static const unsigned char REALISTIC_DOC[] = {
    0x01, 0x01, 0x01, 0x01, 0x01, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f,
    0x1f, 0x1e, 0x1e, 0x1e, 0x1d, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1a,
    0x1a, 0x1a, 0x19, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18,
    0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x17, 0x17, 0x68, 0x65, 0x72, 0x65, 0x27, 0x73, 0x20, 0x73,
    0x6f, 0x6d, 0x65, 0x20, 0x74, 0x65, 0x78, 0x74, 0x20, 0x61, 0x74, 0x20, 0x36, 0x2e, 0x31, 0x33,
    0x2e, 0x34, 0x2f, 0x32, 0x2e, 0x31, 0x31, 0x2e, 0x34, 0x2f, 0x32, 0x2e, 0x32, 0x30, 0x2e, 0x33,
    0x17, 0x74, 0x68, 0x69, 0x73, 0x20, 0x69, 0x73, 0x20, 0x74, 0x68, 0x65, 0x20, 0x6e, 0x65, 0x78,
    0x74, 0x20, 0x73, 0x63, 0x72, 0x6f, 0x6c, 0x6c, 0x20, 0x61, 0x6e, 0x64, 0x20, 0x77, 0x6f, 0x6e,
    0x27, 0x74, 0x20, 0x62, 0x65, 0x20, 0x70, 0x69, 0x63, 0x6b, 0x65, 0x64
};

static const unsigned char REG2_BASELINE[] = {
    0x31, 0x2e, 0x31, 0x2e, 0x31, 0x17, 0x31, 0x2e, 0x31, 0x2e, 0x32, 0x17, 0x31, 0x2e, 0x31, 0x2e,
    0x33, 0x17, 0x31, 0x2e, 0x31, 0x2e, 0x34, 0x18, 0x31, 0x2e, 0x32, 0x2e, 0x31, 0x17, 0x31, 0x2e,
    0x32, 0x2e, 0x32, 0x17, 0x31, 0x2e, 0x32, 0x2e, 0x33, 0x17, 0x31, 0x2e, 0x32, 0x2e, 0x34, 0x19,
    0x32, 0x2e, 0x31, 0x2e, 0x31, 0x19, 0x33, 0x2e, 0x31, 0x2e, 0x31, 0x19, 0x34, 0x2e, 0x31, 0x2e,
    0x31, 0x1a, 0x32, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x17, 0x17, 0x32, 0x2f, 0x31, 0x2e, 0x31,
    0x2e, 0x33, 0x1c, 0x32, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x1d, 0x32, 0x2e, 0x31,
    0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x1e, 0x32, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31,
    0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x1f, 0x32, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31,
    0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x01, 0x32, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31,
    0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31
};

static const unsigned char REG2_EXPECTED[] = {
    0x31, 0x2e, 0x31, 0x2e, 0x31, 0x17, 0x31, 0x2e, 0x31, 0x2e, 0x32, 0x17, 0x31, 0x2e, 0x31, 0x2e,
    0x33, 0x17, 0x31, 0x2e, 0x31, 0x2e, 0x34, 0x18, 0x31, 0x2e, 0x32, 0x2e, 0x31, 0x17, 0x31, 0x2e,
    0x32, 0x2e, 0x32, 0x17, 0x31, 0x2e, 0x32, 0x2e, 0x33, 0x17, 0x31, 0x2e, 0x32, 0x2e, 0x34, 0x19,
    0x32, 0x2e, 0x31, 0x2e, 0x31, 0x19, 0x33, 0x2e, 0x31, 0x2e, 0x31, 0x19, 0x34, 0x2e, 0x31, 0x2e,
    0x31, 0x1a, 0x32, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x17, 0x6e, 0x65, 0x77, 0x20, 0x63, 0x6f,
    0x6e, 0x74, 0x65, 0x6e, 0x74, 0x17, 0x32, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x33, 0x1c, 0x32, 0x2e,
    0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x1d, 0x32, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e,
    0x31, 0x2e, 0x31, 0x1e, 0x32, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e,
    0x31, 0x1f, 0x32, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e,
    0x31, 0x01, 0x32, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e, 0x31, 0x2e, 0x31, 0x2f, 0x31, 0x2e,
    0x31, 0x2e, 0x31
};

/* ----------------------------------------------------------------------------------------------------------
 * test_lib.rs ports
 * ---------------------------------------------------------------------------------------------------------- */

static void test_coordinate_parsing(void) {
    phext_buffer out;
    TEST("test_coordinate_parsing");
    phext_buffer_init(&out);
    coord_str(C("9.8.7/6.5.4/3.2.1"), &out);
    CHECK_BUF(&out, "9.8.7/6.5.4/3.2.1");
    coord_str(C("HOME"), &out);
    CHECK_BUF(&out, "1.1.1/1.1.1/1.1.1");
    phext_buffer_free(&out);
}

static void test_to_urlencoded(void) {
    phext_buffer out;
    TEST("test_to_urlencoded");
    phext_buffer_init(&out);
    phext_coordinate_to_urlencoded(C("1.1.1/1.1.1/1.1.1"), &out);
    CHECK_BUF(&out, "1.1.1;1.1.1;1.1.1");
    phext_coordinate_to_urlencoded(C("98.76.54/32.10.1/23.45.67"), &out);
    CHECK_BUF(&out, "98.76.54;32.10.1;23.45.67");
    phext_buffer_free(&out);
}

/* the Rust test_helper: three texts joined by one delimiter kind, each
 * fetched back at its own address (built in coordinate order - see the
 * note at the top of this file) */
static void fetch_helper(unsigned char delim,
                         const char *text1, const char *addr1,
                         const char *text2, const char *addr2,
                         const char *text3, const char *addr3) {
    /* sample = text1 DELIM text2 DELIM text3, as in the Rust helper */
    unsigned char sample[512];
    size_t len = 0;
    phext_buffer got;
    phext_buffer_init(&got);
#define APPEND_LIT(s) do { memcpy(sample + len, (s), strlen(s)); len += strlen(s); } while (0)
    APPEND_LIT(text1);
    sample[len++] = delim;
    APPEND_LIT(text2);
    sample[len++] = delim;
    APPEND_LIT(text3);
#undef APPEND_LIT
    fetch_lit(sample, len, addr1, &got);
    CHECK(got.len == strlen(text1) && memcmp(got.data, text1, got.len) == 0);
    fetch_lit(sample, len, addr2, &got);
    CHECK(got.len == strlen(text2) && memcmp(got.data, text2, got.len) == 0);
    fetch_lit(sample, len, addr3, &got);
    CHECK(got.len == strlen(text3) && memcmp(got.data, text3, got.len) == 0);
    phext_buffer_free(&got);
}

static void test_dimension_fetches(void) {
    TEST("test_scrolls");
    fetch_helper(PHEXT_SCROLL_BREAK,
                 "Hello World", "1.1.1/1.1.1/1.1.1",
                 "Scroll #2 -- this text will be selected", "1.1.1/1.1.1/1.1.2",
                 "Scroll #3 - this text will be ignored", "1.1.1/1.1.1/1.1.3");
    TEST("test_sections");
    fetch_helper(PHEXT_SECTION_BREAK,
                 "Section A", "1.1.1/1.1.1/1.1.1",
                 "Section B", "1.1.1/1.1.1/1.2.1",
                 "Section C", "1.1.1/1.1.1/1.3.1");
    TEST("test_chapters");
    fetch_helper(PHEXT_CHAPTER_BREAK,
                 "Chapter Alpha", "1.1.1/1.1.1/1.1.1",
                 "Chapter Beta", "1.1.1/1.1.1/2.1.1",
                 "Chapter Gamma", "1.1.1/1.1.1/3.1.1");
    TEST("test_books");
    fetch_helper(PHEXT_BOOK_BREAK,
                 "Book z1", "1.1.1/1.1.1/1.1.1",
                 "Book Something Else #2", "1.1.1/1.1.2/1.1.1",
                 "Book Part 3", "1.1.1/1.1.3/1.1.1");
    TEST("test_volumes");
    fetch_helper(PHEXT_VOLUME_BREAK,
                 "Volume 1-1-1", "1.1.1/1.1.1/1.1.1",
                 "Volume 1-2-1", "1.1.1/1.2.1/1.1.1",
                 "Volume 1-3-1", "1.1.1/1.3.1/1.1.1");
    TEST("test_collections");
    fetch_helper(PHEXT_COLLECTION_BREAK,
                 "Collection 1-1-1", "1.1.1/1.1.1/1.1.1",
                 "Collection 2-1-1", "1.1.1/2.1.1/1.1.1",
                 "Collection 3-1-1", "1.1.1/3.1.1/1.1.1");
    TEST("test_series");
    fetch_helper(PHEXT_SERIES_BREAK,
                 "Series 1-1-1", "1.1.1/1.1.1/1.1.1",
                 "Series 1-1-2", "1.1.2/1.1.1/1.1.1",
                 "Series 1-1-3", "1.1.3/1.1.1/1.1.1");
    TEST("test_shelves");
    fetch_helper(PHEXT_SHELF_BREAK,
                 "Shelf 1-1-1", "1.1.1/1.1.1/1.1.1",
                 "Shelf 1-2-1", "1.2.1/1.1.1/1.1.1",
                 "Shelf 1-3-1", "1.3.1/1.1.1/1.1.1");
    TEST("test_libraries");
    fetch_helper(PHEXT_LIBRARY_BREAK,
                 "Library 1-1-1", "1.1.1/1.1.1/1.1.1",
                 "Library 2-1-1", "2.1.1/1.1.1/1.1.1",
                 "Library 3-1-1", "3.1.1/1.1.1/1.1.1");
}

static void test_coordinates_invalid(void) {
    phext_coordinate c1, c2;
    TEST("test_coordinates_invalid");
    c1 = C("0.0.0/0.0.0/0.0.0");
    memset(&c2, 0, sizeof(c2));
    CHECK(phext_coordinate_equal(c1, c2));
    CHECK(phext_coordinate_validate(c1) == 0);
    CHECK(phext_coordinate_validate(c2) == 0);
}

static void test_coordinates_valid(void) {
    phext_coordinate c1, c2;
    TEST("test_coordinates_valid");
    c1 = C("1001.254.253/32.4.8/4.2.1");
    c2.z.library = 1001; c2.z.shelf = 254; c2.z.series = 253;
    c2.y.collection = 32; c2.y.volume = 4; c2.y.book = 8;
    c2.x.chapter = 4; c2.x.section = 2; c2.x.scroll = 1;
    CHECK(phext_coordinate_equal(c1, c2));
    CHECK(c1.y.volume == 4);
    CHECK(phext_coordinate_validate(c1) == 1);
    CHECK(phext_coordinate_validate(c2) == 1);
}

static void test_url_encoding(void) {
    phext_coordinate c1, c2, c3, c4;
    TEST("test_url_encoding");
    c1 = C("142.143.144;145.146.147;148.149.150");
    c2.z.library = 142; c2.z.shelf = 143; c2.z.series = 144;
    c2.y.collection = 145; c2.y.volume = 146; c2.y.book = 147;
    c2.x.chapter = 148; c2.x.section = 149; c2.x.scroll = 150;
    CHECK(phext_coordinate_equal(c1, c2));
    CHECK(phext_coordinate_validate(c1) == 1);
    CHECK(phext_coordinate_validate(c2) == 1);
    c3 = C("1001.1002.1003;1004.1005.1006;1007.1008.1009");
    c4.z.library = 1001; c4.z.shelf = 1002; c4.z.series = 1003;
    c4.y.collection = 1004; c4.y.volume = 1005; c4.y.book = 1006;
    c4.x.chapter = 1007; c4.x.section = 1008; c4.x.scroll = 1009;
    CHECK(phext_coordinate_equal(c3, c4));
    CHECK(phext_coordinate_validate(c3) == 1);
    CHECK(phext_coordinate_validate(c4) == 1);
}

static void test_realistic_parse(void) {
    phext_buffer got;
    TEST("test_realistic_parse");
    phext_buffer_init(&got);
    phext_fetch(REALISTIC_DOC, sizeof(REALISTIC_DOC), C("6.13.4/2.11.4/2.20.3"), &got);
    CHECK_BUF(&got, "here's some text at 6.13.4/2.11.4/2.20.3");
    phext_buffer_free(&got);
}

/* test-local raw append helpers (phext_buffer is a public struct) */
static void tappend(phext_buffer *buf, const unsigned char *bytes, size_t len) {
    if (buf->len + len + 1 > buf->cap) {
        size_t cap = buf->cap != 0 ? buf->cap : 64;
        while (cap < buf->len + len + 1) cap *= 2;
        buf->data = (unsigned char *)realloc(buf->data, cap);
        buf->cap = cap;
    }
    memcpy(buf->data + buf->len, bytes, len);
    buf->len += len;
    buf->data[buf->len] = 0;
}

static void tappend_str(phext_buffer *buf, const char *text) {
    tappend(buf, (const unsigned char *)text, strlen(text));
}

static void tpush(phext_buffer *buf, unsigned char byte) {
    tappend(buf, &byte, 1);
}

static void tpush_n(phext_buffer *buf, unsigned char byte, int count) {
    int i;
    for (i = 0; i < count; i++) tpush(buf, byte);
}

static void test_dead_reckoning(void) {
    phext_buffer test, got;
    TEST("test_dead_reckoning");
    phext_buffer_init(&test);
    phext_buffer_init(&got);
    tappend_str(&test, "random text in 1.1.1/1.1.1/1.1.1 that we can skip past");
    tpush(&test, PHEXT_LIBRARY_BREAK);
    tappend_str(&test, "everything in here is at 2.1.1/1.1.1/1.1.1");
    tpush(&test, PHEXT_SCROLL_BREAK);
    tappend_str(&test, "and now we're at 2.1.1/1.1.1/1.1.2");
    tpush(&test, PHEXT_SCROLL_BREAK);
    tappend_str(&test, "moving on up to 2.1.1/1.1.1/1.1.3");
    tpush(&test, PHEXT_BOOK_BREAK);
    tappend_str(&test, "and now over to 2.1.1/1.1.2/1.1.1");
    tpush(&test, PHEXT_SHELF_BREAK);
    tappend_str(&test, "woot, up to 2.2.1/1.1.1/1.1.1");
    tpush(&test, PHEXT_LIBRARY_BREAK);
    tappend_str(&test, "here we are at 3.1.1/1.1.1.1.1");
    tpush(&test, PHEXT_LIBRARY_BREAK); /* 4.1.1/1.1.1/1.1.1 */
    tpush(&test, PHEXT_LIBRARY_BREAK); /* 5.1.1/1.1.1/1.1.1 */
    tappend_str(&test, "getting closer to our target now 5.1.1/1.1.1/1.1.1");
    tpush_n(&test, PHEXT_SHELF_BREAK, 4);  /* 5.5.1 */
    tpush_n(&test, PHEXT_SERIES_BREAK, 4); /* 5.5.5 */
    tappend_str(&test, "here we go! 5.5.5/1.1.1/1.1.1");
    tpush_n(&test, PHEXT_COLLECTION_BREAK, 3); /* 5.5.5/4.1.1 */
    tpush_n(&test, PHEXT_BOOK_BREAK, 3);       /* 5.5.5/4.1.4 */
    tappend_str(&test, "this test appears at 5.5.5/4.1.4/1.1.1");
    tpush_n(&test, PHEXT_VOLUME_BREAK, 5);  /* 5.5.5/4.6.1 */
    tpush_n(&test, PHEXT_CHAPTER_BREAK, 4); /* 5.5.5/4.6.1/5.1.1 */
    tpush_n(&test, PHEXT_BOOK_BREAK, 6);    /* 5.5.5/4.6.7 */
    tpush_n(&test, PHEXT_CHAPTER_BREAK, 4); /* 5.5.5/4.6.7/5.1.1 */
    tpush_n(&test, PHEXT_SCROLL_BREAK, 5);  /* 5.5.5/4.6.7/5.1.6 */
    tappend_str(&test, "here's a test at 5.5.5/4.6.7/5.1.6");
    tpush(&test, PHEXT_SCROLL_BREAK);       /* 5.1.7 */
    tpush_n(&test, PHEXT_CHAPTER_BREAK, 4); /* 9.1.1 */
    tpush_n(&test, PHEXT_SECTION_BREAK, 4); /* 9.5.1 */
    tpush_n(&test, PHEXT_SCROLL_BREAK, 8);  /* 9.5.9 */
    tappend_str(&test, "Expected Test Pattern Alpha Whisky Tango Foxtrot");

    phext_fetch(test.data, test.len, C("5.5.5/4.6.7/9.5.9"), &got);
    CHECK_BUF(&got, "Expected Test Pattern Alpha Whisky Tango Foxtrot");
    phext_fetch(test.data, test.len, C("5.5.5/4.6.7/5.1.6"), &got);
    CHECK_BUF(&got, "here's a test at 5.5.5/4.6.7/5.1.6");
    phext_buffer_free(&test);
    phext_buffer_free(&got);
}

static void test_line_break(void) {
    TEST("test_line_break");
    CHECK(PHEXT_LINE_BREAK == '\n');
}

static void test_more_cowbell(void) {
    TEST("test_more_cowbell");
    CHECK(PHEXT_MORE_COWBELL == '\x07');
    CHECK(phext_check_for_cowbell(LIT("Hello\x07")) == 1);
    CHECK(phext_check_for_cowbell(LIT("nope\x17just more scrolls")) == 0);
}

/* one insert step in a chain: doc = insert(doc, coord, text); doc == expected */
#define INSERT_STEP(doc, next, coord, text, expected) do { \
    phext_insert((doc).data, (doc).len, C(coord), LIT(text), &(next)); \
    CHECK_BUF(&(next), expected); \
    buf_swap(&(doc), &(next)); \
} while (0)

static void test_coordinate_based_insert(void) {
    phext_buffer test, next;
    size_t start, end;
    phext_coordinate best, coord1, expected_coord;
    TEST("test_coordinate_based_insert");
    phext_buffer_init(&test);
    phext_buffer_init(&next);
    tappend_str(&test, "aaa");
    tpush(&test, PHEXT_LIBRARY_BREAK);
    tappend_str(&test, "bbb");
    tpush(&test, PHEXT_SCROLL_BREAK);
    tappend_str(&test, "ccc");

    coord1 = C("2.1.1/1.1.1/1.1.3");
    phext_get_subspace_coordinates(test.data, test.len, coord1, &start, &end, &best);
    CHECK(best.z.library == 2);
    CHECK(best.z.shelf == 1);
    CHECK(best.z.series == 1);
    CHECK(best.y.collection == 1);
    CHECK(best.y.volume == 1);
    CHECK(best.y.book == 1);
    CHECK(best.x.chapter == 1);
    CHECK(best.x.section == 1);
    CHECK(best.x.scroll == 2);
    CHECK(start == 11);
    CHECK(end == 11);

    expected_coord = phext_default_coordinate();
    expected_coord.z.library = 2;
    expected_coord.x.scroll = 3;
    CHECK(phext_coordinate_equal(coord1, expected_coord));

    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.3", "ddd", "aaa\x01" "bbb\x17" "ccc\x17" "ddd");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.4", "eee", "aaa\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.2.1", "fff", "aaa\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x18" "fff");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.2.2", "ggg", "aaa\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x18" "fff\x17" "ggg");
    INSERT_STEP(test, next, "2.1.1/1.1.1/2.1.1", "hhh", "aaa\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.5", "iii", "aaa\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "1.1.1/1.1.1/1.1.1", "---AAA", "aaa---AAA\x01" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.1", "---BBB", "aaa---AAA\x01" "bbb---BBB\x17" "ccc\x17" "ddd\x17" "eee\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.2", "---CCC", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd\x17" "eee\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.3", "---DDD", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.4", "---EEE", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.1.5", "---III", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.2.1", "---FFF", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/1.2.2", "---GGG", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh");
    INSERT_STEP(test, next, "2.1.1/1.1.1/2.1.1", "---HHH", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH");
    INSERT_STEP(test, next, "2.1.1/1.1.2/1.1.1", "jjj", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj");
    INSERT_STEP(test, next, "2.1.1/1.2.1/1.1.1", "kkk", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj\x1C" "kkk");
    INSERT_STEP(test, next, "2.1.1/2.1.1/1.1.1", "lll", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj\x1C" "kkk\x1D" "lll");
    INSERT_STEP(test, next, "2.1.2/1.1.1/1.1.1", "mmm", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj\x1C" "kkk\x1D" "lll\x1E" "mmm");
    INSERT_STEP(test, next, "2.2.1/1.1.1/1.1.1", "nnn", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj\x1C" "kkk\x1D" "lll\x1E" "mmm\x1F" "nnn");
    INSERT_STEP(test, next, "3.1.1/1.1.1/1.1.1", "ooo", "aaa---AAA\x01" "bbb---BBB\x17" "ccc---CCC\x17" "ddd---DDD\x17" "eee---EEE\x17" "iii---III\x18" "fff---FFF\x17" "ggg---GGG\x19" "hhh---HHH\x1A" "jjj\x1C" "kkk\x1D" "lll\x1E" "mmm\x1F" "nnn\x01" "ooo");

    phext_buffer_free(&test);
    phext_buffer_free(&next);
}

#define REPLACE_STEP(doc, next, coord, text, expected) do { \
    phext_replace((doc).data, (doc).len, C(coord), LIT(text), &(next)); \
    CHECK_BUF(&(next), expected); \
    buf_swap(&(doc), &(next)); \
} while (0)

static void test_coordinate_based_replace(void) {
    phext_buffer doc, next;
    TEST("test_coordinate_based_replace");
    phext_buffer_init(&doc);
    phext_buffer_init(&next);

    phext_replace(LIT("AAA\x17" "bbb\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj"),
                  C("1.1.1/1.1.1/1.1.1"), LIT("aaa"), &doc);
    CHECK_BUF(&doc, "aaa\x17" "bbb\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");

    REPLACE_STEP(doc, next, "1.1.1/1.1.1/1.1.2", "222",
        "aaa\x17" "222\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.1/1.1.1/1.2.1", "3-",
        "aaa\x17" "222\x18" "3-\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.1/1.1.1/2.1.1", "delta",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.1/1.1.2/1.1.1", "a bridge just close enough",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.1/1.2.1/1.1.1", "nifty",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "nifty\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.1/2.1.1/1.1.1", "G8",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "nifty\x1D" "G8\x1E" "hhh\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.1.2/1.1.1/1.1.1", "Hello World",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "nifty\x1D" "G8\x1E" "Hello World\x1F" "iii\x01" "jjj");
    REPLACE_STEP(doc, next, "1.2.1/1.1.1/1.1.1", "_o_",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "nifty\x1D" "G8\x1E" "Hello World\x1F" "_o_\x01" "jjj");
    REPLACE_STEP(doc, next, "2.1.1/1.1.1/1.1.1", "/win",
        "aaa\x17" "222\x18" "3-\x19" "delta\x1A" "a bridge just close enough\x1C" "nifty\x1D" "G8\x1E" "Hello World\x1F" "_o_\x01" "/win");

    /* the api editor regression (r0a) */
    phext_replace(LIT("hello world\x17" "scroll two"), C("2.1.1/1.1.1/1.1.5"),
                  LIT("2.1.1-1.1.1-1.1.5"), &next);
    CHECK_BUF(&next, "hello world\x17" "scroll two\x01\x17\x17\x17\x17" "2.1.1-1.1.1-1.1.5");
    buf_swap(&doc, &next);

    /* r1a */
    phext_replace(LIT(""), C("1.1.1/1.1.1/1.1.1"), LIT("aaa"), &doc);
    CHECK_BUF(&doc, "aaa");
    REPLACE_STEP(doc, next, "1.1.1/1.1.1/1.1.2", "bbb", "aaa\x17" "bbb");
    REPLACE_STEP(doc, next, "1.2.3/4.5.6/7.8.9", "ccc",
        "aaa\x17" "bbb\x1F\x1E\x1E\x1D\x1D\x1D\x1C\x1C\x1C\x1C\x1A\x1A\x1A\x1A\x1A\x19\x19\x19\x19\x19\x19\x18\x18\x18\x18\x18\x18\x18\x17\x17\x17\x17\x17\x17\x17\x17" "ccc");
    REPLACE_STEP(doc, next, "1.4.4/2.8.8/4.16.16", "ddd",
        "aaa\x17" "bbb\x1F\x1E\x1E\x1D\x1D\x1D\x1C\x1C\x1C\x1C\x1A\x1A\x1A\x1A\x1A\x19\x19\x19\x19\x19\x19\x18\x18\x18\x18\x18\x18\x18\x17\x17\x17\x17\x17\x17\x17\x17" "ccc"
        "\x1F\x1F\x1E\x1E\x1E\x1D\x1C\x1C\x1C\x1C\x1C\x1C\x1C\x1A\x1A\x1A\x1A\x1A\x1A\x1A\x19\x19\x19\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x18\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17\x17" "ddd");

    /* regression_1: replace at 11.12.13/14.15.16/17.18.19 appends the
     * full fixup ladder (10 library, 11 shelf, 12 series, 13 collection,
     * 14 volume, 15 book, 16 chapter, 17 section, 18 scroll breaks) */
    {
        phext_buffer expected;
        phext_buffer_init(&expected);
        tappend(&expected, doc.data, doc.len);
        tpush_n(&expected, PHEXT_LIBRARY_BREAK, 10);
        tpush_n(&expected, PHEXT_SHELF_BREAK, 11);
        tpush_n(&expected, PHEXT_SERIES_BREAK, 12);
        tpush_n(&expected, PHEXT_COLLECTION_BREAK, 13);
        tpush_n(&expected, PHEXT_VOLUME_BREAK, 14);
        tpush_n(&expected, PHEXT_BOOK_BREAK, 15);
        tpush_n(&expected, PHEXT_CHAPTER_BREAK, 16);
        tpush_n(&expected, PHEXT_SECTION_BREAK, 17);
        tpush_n(&expected, PHEXT_SCROLL_BREAK, 18);
        tappend_str(&expected, "eee");
        phext_replace(doc.data, doc.len, C("11.12.13/14.15.16/17.18.19"), LIT("eee"), &next);
        g_checks++;
        if (!buf_eq(&next, expected.data, expected.len)) {
            g_failures++;
            printf("FAIL [%s] regression_1: got len %lu want len %lu\n", g_test,
                   (unsigned long)next.len, (unsigned long)expected.len);
        }
        phext_buffer_free(&expected);
    }

    /* regression_2: replace inside a dense document (raw-byte fixtures) */
    phext_replace(REG2_BASELINE, sizeof(REG2_BASELINE), C("1.1.1/1.1.2/1.1.2"),
                  LIT("new content"), &next);
    CHECK_MEM(&next, REG2_EXPECTED);

    phext_buffer_free(&doc);
    phext_buffer_free(&next);
}

#define REMOVE_STEP(doc, next, coord, expected) do { \
    phext_remove((doc).data, (doc).len, C(coord), &(next)); \
    CHECK_BUF(&(next), expected); \
    buf_swap(&(doc), &(next)); \
} while (0)

static void test_coordinate_based_remove(void) {
    phext_buffer doc, next;
    TEST("test_coordinate_based_remove");
    phext_buffer_init(&doc);
    phext_buffer_init(&next);
    tappend(&doc, LIT("aaa\x17" "bbb\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj"));
    REMOVE_STEP(doc, next, "1.1.1/1.1.1/1.1.1", "\x17" "bbb\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/1.1.1/1.1.2", "\x18" "ccc\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/1.1.1/1.2.1", "\x19" "ddd\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/1.1.1/2.1.1", "\x1A" "eee\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/1.1.2/1.1.1", "\x1C" "fff\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/1.2.1/1.1.1", "\x1D" "ggg\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.1/2.1.1/1.1.1", "\x1E" "hhh\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.1.2/1.1.1/1.1.1", "\x1F" "iii\x01" "jjj");
    REMOVE_STEP(doc, next, "1.2.1/1.1.1/1.1.1", "\x01" "jjj");
    REMOVE_STEP(doc, next, "2.1.1/1.1.1/1.1.1", "");
    phext_buffer_free(&doc);
    phext_buffer_free(&next);
}

static void test_range_based_replace(void) {
    phext_buffer out;
    phext_range range;
    TEST("test_range_based_replace");
    phext_buffer_init(&out);
    range.start = C("1.1.1/1.1.1/2.1.1");
    range.end = C("1.1.1/2.1.1/1.1.1");
    phext_range_replace(LIT("Before\x19" "text to be replaced\x1C" "also this\x1D" "and this\x17" "After"),
                        range, LIT(""), &out);
    CHECK_BUF(&out, "Before\x19\x17" "After");

    range.start = C("2.1.1/1.1.1/1.1.1");
    range.end = C("3.1.1/1.1.1/1.1.1");
    phext_range_replace(LIT("Before\x01" "Library two\x01" "Library three\x01" "Library four"),
                        range, LIT(""), &out);
    CHECK_BUF(&out, "Before\x01\x01" "Library four");
    phext_buffer_free(&out);
}

static void test_next_scroll(void) {
    phext_positioned_scroll ps;
    phext_coordinate next_start;
    phext_buffer remaining, coord_text;
    TEST("test_next_scroll");
    ps = phext_positioned_scroll_new();
    phext_buffer_init(&remaining);
    phext_buffer_init(&coord_text);
    phext_next_scroll(LIT("3A\x17" "B2\x18" "C1"), C("1.1.1/1.1.1/1.1.1"),
                      &ps, &next_start, &remaining);
    phext_coordinate_to_string(ps.coord, &coord_text);
    CHECK_BUF(&coord_text, "1.1.1/1.1.1/1.1.1");
    CHECK_BUF(&ps.scroll, "3A");
    phext_coordinate_to_string(next_start, &coord_text);
    CHECK_BUF(&coord_text, "1.1.1/1.1.1/1.1.2");
    CHECK_BUF(&remaining, "B2\x18" "C1");
    phext_buffer_free(&ps.scroll);
    phext_buffer_free(&remaining);
    phext_buffer_free(&coord_text);
}

static void check_phokens(const unsigned char *doc, size_t len,
                          const char *const *coords, const char *const *scrolls,
                          size_t count) {
    phext_scrolls tokens;
    size_t i;
    phext_scrolls_init(&tokens);
    phext_phokenize(doc, len, &tokens);
    CHECK(tokens.len == count);
    if (tokens.len == count) {
        for (i = 0; i < count; i++) {
            phext_buffer coord_text;
            phext_buffer_init(&coord_text);
            phext_coordinate_to_string(tokens.items[i].coord, &coord_text);
            g_checks++;
            if (!buf_eq(&coord_text, (const unsigned char *)coords[i], strlen(coords[i]))) {
                g_failures++;
                printf("FAIL [%s] phoken %lu coord: got [%s] want [%s]\n", g_test,
                       (unsigned long)i, coord_text.data, coords[i]);
            }
            g_checks++;
            if (!buf_eq(&tokens.items[i].scroll, (const unsigned char *)scrolls[i],
                        strlen(scrolls[i]))) {
                g_failures++;
                printf("FAIL [%s] phoken %lu scroll mismatch\n", g_test, (unsigned long)i);
            }
            phext_buffer_free(&coord_text);
        }
    }
    phext_scrolls_free(&tokens);
}

static void test_phokenize(void) {
    static const char *const c1[] = {"1.1.1/1.1.1/1.1.1", "1.1.1/1.1.1/1.1.2", "1.1.1/1.1.1/1.1.3", "1.1.1/1.1.1/1.1.4"};
    static const char *const s1[] = {"one", "two", "three", "four"};
    static const char *const c2[] = {"1.1.1/1.1.1/1.1.1", "2.1.1/1.1.1/1.1.1", "2.2.1/1.1.1/1.1.1",
                                     "2.2.2/1.1.1/1.1.1", "2.2.2/2.1.1/1.1.1", "2.2.2/2.2.1/1.1.1",
                                     "2.2.2/2.2.2/1.1.1", "2.2.2/2.2.2/2.1.1", "2.2.2/2.2.2/2.2.1",
                                     "2.2.2/2.2.2/2.2.2"};
    static const char *const s2[] = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"};
    static const char *const c3[] = {"1.1.1/1.1.1/1.1.1", "1.1.1/1.1.1/1.1.2", "1.1.1/1.1.1/1.2.1",
                                     "1.1.1/1.1.1/2.1.1", "1.1.1/1.1.2/1.1.1", "1.1.1/1.2.1/1.1.1",
                                     "1.1.1/2.1.1/1.1.1", "1.1.2/1.1.1/1.1.1", "1.2.1/1.1.1/1.1.1",
                                     "2.1.1/1.1.1/1.1.1"};
    static const char *const s3[] = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"};
    static const char *const c4[] = {"2.1.1/1.1.1/1.1.1"};
    static const char *const s4[] = {"stuff here"};
    TEST("test_phokenize");
    check_phokens(LIT("one\x17" "two\x17" "three\x17" "four"), c1, s1, 4);
    check_phokens(LIT("one\x01" "two\x1F" "three\x1E" "four\x1D" "five\x1C" "six\x1A" "seven\x19" "eight\x18" "nine\x17" "ten"),
                  c2, s2, 10);
    check_phokens(LIT("one\x17" "two\x18" "three\x19" "four\x1A" "five\x1C" "six\x1D" "seven\x1E" "eight\x1F" "nine\x01" "ten"),
                  c3, s3, 10);
    check_phokens(LIT("\x1A\x1C\x1D\x1E\x1F\x01" "stuff here"), c4, s4, 1);
}

static void test_last_empty_scroll(void) {
    size_t start, end;
    phext_coordinate best, target;
    phext_buffer got;
    TEST("test_last_empty_scroll");
    phext_buffer_init(&got);
    target = C("1.1.1/1.1.1/1.1.2");
    phext_get_subspace_coordinates(LIT("hello\x17" "world\x17"), target, &start, &end, &best);
    CHECK(start == 6);
    CHECK(end == 11);
    CHECK(phext_coordinate_equal(best, target));
    phext_fetch(LIT("hello\x17" "world\x17"), target, &got);
    CHECK_BUF(&got, "world");
    phext_buffer_free(&got);
}

#define MERGE_CHECK(a, b, expected) do { \
    phext_buffer _o; phext_buffer_init(&_o); \
    phext_merge(LIT(a), LIT(b), &_o); \
    CHECK_BUF(&_o, expected); \
    phext_buffer_free(&_o); \
} while (0)

static void test_merge(void) {
    TEST("test_merge");
    MERGE_CHECK("3A\x17" "B2", "4C\x17" "D1", "3A4C\x17" "B2D1");
    MERGE_CHECK("Hello \x17" "I've come to talk", "Darkness, my old friend.\x17" " with you again.",
                "Hello Darkness, my old friend.\x17" "I've come to talk with you again.");
    MERGE_CHECK("One\x17" "Two\x18" "Three\x19" "Four", "1\x17" "2\x18" "3\x19" "4",
                "One1\x17" "Two2\x18" "Three3\x19" "Four4");
    MERGE_CHECK("\x1A\x1C\x1D\x1E\x1F\x01" "stuff here", "\x1A\x1C\x1D\x1E" "precursor here\x1F\x01" "and more",
                "\x1E" "precursor here\x01" "stuff hereand more");
    MERGE_CHECK("\x01\x01" " Library at 3.1.1/1.1.1/1.1.1 \x1F" " Shelf at 3.2.1/1.1.1/1.1.1",
                "\x01\x01\x01" " Library 4.1.1/1.1.1/1.1.1 \x1E" " Series at 4.1.2/1.1.1/1.1.1",
                "\x01\x01" " Library at 3.1.1/1.1.1/1.1.1 \x1F" " Shelf at 3.2.1/1.1.1/1.1.1\x01" " Library 4.1.1/1.1.1/1.1.1 \x1E" " Series at 4.1.2/1.1.1/1.1.1");
    MERGE_CHECK("\x1D" " Collection at 1.1.1/2.1.1/1.1.1\x1C" " Volume at 1.1.1/2.2.1/1.1.1",
                "\x1D\x1D" " Collection at 1.1.1/3.1.1/1.1.1\x1C" " Volume at 1.1.1/3.2.1/1.1.1",
                "\x1D" " Collection at 1.1.1/2.1.1/1.1.1\x1C" " Volume at 1.1.1/2.2.1/1.1.1\x1D" " Collection at 1.1.1/3.1.1/1.1.1\x1C" " Volume at 1.1.1/3.2.1/1.1.1");
    MERGE_CHECK("\x1A" "Book #2 Part 1\x1A" "Book #3 Part 1", "\x1A" " + Part II\x1A" " + Part Deux",
                "\x1A" "Book #2 Part 1 + Part II\x1A" "Book #3 Part 1 + Part Deux");
    MERGE_CHECK("AA\x01" "BB\x01" "CC", "__\x01" "__\x01" "__", "AA__\x01" "BB__\x01" "CC__");
}

static void test_subtract(void) {
    phext_buffer out;
    TEST("test_subtract");
    phext_buffer_init(&out);
    phext_subtract(LIT("Here's scroll one.\x17" "Scroll two."),
                   LIT("Just content at the first scroll"), &out);
    CHECK_BUF(&out, "\x17" "Scroll two.");
    phext_buffer_free(&out);
}

static void test_normalize(void) {
    phext_buffer out;
    TEST("test_normalize");
    phext_buffer_init(&out);
    phext_normalize(LIT("\x17" "Scroll two\x18\x18\x18\x18"), &out);
    CHECK_BUF(&out, "\x17" "Scroll two");
    phext_buffer_free(&out);
}

static void test_expand(void) {
    phext_buffer doc, next;
    int i;
    TEST("test_expand");
    phext_buffer_init(&doc);
    phext_buffer_init(&next);
    tappend(&doc, LIT("nothing but line breaks\n" "to test expansion to scrolls\n" "line 3"));
    {
        static const char *const stages[] = {
            "nothing but line breaks\x17" "to test expansion to scrolls\x17" "line 3",
            "nothing but line breaks\x18" "to test expansion to scrolls\x18" "line 3",
            "nothing but line breaks\x19" "to test expansion to scrolls\x19" "line 3",
            "nothing but line breaks\x1A" "to test expansion to scrolls\x1A" "line 3",
            "nothing but line breaks\x1C" "to test expansion to scrolls\x1C" "line 3",
            "nothing but line breaks\x1D" "to test expansion to scrolls\x1D" "line 3",
            "nothing but line breaks\x1E" "to test expansion to scrolls\x1E" "line 3",
            "nothing but line breaks\x1F" "to test expansion to scrolls\x1F" "line 3",
            "nothing but line breaks\x01" "to test expansion to scrolls\x01" "line 3",
            "nothing but line breaks\x01" "to test expansion to scrolls\x01" "line 3"
        };
        for (i = 0; i < 10; i++) {
            phext_expand(doc.data, doc.len, &next);
            g_checks++;
            if (!buf_eq(&next, (const unsigned char *)stages[i], strlen(stages[i]))) {
                g_failures++;
                printf("FAIL [%s] expand stage %d mismatch\n", g_test, i + 1);
            }
            buf_swap(&doc, &next);
        }
    }
    phext_buffer_free(&doc);
    phext_buffer_free(&next);
}

static void test_contract(void) {
    phext_buffer out, out2;
    TEST("test_contract");
    phext_buffer_init(&out);
    phext_buffer_init(&out2);
    phext_contract(LIT("A more complex example than expand\x01" "----\x1F" "++++\x1E" "____\x1D" "oooo\x1C" "====\x1A" "zzzz\x19" "gggg\x18" "....\x17" "qqqq"), &out);
    CHECK_BUF(&out, "A more complex example than expand\x1F" "----\x1E" "++++\x1D" "____\x1C" "oooo\x1A" "====\x19" "zzzz\x18" "gggg\x17" "....\n" "qqqq");
    phext_contract(out.data, out.len, &out2);
    CHECK_BUF(&out2, "A more complex example than expand\x1E" "----\x1D" "++++\x1C" "____\x1A" "oooo\x19" "====\x18" "zzzz\x17" "gggg\n" "....\n" "qqqq");
    phext_buffer_free(&out);
    phext_buffer_free(&out2);
}

static int read_file(const char *path, phext_buffer *out) {
    FILE *f = fopen(path, "rb");
    unsigned char chunk[8192];
    size_t n;
    if (f == NULL) {
        return 0;
    }
    phext_buffer_reset(out);
    while ((n = fread(chunk, 1, sizeof(chunk), f)) > 0) {
        tappend(out, chunk, n);
    }
    fclose(f);
    return 1;
}

static void test_fs_read_write(void) {
    const char *filename = "unit-test.phext";
    const char *initial = "a simple phext doc with three scrolls\x17" "we just want to verify\x17" "that all of our breaks are making it through rust's fs layer.\x18" "section 2\x19" "chapter 2\x1A" "book 2\x1C" "volume 2\x1D" "collection 2\x1E" "series 2\x1F" "shelf 2\x01" "library 2";
    FILE *f;
    phext_buffer prior, message;
    TEST("test_fs_read_write");
    phext_buffer_init(&prior);
    phext_buffer_init(&message);
    f = fopen(filename, "wb");
    CHECK(f != NULL);
    if (f != NULL) {
        fwrite(initial, 1, strlen(initial), f);
        fclose(f);
    }
    CHECK(read_file(filename, &prior) == 1);
    CHECK(prior.len == strlen(initial) && memcmp(prior.data, initial, prior.len) == 0);
    phext_replace(prior.data, prior.len, C("2.1.1/1.1.1/1.1.1"), LIT("still lib 2"), &message);
    CHECK_BUF(&message, "a simple phext doc with three scrolls\x17" "we just want to verify\x17" "that all of our breaks are making it through rust's fs layer.\x18" "section 2\x19" "chapter 2\x1A" "book 2\x1C" "volume 2\x1D" "collection 2\x1E" "series 2\x1F" "shelf 2\x01" "still lib 2");
    remove(filename);
    phext_buffer_free(&prior);
    phext_buffer_free(&message);
}

static void test_replace_create(void) {
    phext_buffer out;
    TEST("test_replace_create");
    phext_buffer_init(&out);
    phext_replace(LIT("A\x17" "B\x17" "C\x18" "D\x19" "E\x1A" "F\x1C" "G\x1D" "H\x1E" "I\x1F" "J\x01" "K"),
                  C("3.1.1/1.1.1/1.1.1"), LIT("L"), &out);
    CHECK_BUF(&out, "A\x17" "B\x17" "C\x18" "D\x19" "E\x1A" "F\x1C" "G\x1D" "H\x1E" "I\x1F" "J\x01" "K\x01" "L");
    phext_buffer_free(&out);
}

static void test_summary(void) {
    phext_buffer out;
    TEST("test_summary");
    phext_buffer_init(&out);
    phext_create_summary(LIT("A short phext\nSecond line\x17" "second scroll............................."), &out);
    CHECK_BUF(&out, "A short phext...");
    phext_create_summary(LIT("very terse"), &out);
    CHECK_BUF(&out, "very terse");
    phext_buffer_free(&out);
}

static void test_navmap(void) {
    phext_buffer out;
    TEST("test_navmap");
    phext_buffer_init(&out);
    phext_navmap("http://127.0.0.1/api/v1/index/",
                 LIT("Just a couple of scrolls.\x17" "Second scroll\x17" "Third scroll"), &out);
    CHECK_BUF(&out, "<ul>\n<li><a href=\"http://127.0.0.1/api/v1/index/1.1.1;1.1.1;1.1.1\">1.1.1/1.1.1/1.1.1 Just a couple of scrolls.</a></li>\n<li><a href=\"http://127.0.0.1/api/v1/index/1.1.1;1.1.1;1.1.2\">1.1.1/1.1.1/1.1.2 Second scroll</a></li>\n<li><a href=\"http://127.0.0.1/api/v1/index/1.1.1;1.1.1;1.1.3\">1.1.1/1.1.1/1.1.3 Third scroll</a></li>\n</ul>\n");
    phext_buffer_free(&out);
}

static void test_textmap(void) {
    phext_buffer out;
    TEST("test_textmap");
    phext_buffer_init(&out);
    phext_textmap(LIT("Just a couple of scrolls.\x17" "Second scroll\x17" "Third scroll"), &out);
    CHECK_BUF(&out, "* 1.1.1/1.1.1/1.1.1: Just a couple of scrolls.\n* 1.1.1/1.1.1/1.1.2: Second scroll\n* 1.1.1/1.1.1/1.1.3: Third scroll\n");
    phext_buffer_free(&out);
}

static void test_larger_coordinates(void) {
    phext_buffer result, map;
    phext_coordinate coord;
    TEST("test_larger_coordinates");
    phext_buffer_init(&result);
    phext_buffer_init(&map);
    coord = C("111.222.333/444.555.666/777.888.999");
    phext_insert(LIT(""), coord, LIT("Hello World"), &result);
    phext_textmap(result.data, result.len, &map);
    CHECK(result.len == 4997);
    CHECK_BUF(&map, "* 111.222.333/444.555.666/777.888.999: Hello World\n");
    phext_buffer_free(&result);
    phext_buffer_free(&map);
}

static void test_phext_index(void) {
    static const char *example = "first scroll\x17" "second scroll\x18" "second section\x19" "second chapter\x1A" "book 2\x1C" "volume 2\x1D" "collection 2\x1E" "series 2\x1F" "shelf 2\x01" "library 2";
    phext_buffer result;
    size_t offset = 0;
    TEST("test_phext_index");
    phext_buffer_init(&result);
    phext_index((const unsigned char *)example, strlen(example), &result);
    CHECK_BUF(&result, "0\x17" "13\x18" "27\x19" "42\x1A" "57\x1C" "64\x1D" "73\x1E" "86\x1F" "95\x01" "103");

    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.1.1/1.1.1"), &offset); CHECK(offset == 0);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.1.1/1.1.2"), &offset); CHECK(offset == 13);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.1.1/1.2.1"), &offset); CHECK(offset == 27);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.1.1/2.1.1"), &offset); CHECK(offset == 42);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.1.2/1.1.1"), &offset); CHECK(offset == 57);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/1.2.1/1.1.1"), &offset); CHECK(offset == 64);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.1/2.1.1/1.1.1"), &offset); CHECK(offset == 73);
    phext_offset((const unsigned char *)example, strlen(example), C("1.1.2/1.1.1/1.1.1"), &offset); CHECK(offset == 86);
    phext_offset((const unsigned char *)example, strlen(example), C("1.2.1/1.1.1/1.1.1"), &offset); CHECK(offset == 95);
    phext_offset((const unsigned char *)example, strlen(example), C("2.1.1/1.1.1/1.1.1"), &offset); CHECK(offset == 103);
    phext_offset((const unsigned char *)example, strlen(example), C("2.1.1/1.1.1/1.2.1"), &offset); CHECK(offset == 103);
    CHECK(strlen(example) == 112);
    phext_buffer_free(&result);
}

static void test_scroll_manifest(void) {
    static const char *example = "first scroll\x17" "second scroll\x18" "second section\x19" "second chapter\x1A" "book 2\x1C" "volume 2\x1D" "collection 2\x1E" "series 2\x1F" "shelf 2\x01" "library 2";
    static const char *const texts[] = {
        "00000000000000000000", "first scroll", "second scroll", "second section",
        "second chapter", "book 2", "volume 2", "collection 2", "series 2",
        "shelf 2", "library 2"
    };
    static const char *const hashes[] = {
        "7e79edd92a62a048e1cd24ffab542e34", "ba9d944e4967e29d48bae69ac2999699",
        "2fe1b2040314ac66f132dd3b4926157c", "fddb6916753b6f4e0b5281469134778b",
        "16ab5b1a0a997db95ec215a3bf2c57b3", "0f20f79bf36f63e8fba25cc6765e2d0d",
        "7ead0c6fef43adb446fe3bda6fb0adc7", "78c12298931c6edede92962137a9280a",
        "0f35100c84df601a490b7b63d7e8c0a8", "3bbf7e67cb33d613a906bc5a3cbefd95",
        "2e7fdd387196a8a2706ccb9ad6792bc3"
    };
    phext_buffer result, expected;
    int i;
    TEST("test_scroll_manifest");
    phext_buffer_init(&result);
    phext_buffer_init(&expected);
    for (i = 0; i < 11; i++) {
        char hex[33];
        phext_checksum((const unsigned char *)texts[i], strlen(texts[i]), hex);
        g_checks++;
        if (strcmp(hex, hashes[i]) != 0) {
            g_failures++;
            printf("FAIL [%s] checksum(\"%s\"): got %s want %s\n", g_test, texts[i], hex, hashes[i]);
        }
    }
    phext_manifest((const unsigned char *)example, strlen(example), &result);
    tappend_str(&expected, hashes[1]); tpush(&expected, PHEXT_SCROLL_BREAK);
    tappend_str(&expected, hashes[2]); tpush(&expected, PHEXT_SECTION_BREAK);
    tappend_str(&expected, hashes[3]); tpush(&expected, PHEXT_CHAPTER_BREAK);
    tappend_str(&expected, hashes[4]); tpush(&expected, PHEXT_BOOK_BREAK);
    tappend_str(&expected, hashes[5]); tpush(&expected, PHEXT_VOLUME_BREAK);
    tappend_str(&expected, hashes[6]); tpush(&expected, PHEXT_COLLECTION_BREAK);
    tappend_str(&expected, hashes[7]); tpush(&expected, PHEXT_SERIES_BREAK);
    tappend_str(&expected, hashes[8]); tpush(&expected, PHEXT_SHELF_BREAK);
    tappend_str(&expected, hashes[9]); tpush(&expected, PHEXT_LIBRARY_BREAK);
    tappend_str(&expected, hashes[10]);
    g_checks++;
    if (!buf_eq(&result, expected.data, expected.len)) {
        g_failures++;
        printf("FAIL [%s] manifest mismatch\n", g_test);
    }
    phext_buffer_free(&result);
    phext_buffer_free(&expected);
}

static void test_phext_soundex_v1(void) {
    phext_buffer out;
    TEST("test_phext_soundex_v1");
    phext_buffer_init(&out);
    phext_soundex_v1(LIT("it was the best of scrolls\x17" "it was the worst of scrolls\x17" "aaa\x17" "bbb\x17" "ccc\x17" "ddd\x17" "eee\x17" "fff\x17" "ggg\x17" "hhh\x17" "iii\x17" "jjj\x17" "kkk\x17" "lll\x18" "mmm\x18" "nnn\x18" "ooo\x18" "ppp\x19" "qqq\x19" "rrr\x19" "sss\x19" "ttt\x1A" "uuu\x1A" "vvv\x1A" "www\x1A" "xxx\x1A" "yyy\x1A" "zzz"), &out);
    CHECK_BUF(&out, "36\x17" "41\x17" "1\x17" "4\x17" "7\x17" "10\x17" "1\x17" "4\x17" "7\x17" "1\x17" "1\x17" "7\x17" "7\x17" "13\x18" "16\x18" "16\x18" "1\x18" "4\x19" "7\x19" "19\x19" "7\x19" "10\x1A" "1\x1A" "4\x1A" "1\x1A" "7\x1A" "1\x1A" "7");
    phext_buffer_free(&out);
}

static void test_insert_performance_2k_scrolls(void) {
    const char *doc1 = "the quick brown fox jumped over the lazy dog";
    phext_buffer doc, next;
    phext_coordinate coord;
    int x = 0;
    double t0, elapsed;
    size_t i, phext_tokens = 0, scroll_breaks = 0, section_breaks = 0, chapter_breaks = 0;
    TEST("test_insert_performance_2k_scrolls");
    phext_buffer_init(&doc);
    phext_buffer_init(&next);
    coord = C("1.1.1/1.1.1/1.1.1");
    t0 = now_ms();
    for (;;) {
        x += 1;
        if (x > 2000) break;
        if (coord.x.scroll > 32) phext_coordinate_section_break(&coord);
        if (coord.x.section > 32) phext_coordinate_chapter_break(&coord);
        if (coord.x.chapter > 32) phext_coordinate_book_break(&coord);
        phext_insert(doc.data, doc.len, coord, LIT("the quick brown fox jumped over the lazy dog"), &next);
        buf_swap(&doc, &next);
        phext_coordinate_scroll_break(&coord);
    }
    elapsed = now_ms() - t0;
    printf("  [%s] 2000 inserts took %.0f ms\n", g_test, elapsed);
    CHECK(elapsed < 5000);
    CHECK(phext_coordinate_equal(coord, C("1.1.1/1.1.1/2.31.17")));
    CHECK(strlen(doc1) == 44);
    for (i = 0; i < doc.len; i++) {
        if (phext_is_phext_break(doc.data[i])) phext_tokens += 1;
        if (doc.data[i] == PHEXT_SCROLL_BREAK) scroll_breaks += 1;
        if (doc.data[i] == PHEXT_SECTION_BREAK) section_breaks += 1;
        if (doc.data[i] == PHEXT_CHAPTER_BREAK) chapter_breaks += 1;
    }
    CHECK(phext_tokens == 1999);
    CHECK(scroll_breaks == 1937);
    CHECK(section_breaks == 61);
    CHECK(chapter_breaks == 1);
    CHECK(doc.len == 2000 * 44 + 1999);
    phext_buffer_free(&doc);
    phext_buffer_free(&next);
}

static void test_insert_performance_medium_scrolls(void) {
    const char *doc_template = "the quick brown fox jumped over the lazy dog\n";
    phext_buffer doc1, doc, next;
    phext_coordinate coord;
    int x;
    double t0, elapsed;
    size_t i, phext_tokens = 0, line_breaks = 0, scroll_breaks = 0, section_breaks = 0, chapter_breaks = 0;
    TEST("test_insert_performance_medium_scrolls");
    phext_buffer_init(&doc1);
    phext_buffer_init(&doc);
    phext_buffer_init(&next);
    for (x = 0; x < 1000; x++) {
        tappend_str(&doc1, doc_template);
    }
    coord = C("1.1.1/1.1.1/1.1.1");
    t0 = now_ms();
    x = 0;
    for (;;) {
        x += 1;
        if (x > 25) break;
        if (coord.x.scroll > 5) phext_coordinate_section_break(&coord);
        if (coord.x.section > 5) phext_coordinate_chapter_break(&coord);
        if (coord.x.chapter > 5) phext_coordinate_book_break(&coord);
        phext_insert(doc.data, doc.len, coord, doc1.data, doc1.len, &next);
        buf_swap(&doc, &next);
        phext_coordinate_scroll_break(&coord);
    }
    elapsed = now_ms() - t0;
    printf("  [%s] 25 medium inserts took %.0f ms\n", g_test, elapsed);
    CHECK(elapsed < 1000);
    CHECK(phext_coordinate_equal(coord, C("1.1.1/1.1.1/1.5.6")));
    CHECK(doc1.len == 45000);
    for (i = 0; i < doc.len; i++) {
        if (phext_is_phext_break(doc.data[i])) phext_tokens += 1;
        if (doc.data[i] == PHEXT_LINE_BREAK) line_breaks += 1;
        if (doc.data[i] == PHEXT_SCROLL_BREAK) scroll_breaks += 1;
        if (doc.data[i] == PHEXT_SECTION_BREAK) section_breaks += 1;
        if (doc.data[i] == PHEXT_CHAPTER_BREAK) chapter_breaks += 1;
    }
    CHECK(phext_tokens == 25024);
    CHECK(line_breaks == 25000);
    CHECK(scroll_breaks == 20);
    CHECK(section_breaks == 4);
    CHECK(chapter_breaks == 0);
    CHECK(doc.len == 25 * (45000 - 1000) + 25024);
    phext_buffer_free(&doc1);
    phext_buffer_free(&doc);
    phext_buffer_free(&next);
}

static void test_new_operators(void) {
    phext_positioned_scroll ps;
    phext_coordinate coord;
    phext_range range;
    phext_zcoordinate zc;
    phext_ycoordinate yc;
    phext_xcoordinate xc;
    TEST("test_new_operators");
    ps = phext_positioned_scroll_new();
    CHECK(ps.scroll.len == 0);
    CHECK(phext_coordinate_equal(ps.coord, C("1.1.1/1.1.1/1.1.1")));
    phext_buffer_free(&ps.scroll);

    coord = phext_coordinate_new();
    zc = phext_zcoordinate_new();
    yc = phext_ycoordinate_new();
    xc = phext_xcoordinate_new();
    CHECK(coord.z.library == zc.library && coord.z.shelf == zc.shelf && coord.z.series == zc.series);
    CHECK(coord.y.collection == yc.collection && coord.y.volume == yc.volume && coord.y.book == yc.book);
    CHECK(coord.x.chapter == xc.chapter && coord.x.section == xc.section && coord.x.scroll == xc.scroll);

    range = phext_range_new();
    CHECK(phext_coordinate_equal(range.start, phext_coordinate_new()));
    CHECK(phext_coordinate_equal(range.end, phext_coordinate_new()));

    CHECK(zc.library == 1 && zc.shelf == 1 && zc.series == 1);
    CHECK(yc.collection == 1 && yc.volume == 1 && yc.book == 1);
    CHECK(xc.chapter == 1 && xc.section == 1 && xc.scroll == 1);
}

static void test_hash_support(void) {
    phext_scrolls stuff;
    const phext_buffer *got;
    phext_buffer serialized;
    TEST("test_hash_support");
    phext_scrolls_init(&stuff);
    phext_buffer_init(&serialized);
    phext_explode(LIT("hello world\x17\x17\x17" "scroll 4\x01" "Library 2"), &stuff);
    got = phext_map_get(&stuff, C("1.1.1/1.1.1/1.1.1"));
    CHECK(got != NULL && buf_eq(got, LIT("hello world")));
    got = phext_map_get(&stuff, C("1.1.1/1.1.1/1.1.4"));
    CHECK(got != NULL && buf_eq(got, LIT("scroll 4")));
    got = phext_map_get(&stuff, C("2.1.1/1.1.1/1.1.1"));
    CHECK(got != NULL && buf_eq(got, LIT("Library 2")));
    phext_map_insert(&stuff, C("2.3.4/5.6.7/8.9.1"), LIT("random insertion"));
    phext_implode(&stuff, &serialized);
    CHECK_BUF(&serialized, "hello world\x17\x17\x17" "scroll 4\x01" "Library 2"
              "\x1F\x1F\x1E\x1E\x1E\x1D\x1D\x1D\x1D\x1C\x1C\x1C\x1C\x1C\x1A\x1A\x1A\x1A\x1A\x1A"
              "\x19\x19\x19\x19\x19\x19\x19\x18\x18\x18\x18\x18\x18\x18\x18" "random insertion");
    phext_scrolls_free(&stuff);
    phext_buffer_free(&serialized);
}

static void test_subspace_filter(void) {
    TEST("test_subspace_filter");
    /* the Rust test is a comment-only TODO sketch with no assertions;
     * ported as an empty test so the suite inventories match */
}

static void test_emoji_in_scroll(void) {
    phext_buffer update, result;
    TEST("test_emoji_in_scroll");
    phext_buffer_init(&update);
    phext_buffer_init(&result);
    phext_insert(LIT(""), C("1.1.1/1.1.1/1.1.1"), LIT("Lux \xF0\x9F\x94\x86 test"), &update);
    phext_fetch(update.data, update.len, C("1.1.1/1.1.1/1.1.1"), &result);
    CHECK_BUF(&result, "Lux \xF0\x9F\x94\x86 test");
    phext_buffer_free(&update);
    phext_buffer_free(&result);
}

static void test_coordinate_above_999_parse_print_round_trip(void) {
    const char *address = "1000.1001.1002/1003.1004.1005/1006.1007.1008";
    phext_coordinate coord, parsed, zero;
    phext_buffer out;
    TEST("test_coordinate_above_999_parse_print_round_trip");
    phext_buffer_init(&out);
    coord = C(address);
    CHECK(coord.z.library == 1000);
    CHECK(coord.z.shelf == 1001);
    CHECK(coord.z.series == 1002);
    CHECK(coord.y.collection == 1003);
    CHECK(coord.y.volume == 1004);
    CHECK(coord.y.book == 1005);
    CHECK(coord.x.chapter == 1006);
    CHECK(coord.x.section == 1007);
    CHECK(coord.x.scroll == 1008);
    CHECK(phext_coordinate_validate(coord) == 1);
    phext_coordinate_to_string(coord, &out);
    CHECK_BUF(&out, "1000.1001.1002/1003.1004.1005/1006.1007.1008");
    phext_coordinate_to_urlencoded(coord, &out);
    CHECK_BUF(&out, "1000.1001.1002;1003.1004.1005;1006.1007.1008");

    CHECK(phext_coordinate_parse(address, &parsed) == PHEXT_OK);
    CHECK(phext_coordinate_equal(parsed, coord));
    phext_coordinate_to_string(parsed, &out);
    CHECK_BUF(&out, "1000.1001.1002/1003.1004.1005/1006.1007.1008");

    zero = C("0.1.1/1.1.1/1.1.1");
    CHECK(phext_coordinate_validate(zero) == 0);
    phext_coordinate_to_string(zero, &out);
    CHECK_BUF(&out, "");
    phext_buffer_free(&out);
}

static void test_scroll_breaks_advance_past_999(void) {
    phext_buffer doc, got;
    phext_scrolls parts;
    int i;
    TEST("test_scroll_breaks_advance_past_999");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    phext_scrolls_init(&parts);
    for (i = 1; i <= 1001; i++) {
        char text[16];
        if (i > 1) tpush(&doc, PHEXT_SCROLL_BREAK);
        sprintf(text, "s%d", i);
        tappend_str(&doc, text);
    }
    {
        static const int wanted[] = {998, 999, 1000, 1001};
        int k;
        for (k = 0; k < 4; k++) {
            char addr[64], want[16];
            sprintf(addr, "1.1.1/1.1.1/1.1.%d", wanted[k]);
            sprintf(want, "s%d", wanted[k]);
            phext_fetch(doc.data, doc.len, C(addr), &got);
            g_checks++;
            if (!buf_eq(&got, (const unsigned char *)want, strlen(want))) {
                g_failures++;
                printf("FAIL [%s] fetch at scroll %d\n", g_test, wanted[k]);
            }
        }
    }
    phext_phokenize(doc.data, doc.len, &parts);
    CHECK(parts.len == 1001);
    if (parts.len == 1001) {
        CHECK(parts.items[997].coord.x.scroll == 998);
        CHECK(parts.items[998].coord.x.scroll == 999);
        CHECK(parts.items[999].coord.x.scroll == 1000);
        CHECK(parts.items[1000].coord.x.scroll == 1001);
    }
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
    phext_scrolls_free(&parts);
}

static void test_fetch_and_explode_above_999(void) {
    phext_coordinate coord, first;
    phext_buffer doc, got;
    phext_scrolls map;
    const phext_buffer *hit;
    TEST("test_fetch_and_explode_above_999");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    phext_scrolls_init(&map);
    coord = C("1.1.1/1.1.1/1000.1.1");
    phext_replace(LIT(""), coord, LIT("beyond the cap"), &doc);
    phext_fetch(doc.data, doc.len, coord, &got);
    CHECK_BUF(&got, "beyond the cap");
    phext_explode(doc.data, doc.len, &map);
    hit = phext_map_get(&map, coord);
    CHECK(hit != NULL && buf_eq(hit, LIT("beyond the cap")));
    first = C("1.1.1/1.1.1/1.1.1");
    phext_fetch(doc.data, doc.len, first, &got);
    CHECK_BUF(&got, "");
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
    phext_scrolls_free(&map);
}

static void test_emoji_boundary_crash(void) {
    phext_buffer text, summary;
    int i;
    TEST("test_emoji_boundary_crash");
    phext_buffer_init(&text);
    phext_buffer_init(&summary);
    for (i = 0; i < 29; i++) tpush(&text, (unsigned char)'a');
    tappend(&text, LIT("\xF0\x9F\x94\x86")); /* emoji at bytes 29-32 */
    phext_create_summary(text.data, text.len, &summary);
    CHECK(summary.len > 0);
    phext_buffer_free(&text);
    phext_buffer_free(&summary);
}

/* ----------------------------------------------------------------------------------------------------------
 * test_phokenize.rs ports
 * ---------------------------------------------------------------------------------------------------------- */

/* the same LCG as the Rust tests, so generated documents are identical */
typedef struct lcg {
    uint64_t state;
} lcg;

static uint64_t lcg_next(lcg *rng) {
    rng->state = rng->state * (uint64_t)6364136223846793005ULL +
                 (uint64_t)1442695040888963407ULL;
    return rng->state >> 33;
}

static void random_doc(lcg *rng, phext_buffer *doc) {
    static const char *const pieces[] = {
        "a", "bc", "\xC3\xBC", "\xE2\x98\x83", "\xF0\x9F\x9C\x81", "\n", " ", "text"
    };
    static const unsigned char breaks[] = {0x17, 0x18, 0x19, 0x1A, 0x1C, 0x1D, 0x1E, 0x1F, 0x01};
    uint64_t count = lcg_next(rng) % 60;
    uint64_t i;
    phext_buffer_reset(doc);
    for (i = 0; i < count; i++) {
        if (lcg_next(rng) % 3 == 0) {
            uint64_t run = 1 + lcg_next(rng) % 3;
            uint64_t j;
            for (j = 0; j < run; j++) {
                tpush(doc, breaks[lcg_next(rng) % 9]);
            }
        } else {
            const char *piece = pieces[lcg_next(rng) % 8];
            tappend(doc, (const unsigned char *)piece, strlen(piece));
        }
    }
}

static const char *const EDGE_DOCS[] = {
    "",
    "one scroll\nwith two lines",
    "a\x17" "b\x18" "c\x19" "d\x1A" "e\x1C" "f\x1D" "g\x1E" "h\x1F" "i\x01" "j",
    "\x17\x17" "lead\x17\x17\x17" "gap\x01\x01\x17" "deep\x17",
    "trailing one\x17",
    "trailing two\x17\x17",
    "\x01\x1F\x1E\x1D\x1C\x1A\x19\x18\x17",
    NULL, /* unicode doc: built from bytes below */
    "\n\n\x17\n"
};

static const unsigned char EDGE_DOC_UNICODE[] = {
    0xC3, 0xBC, 'n', 0xC3, 0xAF, 'c', 0xC3, 0xB6, 'd', 0xC3, 0xA9, ' ',
    0xE2, 0x9C, 0x93, 0x1F, 's', 'h', 'e', 'l', 'f', ' ',
    0xE2, 0x98, 0x83, 0x1A, 'b', 'o', 'e', 'k', ' ', 0xC3, 0xBC, 0x17,
    0xF0, 0x9F, 0x9C, 0x81
};

static int scrolls_equal(const phext_scrolls *a, const phext_scrolls *b) {
    size_t i;
    if (a->len != b->len) return 0;
    for (i = 0; i < a->len; i++) {
        if (!phext_coordinate_equal(a->items[i].coord, b->items[i].coord)) return 0;
        if (!buf_eq(&a->items[i].scroll, b->items[i].scroll.data, b->items[i].scroll.len)) return 0;
    }
    return 1;
}

static void clone_scrolls(const phext_scrolls *from, phext_scrolls *to) {
    size_t i;
    phext_scrolls_reset(to);
    for (i = 0; i < from->len; i++) {
        phext_scrolls_push(to, from->items[i].coord,
                           from->items[i].scroll.data, from->items[i].scroll.len);
    }
}

/* the non-empty scrolls of a document, as explode sees them (Rust: content) */
static void content_of(const unsigned char *doc, size_t len, phext_scrolls *out) {
    size_t i, w = 0;
    phext_explode(doc, len, out);
    for (i = 0; i < out->len; i++) {
        if (out->items[i].scroll.len > 0) {
            if (w != i) {
                out->items[w] = out->items[i];
            }
            w += 1;
        } else {
            phext_buffer_free(&out->items[i].scroll);
        }
    }
    out->len = w;
}

static void list_remove_coord(phext_scrolls *list, phext_coordinate coord) {
    size_t i;
    for (i = 0; i < list->len; i++) {
        if (phext_coordinate_equal(list->items[i].coord, coord)) {
            phext_buffer_free(&list->items[i].scroll);
            if (i + 1 < list->len) {
                memmove(&list->items[i], &list->items[i + 1],
                        (list->len - i - 1) * sizeof(phext_positioned_scroll));
            }
            list->len -= 1;
            return;
        }
    }
}

/* the next_scroll-loop reference tokenizer (Rust: reference) */
static void reference_pairs(const unsigned char *doc, size_t len, phext_scrolls *out) {
    phext_buffer temp, remaining;
    phext_coordinate coord = phext_default_coordinate();
    phext_buffer_init(&temp);
    phext_buffer_init(&remaining);
    tappend(&temp, doc, len);
    phext_scrolls_reset(out);
    for (;;) {
        phext_positioned_scroll item = phext_positioned_scroll_new();
        phext_coordinate next_coord;
        phext_next_scroll(temp.data, temp.len, coord, &item, &next_coord, &remaining);
        coord = next_coord;
        phext_scrolls_push(out, item.coord, item.scroll.data, item.scroll.len);
        phext_buffer_free(&item.scroll);
        buf_swap(&temp, &remaining);
        if (temp.len == 0) break;
    }
    phext_buffer_free(&temp);
    phext_buffer_free(&remaining);
}

static void check_doc_pairs(const unsigned char *doc, size_t len) {
    phext_scrolls fast, slow;
    phext_scrolls_init(&fast);
    phext_scrolls_init(&slow);
    phext_phokenize(doc, len, &fast);
    reference_pairs(doc, len, &slow);
    g_checks++;
    if (!scrolls_equal(&fast, &slow)) {
        g_failures++;
        printf("FAIL [%s] phokenize != next_scroll loop for doc len %lu\n",
               g_test, (unsigned long)len);
    }
    phext_scrolls_free(&fast);
    phext_scrolls_free(&slow);
}

static void phokenize_matches_the_next_scroll_loop(void) {
    size_t i;
    lcg rng;
    phext_buffer doc;
    TEST("phokenize_matches_the_next_scroll_loop");
    phext_buffer_init(&doc);
    for (i = 0; i < 9; i++) {
        if (i == 7) {
            check_doc_pairs(EDGE_DOC_UNICODE, sizeof(EDGE_DOC_UNICODE));
        } else {
            check_doc_pairs((const unsigned char *)EDGE_DOCS[i], strlen(EDGE_DOCS[i]));
        }
    }
    rng.state = 0x5eed;
    for (i = 0; i < 5000; i++) {
        random_doc(&rng, &doc);
        check_doc_pairs(doc.data, doc.len);
    }
    phext_buffer_free(&doc);
}

/* a growable set of documents (Rust: documents()) */
typedef struct doc_set {
    phext_buffer *docs;
    size_t len;
    size_t cap;
} doc_set;

static void doc_set_add(doc_set *set, const unsigned char *bytes, size_t len) {
    if (set->len == set->cap) {
        set->cap = set->cap != 0 ? set->cap * 2 : 32;
        set->docs = (phext_buffer *)realloc(set->docs, set->cap * sizeof(phext_buffer));
    }
    phext_buffer_init(&set->docs[set->len]);
    tappend(&set->docs[set->len], bytes, len);
    set->len += 1;
}

static void doc_set_free(doc_set *set) {
    size_t i;
    for (i = 0; i < set->len; i++) {
        phext_buffer_free(&set->docs[i]);
    }
    free(set->docs);
    set->docs = NULL;
    set->len = set->cap = 0;
}

static const char *g_fixture_dir = ".";

static void build_documents(uint64_t seed, size_t count, doc_set *set) {
    lcg rng;
    size_t i;
    phext_buffer doc, helios;
    rng.state = seed;
    phext_buffer_init(&doc);
    phext_buffer_init(&helios);
    for (i = 0; i < 9; i++) {
        if (i == 7) {
            doc_set_add(set, EDGE_DOC_UNICODE, sizeof(EDGE_DOC_UNICODE));
        } else {
            doc_set_add(set, (const unsigned char *)EDGE_DOCS[i], strlen(EDGE_DOCS[i]));
        }
    }
    doc_set_add(set, LIT("a\x18" "b\x19" "c"));
    doc_set_add(set, LIT("a\x17" "b\x17"));
    doc_set_add(set, LIT("x\x17"));
    doc_set_add(set, LIT("\x19\x1A" "a"));
    doc_set_add(set, LIT("a\x18" "b\x19" "c\x1A" "d\x1C" "e\x1D" "f\x1E" "g\x1F" "h\x01" "i"));
    {
        phext_buffer deep;
        phext_buffer_init(&deep);
        tpush_n(&deep, PHEXT_LIBRARY_BREAK, 1001);
        tappend_str(&deep, "deep");
        tpush_n(&deep, PHEXT_SHELF_BREAK, 1001);
        tappend_str(&deep, "deeper");
        doc_set_add(set, deep.data, deep.len);
        phext_buffer_free(&deep);
    }
    for (i = 0; i < count; i++) {
        random_doc(&rng, &doc);
        doc_set_add(set, doc.data, doc.len);
    }
    {
        char path[1024];
        sprintf(path, "%s/regression-1-helios.phext", g_fixture_dir);
        if (read_file(path, &helios)) {
            doc_set_add(set, helios.data, helios.len);
        }
    }
    phext_buffer_free(&doc);
    phext_buffer_free(&helios);
}

static void edits_act_on_exactly_the_target_scroll(void) {
    doc_set docs;
    lcg rng;
    size_t d;
    TEST("edits_act_on_exactly_the_target_scroll");
    docs.docs = NULL;
    docs.len = docs.cap = 0;
    build_documents(0xc0de, 1500, &docs);
    rng.state = 0xc0de;
    for (d = 0; d < docs.len; d++) {
        const unsigned char *doc = docs.docs[d].data;
        size_t len = docs.docs[d].len;
        phext_scrolls before, tokens, targets;
        size_t t, i;
        phext_scrolls_init(&before);
        phext_scrolls_init(&tokens);
        phext_scrolls_init(&targets);
        content_of(doc, len, &before);
        phext_phokenize(doc, len, &tokens);
        for (i = 0; i < tokens.len; i++) {
            phext_coordinate after = tokens.items[i].coord;
            phext_coordinate deeper = tokens.items[i].coord;
            phext_scrolls_push(&targets, tokens.items[i].coord, LIT(""));
            phext_coordinate_scroll_break(&after);
            phext_scrolls_push(&targets, after, LIT(""));
            phext_coordinate_section_break(&deeper);
            phext_scrolls_push(&targets, deeper, LIT(""));
        }
        for (i = 0; i < 4; i++) {
            phext_coordinate random_coord;
            random_coord.z.library = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.z.shelf = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.z.series = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.y.collection = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.y.volume = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.y.book = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.x.chapter = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.x.section = 1 + (size_t)(lcg_next(&rng) % 3);
            random_coord.x.scroll = 1 + (size_t)(lcg_next(&rng) % 5);
            phext_scrolls_push(&targets, random_coord, LIT(""));
        }
        for (t = 0; t < targets.len; t++) {
            phext_coordinate target = targets.items[t].coord;
            const phext_buffer *hit = phext_map_get(&before, target);
            phext_buffer current, edited, got_content_dummy;
            phext_scrolls want, got;
            size_t ignored_offset = 0;
            phext_buffer_init(&current);
            phext_buffer_init(&edited);
            phext_buffer_init(&got_content_dummy);
            phext_scrolls_init(&want);
            phext_scrolls_init(&got);
            if (hit != NULL) {
                tappend(&current, hit->data, hit->len);
            }

            phext_fetch(doc, len, target, &edited);
            g_checks++;
            if (!buf_eq(&edited, current.data, current.len)) {
                g_failures++;
                printf("FAIL [%s] fetch at target %lu of doc %lu\n", g_test,
                       (unsigned long)t, (unsigned long)d);
            }

            clone_scrolls(&before, &want);
            phext_map_insert(&want, target, LIT("X"));
            phext_replace(doc, len, target, LIT("X"), &edited);
            content_of(edited.data, edited.len, &got);
            g_checks++;
            if (!scrolls_equal(&got, &want)) {
                g_failures++;
                printf("FAIL [%s] replace at target %lu of doc %lu\n", g_test,
                       (unsigned long)t, (unsigned long)d);
            }

            clone_scrolls(&before, &want);
            {
                phext_buffer extended;
                phext_buffer_init(&extended);
                tappend(&extended, current.data, current.len);
                tappend_str(&extended, "Y");
                phext_map_insert(&want, target, extended.data, extended.len);
                phext_insert(doc, len, target, LIT("Y"), &edited);
                content_of(edited.data, edited.len, &got);
                g_checks++;
                if (!scrolls_equal(&got, &want)) {
                    g_failures++;
                    printf("FAIL [%s] insert at target %lu of doc %lu\n", g_test,
                           (unsigned long)t, (unsigned long)d);
                }
                phext_buffer_free(&extended);
            }

            clone_scrolls(&before, &want);
            list_remove_coord(&want, target);
            phext_remove(doc, len, target, &edited);
            content_of(edited.data, edited.len, &got);
            g_checks++;
            if (!scrolls_equal(&got, &want)) {
                g_failures++;
                printf("FAIL [%s] remove at target %lu of doc %lu\n", g_test,
                       (unsigned long)t, (unsigned long)d);
            }

            phext_offset(doc, len, target, &ignored_offset);
            phext_buffer_free(&current);
            phext_buffer_free(&edited);
            phext_buffer_free(&got_content_dummy);
            phext_scrolls_free(&want);
            phext_scrolls_free(&got);
        }
        phext_scrolls_free(&before);
        phext_scrolls_free(&tokens);
        phext_scrolls_free(&targets);
    }
    doc_set_free(&docs);
}

static void missing_coordinates_between_scrolls_are_left_alone(void) {
    phext_buffer out;
    phext_coordinate between;
    TEST("missing_coordinates_between_scrolls_are_left_alone");
    phext_buffer_init(&out);
    between = C("1.1.1/1.1.1/1.1.2");
    phext_fetch(LIT("a\x18" "b\x19" "c"), between, &out);
    CHECK_BUF(&out, "");
    phext_replace(LIT("a\x18" "b\x19" "c"), between, LIT("X"), &out);
    CHECK_BUF(&out, "a\x17" "X\x18" "b\x19" "c");
    phext_insert(LIT("a\x18" "b\x19" "c"), between, LIT("Y"), &out);
    CHECK_BUF(&out, "a\x17" "Y\x18" "b\x19" "c");
    phext_remove(LIT("a\x18" "b\x19" "c"), between, &out);
    CHECK_BUF(&out, "a\x18" "b\x19" "c");
    phext_insert(LIT("x\x17"), between, LIT("Y"), &out);
    CHECK_BUF(&out, "x\x17" "Y");
    phext_fetch(LIT("a\x17" "b\x17"), between, &out);
    CHECK_BUF(&out, "b");
    phext_buffer_free(&out);
}

static void subtract_removes_only_scrolls_with_content_on_the_right(void) {
    doc_set docs;
    size_t i;
    phext_buffer out;
    TEST("subtract_removes_only_scrolls_with_content_on_the_right");
    docs.docs = NULL;
    docs.len = docs.cap = 0;
    build_documents(0x5b7, 1000, &docs);
    phext_buffer_init(&out);
    for (i = 0; i < docs.len; i++) {
        const phext_buffer *left = &docs.docs[i];
        const phext_buffer *right = &docs.docs[(i + 1) % docs.len];
        phext_scrolls left_content, mask, want, got;
        size_t k, w;
        phext_scrolls_init(&left_content);
        phext_scrolls_init(&mask);
        phext_scrolls_init(&want);
        phext_scrolls_init(&got);
        content_of(left->data, left->len, &left_content);
        content_of(right->data, right->len, &mask);
        clone_scrolls(&left_content, &want);
        w = 0;
        for (k = 0; k < want.len; k++) {
            if (phext_map_get(&mask, want.items[k].coord) == NULL) {
                if (w != k) want.items[w] = want.items[k];
                w += 1;
            } else {
                phext_buffer_free(&want.items[k].scroll);
            }
        }
        want.len = w;
        phext_subtract(left->data, left->len, right->data, right->len, &out);
        content_of(out.data, out.len, &got);
        g_checks++;
        if (!scrolls_equal(&got, &want)) {
            g_failures++;
            printf("FAIL [%s] subtract doc %lu\n", g_test, (unsigned long)i);
        }
        phext_scrolls_free(&left_content);
        phext_scrolls_free(&mask);
        phext_scrolls_free(&want);
        phext_scrolls_free(&got);
    }
    phext_subtract(LIT("\x17\x17" "lead"), LIT("a\x18" "b"), &out);
    CHECK_BUF(&out, "\x17\x17" "lead");
    phext_buffer_free(&out);
    doc_set_free(&docs);
}

static void offset_does_not_panic_before_the_first_scroll(void) {
    size_t offset = 999;
    TEST("offset_does_not_panic_before_the_first_scroll");
    phext_offset(LIT("\x19\x1A" "a"), C("1.1.1/1.1.1/1.1.1"), &offset);
    CHECK(offset == 0);
    phext_offset(LIT(""), C("2.2.2/2.2.2/2.2.2"), &offset);
    CHECK(offset == 0);
    phext_offset(LIT("ab\x17" "cd"), C("1.1.1/1.1.1/1.1.2"), &offset);
    CHECK(offset == 3);
    phext_offset(LIT("ab\x17" "cd"), C("1.1.1/1.1.1/1.1.9"), &offset);
    CHECK(offset == 3);
}

static void summaries_keep_multibyte_characters_whole(void) {
    phext_buffer out;
    TEST("summaries_keep_multibyte_characters_whole");
    phext_buffer_init(&out);
    /* U+010A is C4 8A in UTF-8; its low byte is 0x0A, a line break */
    phext_create_summary(LIT("\xC4\x8A" "bc"), &out);
    CHECK_BUF(&out, "\xC4\x8A" "bc");
    phext_create_summary(LIT("\xE6\x97\xA5\xE6\x9C\xAC\x17" "rest"), &out);
    CHECK_BUF(&out, "\xE6\x97\xA5\xE6\x9C\xAC" "...");
    phext_create_summary(LIT("one\ntwo"), &out);
    CHECK_BUF(&out, "one...");
    phext_buffer_free(&out);
}

static void explode_and_implode_roundtrip_the_same_scrolls(void) {
    lcg rng;
    phext_buffer doc, rebuilt;
    int i;
    TEST("explode_and_implode_roundtrip_the_same_scrolls");
    phext_buffer_init(&doc);
    phext_buffer_init(&rebuilt);
    rng.state = 0xfab1e;
    for (i = 0; i < 2000; i++) {
        phext_scrolls map, again, filled_map, filled_again;
        phext_scrolls_init(&map);
        phext_scrolls_init(&again);
        phext_scrolls_init(&filled_map);
        phext_scrolls_init(&filled_again);
        random_doc(&rng, &doc);
        phext_explode(doc.data, doc.len, &map);
        phext_implode(&map, &rebuilt);
        phext_explode(rebuilt.data, rebuilt.len, &again);
        content_of(doc.data, doc.len, &filled_map);
        content_of(rebuilt.data, rebuilt.len, &filled_again);
        g_checks++;
        if (!scrolls_equal(&filled_map, &filled_again)) {
            g_failures++;
            printf("FAIL [%s] roundtrip doc %d\n", g_test, i);
        }
        phext_scrolls_free(&map);
        phext_scrolls_free(&again);
        phext_scrolls_free(&filled_map);
        phext_scrolls_free(&filled_again);
    }
    phext_buffer_free(&doc);
    phext_buffer_free(&rebuilt);
}

static void a_large_phext_explodes_in_linear_time(void) {
    phext_buffer doc, rebuilt, toc;
    phext_scrolls map;
    int index;
    double t0, elapsed;
    size_t i, lines = 0;
    TEST("a_large_phext_explodes_in_linear_time");
    phext_buffer_init(&doc);
    phext_buffer_init(&rebuilt);
    phext_buffer_init(&toc);
    phext_scrolls_init(&map);
    for (index = 0; index < 50000; index++) {
        if (index > 0) {
            if (index % 1600 == 0) tpush(&doc, PHEXT_VOLUME_BREAK);
            else if (index % 40 == 0) tpush(&doc, PHEXT_BOOK_BREAK);
            else tpush(&doc, PHEXT_SCROLL_BREAK);
        }
        tappend_str(&doc, "kind: message\nauthor: bench\n---\nsome words about the topic here");
    }
    t0 = now_ms();
    phext_explode(doc.data, doc.len, &map);
    phext_implode(&map, &rebuilt);
    phext_textmap(doc.data, doc.len, &toc);
    elapsed = now_ms() - t0;
    printf("  [%s] 50000 scrolls explode+implode+textmap took %.0f ms\n", g_test, elapsed);
    CHECK(map.len == 50000);
    g_checks++;
    if (!buf_eq(&rebuilt, doc.data, doc.len)) {
        g_failures++;
        printf("FAIL [%s] rebuilt != original\n", g_test);
    }
    for (i = 0; i < toc.len; i++) {
        if (toc.data[i] == '\n') lines += 1;
    }
    CHECK(lines == 50000);
    CHECK(elapsed < 2000);
    phext_buffer_free(&doc);
    phext_buffer_free(&rebuilt);
    phext_buffer_free(&toc);
    phext_scrolls_free(&map);
}

/* ----------------------------------------------------------------------------------------------------------
 * regressions.rs port
 * ---------------------------------------------------------------------------------------------------------- */

static void helios_stalled_parse(void) {
    char path[1024];
    phext_buffer helios, msg, got, replaced;
    TEST("helios_stalled_parse");
    phext_buffer_init(&helios);
    phext_buffer_init(&msg);
    phext_buffer_init(&got);
    phext_buffer_init(&replaced);
    sprintf(path, "%s/regression-1-helios.phext", g_fixture_dir);
    CHECK(read_file(path, &helios) == 1);
    sprintf(path, "%s/regression-1-msg.txt", g_fixture_dir);
    CHECK(read_file(path, &msg) == 1);
    phext_fetch(helios.data, helios.len, C("1.1.1/1.1.1/1.1.1"), &got);
    CHECK(got.len == 358 || got.len == 370);
    phext_replace(helios.data, helios.len, C("2.1.100/1.1.1/1.1.1"),
                  msg.data, msg.len, &replaced);
    CHECK(replaced.len == 15150 || replaced.len == 15317);
    phext_buffer_free(&helios);
    phext_buffer_free(&msg);
    phext_buffer_free(&got);
    phext_buffer_free(&replaced);
}

/* ----------------------------------------------------------------------------------------------------------
 * src/test_binary.rs (libphext-rs 0.5.0) - same vectors, same names
 * ---------------------------------------------------------------------------------------------------------- */

static void test_encode_decode_round_trip(void) {
    phext_buffer scroll, back;
    size_t i;
    TEST("test_encode_decode_round_trip");
    phext_buffer_init(&scroll);
    phext_buffer_init(&back);

    /* empty payload: header line alone */
    CHECK(phext_encode_scroll(LIT(""), &scroll) == PHEXT_OK);
    CHECK_BUF(&scroll, "phext-binary:1:base64\n");
    CHECK(phext_decode_scroll(scroll.data, scroll.len, &back) == PHEXT_OK);
    CHECK(back.len == 0);

    /* every byte value */
    {
        unsigned char all[256];
        for (i = 0; i < 256; i++) {
            all[i] = (unsigned char)i;
        }
        CHECK(phext_encode_scroll(all, sizeof(all), &scroll) == PHEXT_OK);
        CHECK(phext_is_binary_scroll(scroll.data, scroll.len));
        CHECK(phext_decode_scroll(scroll.data, scroll.len, &back) == PHEXT_OK);
        CHECK_MEM(&back, all);
    }

    /* a plainly non-UTF-8 sequence */
    {
        static const unsigned char foreign[] = { 0xFF, 0xFE, 0x80, 0x00, 0x61, 0xC3, 0x28 };
        CHECK(phext_encode_scroll(foreign, sizeof(foreign), &scroll) == PHEXT_OK);
        CHECK(phext_decode_scroll(scroll.data, scroll.len, &back) == PHEXT_OK);
        CHECK_MEM(&back, foreign);
    }

    /* >= 1 MiB payload, deterministic pattern covering all byte values */
    {
        size_t big_len = 1024 * 1024 + 13;
        unsigned char *big = (unsigned char *)malloc(big_len);
        CHECK(big != NULL);
        for (i = 0; i < big_len; i++) {
            big[i] = (unsigned char)(i % 256);
        }
        CHECK(phext_encode_scroll(big, big_len, &scroll) == PHEXT_OK);
        CHECK(phext_decode_scroll(scroll.data, scroll.len, &back) == PHEXT_OK);
        CHECK(back.len == big_len && memcmp(back.data, big, big_len) == 0);
        free(big);
    }

    phext_buffer_free(&scroll);
    phext_buffer_free(&back);
}

static void test_decode_scroll_rejects_non_binary(void) {
    phext_buffer back;
    TEST("test_decode_scroll_rejects_non_binary");
    phext_buffer_init(&back);
    CHECK(phext_decode_scroll(LIT("just some text"), &back) == PHEXT_ENONE);
    CHECK(phext_decode_scroll(LIT(""), &back) == PHEXT_ENONE);
    /* header must be a complete line: no line break, no binary scroll */
    CHECK(phext_decode_scroll(LIT("phext-binary:1:base64"), &back) == PHEXT_ENONE);
    CHECK(!phext_is_binary_scroll(LIT("phext-binary:1:base64")));
    /* malformed base64 body: recognisably binary, undecodable */
    CHECK(phext_is_binary_scroll(LIT("phext-binary:1:base64\n!!! not base64 !!!")));
    CHECK(phext_decode_scroll(LIT("phext-binary:1:base64\n!!! not base64 !!!"), &back) == PHEXT_ENONE);
    phext_buffer_free(&back);
}

static void test_insert_and_fetch_binary(void) {
    static const unsigned char payload[] = { 0x00, 0x01, 0x02, 0xFE, 0xFF, 0x7F, 0x80 };
    phext_buffer doc, got, decoded, next;
    TEST("test_insert_and_fetch_binary");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    phext_buffer_init(&decoded);
    phext_buffer_init(&next);
    CHECK(phext_insert(LIT(""), C("1.1.1/1.1.1/1.1.1"), LIT("plain text scroll"), &doc) == PHEXT_OK);
    /* chained edits build into a scratch buffer and swap, as everywhere
     * in this suite (outputs are reset on entry; in == out unsupported) */
    CHECK(phext_insert_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"),
                              payload, sizeof(payload), &next) == PHEXT_OK);
    buf_swap(&doc, &next);
    /* the text scroll next door is untouched */
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "plain text scroll");
    /* the binary scroll fetches back byte-identical */
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"), &got) == PHEXT_OK);
    CHECK_MEM(&got, payload);
    /* and its stored form is the canonical binary scroll */
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"), &got) == PHEXT_OK);
    CHECK(phext_is_binary_scroll(got.data, got.len));
    CHECK(phext_decode_scroll(got.data, got.len, &decoded) == PHEXT_OK);
    CHECK_MEM(&decoded, payload);
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
    phext_buffer_free(&decoded);
    phext_buffer_free(&next);
}

static void test_fetch_binary_fallbacks(void) {
    phext_buffer doc, got;
    TEST("test_fetch_binary_fallbacks");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    CHECK(phext_insert(LIT(""), C("1.1.1/1.1.1/1.1.1"), LIT("hello"), &doc) == PHEXT_OK);
    /* a plain text scroll yields its own UTF-8 bytes */
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "hello");
    /* an unoccupied coordinate yields no bytes */
    CHECK(phext_fetch_binary(doc.data, doc.len, C("9.9.9/9.9.9/9.9.9"), &got) == PHEXT_OK);
    CHECK(got.len == 0);
    /* a malformed binary scroll yields its own bytes verbatim */
    CHECK(phext_insert(LIT(""), C("1.1.1/1.1.1/1.1.1"),
                       LIT("phext-binary:1:base64\n!!!"), &doc) == PHEXT_OK);
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "phext-binary:1:base64\n!!!");
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
}

static void test_update_rule_non_utf8_is_base64_verbatim(void) {
    /* payload deliberately includes dimension-break bytes (0x17, 0x1C):
     * armoured as base64, they round-trip as content, not structure */
    static const unsigned char payload[] = { 0xFF, 0x17, 0x1C, 0x80, 0x00 };
    phext_buffer doc, got;
    TEST("test_update_rule_non_utf8_is_base64_verbatim");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    CHECK(phext_replace_bytes(LIT(""), C("1.1.1/1.1.1/1.1.1"),
                              payload, sizeof(payload), &doc) == PHEXT_OK);
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK(phext_is_binary_scroll(got.data, got.len));
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_MEM(&got, payload);
    /* same rule through the insert entry point */
    CHECK(phext_insert_bytes(LIT(""), C("1.1.1/1.1.1/1.1.1"),
                             payload, sizeof(payload), &doc) == PHEXT_OK);
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_MEM(&got, payload);
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
}

static void test_update_rule_utf8_stays_text(void) {
    /* "ordinary text" + U+2713 CHECK MARK (E2 9C 93) */
    static const unsigned char text[] = "ordinary text \xE2\x9C\x93";
    phext_buffer doc, got;
    TEST("test_update_rule_utf8_stays_text");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    CHECK(phext_replace_bytes(LIT(""), C("1.1.1/1.1.1/1.1.1"),
                              text, sizeof(text) - 1, &doc) == PHEXT_OK);
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK(buf_eq(&got, text, sizeof(text) - 1));
    CHECK(!phext_is_binary_scroll(got.data, got.len));
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK(buf_eq(&got, text, sizeof(text) - 1));
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
}

static void test_ingest_foreign_byte_stream(void) {
    /* a phext byte stream whose second scroll is not valid UTF-8 */
    static const unsigned char stream[] =
        { 'h', 'e', 'l', 'l', 'o', 0x17, 0xFF, 0xFE, 0x41, 0x80 };
    static const unsigned char foreign[] = { 0xFF, 0xFE, 0x41, 0x80 };
    phext_buffer doc, got;
    TEST("test_ingest_foreign_byte_stream");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    CHECK(phext_ingest(stream, sizeof(stream), &doc) == PHEXT_OK);
    /* text scroll passes through verbatim */
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "hello");
    /* foreign scroll: stored as a binary scroll, reads back as the original bytes */
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"), &got) == PHEXT_OK);
    CHECK(phext_is_binary_scroll(got.data, got.len));
    CHECK(phext_fetch_binary(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"), &got) == PHEXT_OK);
    CHECK_MEM(&got, foreign);
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
}

static void test_ingest_canonical_phext_is_identity(void) {
    phext_buffer doc, back, next;
    TEST("test_ingest_canonical_phext_is_identity");
    phext_buffer_init(&doc);
    phext_buffer_init(&back);
    phext_buffer_init(&next);
    CHECK(phext_insert(LIT(""), C("1.1.1/1.1.1/1.1.1"), LIT("first"), &doc) == PHEXT_OK);
    CHECK(phext_insert(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"),
                       LIT("second \xE2\x9C\x93 scroll"), &next) == PHEXT_OK);
    buf_swap(&doc, &next);
    CHECK(phext_insert(doc.data, doc.len, C("2.1.1/1.3.1/1.1.1"), LIT("far away"), &next) == PHEXT_OK);
    buf_swap(&doc, &next);
    /* the scrolls themselves are what Rust built (guard against a
     * self-consistent corruption cancelling out of the identity check) */
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &back) == PHEXT_OK);
    CHECK_BUF(&back, "first");
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.2"), &back) == PHEXT_OK);
    CHECK_BUF(&back, "second \xE2\x9C\x93 scroll");
    CHECK(phext_fetch(doc.data, doc.len, C("2.1.1/1.3.1/1.1.1"), &back) == PHEXT_OK);
    CHECK_BUF(&back, "far away");
    CHECK(phext_ingest(doc.data, doc.len, &back) == PHEXT_OK);
    CHECK(back.len == doc.len && memcmp(back.data, doc.data, doc.len) == 0);
    phext_buffer_free(&doc);
    phext_buffer_free(&back);
    phext_buffer_free(&next);
}

static void test_ingest_empty_and_break_only_streams(void) {
    static const unsigned char breaks[] = { 0x17, 0x18 }; /* SCROLL_BREAK, SECTION_BREAK */
    phext_buffer doc, got;
    TEST("test_ingest_empty_and_break_only_streams");
    phext_buffer_init(&doc);
    phext_buffer_init(&got);
    CHECK(phext_ingest(LIT(""), &doc) == PHEXT_OK);
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "");
    CHECK(phext_ingest(breaks, sizeof(breaks), &doc) == PHEXT_OK);
    CHECK(phext_fetch(doc.data, doc.len, C("1.1.1/1.1.1/1.1.1"), &got) == PHEXT_OK);
    CHECK_BUF(&got, "");
    phext_buffer_free(&doc);
    phext_buffer_free(&got);
}

static void test_phokenize_bytes_matches_phokenize(void) {
    static const unsigned char doc[] = "alpha\x17" "beta\x18" "gamma";
    phext_scrolls text_parts, byte_parts;
    size_t i;
    TEST("test_phokenize_bytes_matches_phokenize");
    phext_scrolls_init(&text_parts);
    phext_scrolls_init(&byte_parts);
    CHECK(phext_phokenize(doc, sizeof(doc) - 1, &text_parts) == PHEXT_OK);
    CHECK(phext_phokenize_bytes(doc, sizeof(doc) - 1, &byte_parts) == PHEXT_OK);
    CHECK(text_parts.len == byte_parts.len);
    for (i = 0; i < text_parts.len && i < byte_parts.len; i++) {
        CHECK(phext_coordinate_compare(text_parts.items[i].coord, byte_parts.items[i].coord) == 0);
        CHECK(buf_eq(&byte_parts.items[i].scroll,
                     text_parts.items[i].scroll.data, text_parts.items[i].scroll.len));
    }
    phext_scrolls_free(&text_parts);
    phext_scrolls_free(&byte_parts);
}

/* C-side addition: the strict base64 acceptance table of the base64
 * crate's STANDARD engine, probed against the published Rust 0.5.0
 * library (decode_scroll over "phext-binary:1:base64\n" + body) */
static void test_base64_strictness(void) {
    static const unsigned char want_f[] = { 0x66 };
    static const unsigned char want_fo[] = { 0x66, 0x6F };
    static const unsigned char want_foo[] = { 0x66, 0x6F, 0x6F };
    static const unsigned char want_000[] = { 0x00, 0x00, 0x00 };
    static const unsigned char want_00[] = { 0x00, 0x00 };
    static const unsigned char want_0[] = { 0x00 };
    static const struct {
        const char *body; int ok; const unsigned char *want; size_t want_len;
    } cases[] = {
        { "Zg==",     1, want_f,   sizeof(want_f) },
        { "Zm8=",     1, want_fo,  sizeof(want_fo) },
        { "Zm9v",     1, want_foo, sizeof(want_foo) },
        { "AAAA",     1, want_000, sizeof(want_000) },
        { "AAA=",     1, want_00,  sizeof(want_00) },
        { "AA==",     1, want_0,   sizeof(want_0) },
        { "",         1, want_0,   0 },
        { "Zh==",     0, NULL, 0 }, /* non-zero trailing bits */
        { "Zm9=",     0, NULL, 0 }, /* non-zero trailing bits */
        { "Zg",       0, NULL, 0 }, /* padding required */
        { "Zg=",      0, NULL, 0 },
        { "Zm9vYg",   0, NULL, 0 },
        { "Zm9vYg=",  0, NULL, 0 },
        { "AAE",      0, NULL, 0 },
        { "AA",       0, NULL, 0 },
        { "Zg==AAAA", 0, NULL, 0 }, /* data after padding */
        { "Zg==Zg==", 0, NULL, 0 },
        { "====",     0, NULL, 0 },
        { "Z===",     0, NULL, 0 },
        { "####",     0, NULL, 0 }, /* foreign alphabet */
        { "Zm9 Yg==", 0, NULL, 0 }, /* whitespace is not skipped */
        { "Zm9vYg== ", 0, NULL, 0 }, /* length not a multiple of 4 */
    };
    phext_buffer scroll, back;
    size_t i;
    TEST("test_base64_strictness");
    phext_buffer_init(&scroll);
    phext_buffer_init(&back);
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        phext_status status;
        phext_buffer_reset(&scroll);
        tappend(&scroll, LIT("phext-binary:1:base64\n"));
        tappend(&scroll, (const unsigned char *)cases[i].body, strlen(cases[i].body));
        status = phext_decode_scroll(scroll.data, scroll.len, &back);
        if (cases[i].ok) {
            CHECK(status == PHEXT_OK);
            CHECK(buf_eq(&back, cases[i].want, cases[i].want_len));
        } else {
            CHECK(status == PHEXT_ENONE);
        }
    }
    phext_buffer_free(&scroll);
    phext_buffer_free(&back);
}

/* C-side addition (0.5.0 core): the lenient parser's digit accumulation
 * saturates at u64::MAX instead of wrapping (0.4.1 wrapped, and the C
 * port wrapped with it). Found by the differential fuzz (op 21) against
 * the published 0.5.0 library; see PARITY.md D-2. */
static void test_lenient_parse_saturates_at_u64_max(void) {
    phext_coordinate c;
    phext_buffer s;
    TEST("test_lenient_parse_saturates_at_u64_max");
    phext_buffer_init(&s);
    c = phext_to_coordinate("18446744073709551616.1.1/1.1.1/1.1.1"); /* 2^64 */
    CHECK(c.z.library == (size_t)18446744073709551615ULL);
    c = phext_to_coordinate("99999999999999999999999.1.1/1.1.1/1.1.1");
    CHECK(c.z.library == (size_t)18446744073709551615ULL);
    /* exactly u64::MAX still parses exactly */
    c = phext_to_coordinate("18446744073709551615.1.1/1.1.1/1.1.1");
    CHECK(c.z.library == (size_t)18446744073709551615ULL);
    phext_coordinate_to_string(c, &s);
    CHECK_BUF(&s, "18446744073709551615.1.1/1.1.1/1.1.1");
    phext_buffer_free(&s);
}

/* ----------------------------------------------------------------------------------------------------------
 * src/test_seal.rs (libphext-rs 0.5.0) - same vectors, same names, plus
 * the trailing-data verdicts probed against the published library.
 * The Rust corpus test reads ../unit-test.phext, which the published
 * .crate package does not ship; the C port seals the helios regression
 * fixture instead - the same role (a real, multi-scroll phext).
 * ---------------------------------------------------------------------------------------------------------- */

#ifdef PHEXT_WITH_XZ

static void test_seal_round_trip_real_phext(void) {
    char path[1024];
    phext_buffer corpus, sealed, restored;
    static const unsigned char xz_magic[] = { 0xFD, 0x37, 0x7A, 0x58, 0x5A, 0x00 };
    TEST("test_seal_round_trip_real_phext");
    phext_buffer_init(&corpus);
    phext_buffer_init(&sealed);
    phext_buffer_init(&restored);
    sprintf(path, "%s/regression-1-helios.phext", g_fixture_dir);
    CHECK(phext_seal_compiled() == 1);
    CHECK(read_file(path, &corpus));
    CHECK(corpus.len > 0);
    CHECK(phext_seal(corpus.data, corpus.len, &sealed) == PHEXT_OK);
    CHECK(sealed.len > 0);
    CHECK(sealed.len >= sizeof(xz_magic) && memcmp(sealed.data, xz_magic, sizeof(xz_magic)) == 0);
    CHECK(phext_unseal_string(sealed.data, sealed.len, &restored) == PHEXT_OK);
    CHECK(restored.len == corpus.len && memcmp(restored.data, corpus.data, corpus.len) == 0);
    phext_buffer_free(&corpus);
    phext_buffer_free(&sealed);
    phext_buffer_free(&restored);
}

static void test_seal_round_trip_empty_and_small(void) {
    phext_buffer sealed, back;
    TEST("test_seal_round_trip_empty_and_small");
    phext_buffer_init(&sealed);
    phext_buffer_init(&back);
    CHECK(phext_seal(LIT(""), &sealed) == PHEXT_OK);
    CHECK(phext_unseal_string(sealed.data, sealed.len, &back) == PHEXT_OK);
    CHECK_BUF(&back, "");
    CHECK(phext_seal(LIT("hello phext"), &sealed) == PHEXT_OK);
    CHECK(phext_unseal(sealed.data, sealed.len, &back) == PHEXT_OK);
    CHECK_BUF(&back, "hello phext");
    phext_buffer_free(&sealed);
    phext_buffer_free(&back);
}

static void test_seal_carrying_binary_scrolls(void) {
    static const unsigned char doc[] =
        "cover text\x17" "phext-binary:1:base64\nAAEC/f7/fw==\x17" "after";
    phext_buffer sealed, restored;
    TEST("test_seal_carrying_binary_scrolls");
    phext_buffer_init(&sealed);
    phext_buffer_init(&restored);
    CHECK(phext_seal(doc, sizeof(doc) - 1, &sealed) == PHEXT_OK);
    CHECK(phext_unseal_string(sealed.data, sealed.len, &restored) == PHEXT_OK);
    CHECK(buf_eq(&restored, doc, sizeof(doc) - 1));
    phext_buffer_free(&sealed);
    phext_buffer_free(&restored);
}

static void test_seal_is_deterministic(void) {
    static const unsigned char doc[] =
        "the same phext, sealed twice\x17" "the same phext, sealed twice";
    phext_buffer first, second;
    TEST("test_seal_is_deterministic");
    phext_buffer_init(&first);
    phext_buffer_init(&second);
    CHECK(phext_seal(doc, sizeof(doc) - 1, &first) == PHEXT_OK);
    CHECK(phext_seal(doc, sizeof(doc) - 1, &second) == PHEXT_OK);
    CHECK(first.len == second.len && memcmp(first.data, second.data, first.len) == 0);
    phext_buffer_free(&first);
    phext_buffer_free(&second);
}

static void test_unseal_rejects_non_xz_data(void) {
    phext_buffer back;
    TEST("test_unseal_rejects_non_xz_data");
    phext_buffer_init(&back);
    CHECK(phext_unseal(LIT("this is not an xz stream"), &back) == PHEXT_EINVAL);
    CHECK(phext_unseal(LIT(""), &back) == PHEXT_EINVAL);
    CHECK(phext_unseal_string(LIT("phext, but unsealed"), &back) == PHEXT_EINVAL);
    phext_buffer_free(&back);
}

/* C-side addition: the Rust decoder errors on ANY bytes after the
 * stream end - probed against the published library (trailing junk,
 * trailing zero padding, a second concatenated stream, truncation) */
static void test_unseal_rejects_trailing_data(void) {
    phext_buffer sealed, back;
    TEST("test_unseal_rejects_trailing_data");
    phext_buffer_init(&sealed);
    phext_buffer_init(&back);
    CHECK(phext_seal(LIT("hello phext"), &sealed) == PHEXT_OK);
    /* trailing junk */
    tappend(&sealed, LIT("junk"));
    CHECK(phext_unseal(sealed.data, sealed.len, &back) == PHEXT_EINVAL);
    /* trailing zero padding */
    CHECK(phext_seal(LIT("hello phext"), &sealed) == PHEXT_OK);
    {
        static const unsigned char zeros[] = { 0, 0, 0, 0 };
        tappend(&sealed, zeros, sizeof(zeros));
    }
    CHECK(phext_unseal(sealed.data, sealed.len, &back) == PHEXT_EINVAL);
    /* a second concatenated stream */
    CHECK(phext_seal(LIT("hello phext"), &sealed) == PHEXT_OK);
    {
        phext_buffer again;
        phext_buffer_init(&again);
        CHECK(phext_seal(LIT("hello phext"), &again) == PHEXT_OK);
        tappend(&sealed, again.data, again.len);
        phext_buffer_free(&again);
    }
    CHECK(phext_unseal(sealed.data, sealed.len, &back) == PHEXT_EINVAL);
    /* truncated stream */
    CHECK(phext_seal(LIT("hello phext"), &sealed) == PHEXT_OK);
    CHECK(sealed.len > 10);
    CHECK(phext_unseal(sealed.data, sealed.len - 10, &back) == PHEXT_EINVAL);
    phext_buffer_free(&sealed);
    phext_buffer_free(&back);
}

static void test_unseal_string_rejects_non_utf8(void) {
    static const unsigned char raw[] = { 0xFF, 0x00, 0xFE };
    phext_buffer sealed, back;
    TEST("test_unseal_string_rejects_non_utf8");
    phext_buffer_init(&sealed);
    phext_buffer_init(&back);
    CHECK(phext_seal_bytes(raw, sizeof(raw), &sealed) == PHEXT_OK);
    CHECK(phext_unseal(sealed.data, sealed.len, &back) == PHEXT_OK);
    CHECK_MEM(&back, raw);
    CHECK(phext_unseal_string(sealed.data, sealed.len, &back) == PHEXT_EINVAL);
    phext_buffer_free(&sealed);
    phext_buffer_free(&back);
}

#else /* !PHEXT_WITH_XZ */

static void test_seal_not_compiled(void) {
    phext_buffer back;
    TEST("test_seal_not_compiled");
    phext_buffer_init(&back);
    CHECK(phext_seal_compiled() == 0);
    CHECK(phext_seal_bytes(LIT("hello phext"), &back) == PHEXT_ENOSEAL);
    CHECK(phext_seal(LIT("hello phext"), &back) == PHEXT_ENOSEAL);
    CHECK(phext_unseal(LIT("hello phext"), &back) == PHEXT_ENOSEAL);
    CHECK(phext_unseal_string(LIT("hello phext"), &back) == PHEXT_ENOSEAL);
    phext_buffer_free(&back);
}

#endif /* PHEXT_WITH_XZ */

int main(int argc, char **argv) {
    if (argc > 1) {
        g_fixture_dir = argv[1];
    }

    /* test_lib.rs */
    test_coordinate_parsing();
    test_to_urlencoded();
    test_dimension_fetches();
    test_coordinates_invalid();
    test_coordinates_valid();
    test_url_encoding();
    test_realistic_parse();
    test_dead_reckoning();
    test_line_break();
    test_more_cowbell();
    test_coordinate_based_insert();
    test_coordinate_based_replace();
    test_coordinate_based_remove();
    test_range_based_replace();
    test_next_scroll();
    test_phokenize();
    test_last_empty_scroll();
    test_merge();
    test_subtract();
    test_normalize();
    test_expand();
    test_contract();
    test_fs_read_write();
    test_replace_create();
    test_summary();
    test_navmap();
    test_textmap();
    test_larger_coordinates();
    test_phext_index();
    test_scroll_manifest();
    test_phext_soundex_v1();
    test_insert_performance_2k_scrolls();
    test_insert_performance_medium_scrolls();
    test_new_operators();
    test_hash_support();
    test_subspace_filter();
    test_emoji_in_scroll();
    test_coordinate_above_999_parse_print_round_trip();
    test_scroll_breaks_advance_past_999();
    test_fetch_and_explode_above_999();
    test_emoji_boundary_crash();

    /* test_phokenize.rs */
    phokenize_matches_the_next_scroll_loop();
    edits_act_on_exactly_the_target_scroll();
    missing_coordinates_between_scrolls_are_left_alone();
    subtract_removes_only_scrolls_with_content_on_the_right();
    offset_does_not_panic_before_the_first_scroll();
    summaries_keep_multibyte_characters_whole();
    explode_and_implode_roundtrip_the_same_scrolls();
    a_large_phext_explodes_in_linear_time();

    /* regressions.rs */
    helios_stalled_parse();

    /* test_binary.rs (0.5.0) */
    test_encode_decode_round_trip();
    test_decode_scroll_rejects_non_binary();
    test_insert_and_fetch_binary();
    test_fetch_binary_fallbacks();
    test_update_rule_non_utf8_is_base64_verbatim();
    test_update_rule_utf8_stays_text();
    test_ingest_foreign_byte_stream();
    test_ingest_canonical_phext_is_identity();
    test_ingest_empty_and_break_only_streams();
    test_phokenize_bytes_matches_phokenize();
    test_base64_strictness();
    test_lenient_parse_saturates_at_u64_max();

    /* test_seal.rs (0.5.0) */
#ifdef PHEXT_WITH_XZ
    test_seal_round_trip_real_phext();
    test_seal_round_trip_empty_and_small();
    test_seal_carrying_binary_scrolls();
    test_seal_is_deterministic();
    test_unseal_rejects_non_xz_data();
    test_unseal_rejects_trailing_data();
    test_unseal_string_rejects_non_utf8();
#else
    test_seal_not_compiled();
#endif

    printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures != 0;
}
