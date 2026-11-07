/* uchar.h - C11 Unicode character types and conversion functions (F7) */
#ifndef _UCHAR_H
#define _UCHAR_H

#include <stddef.h>
#include <stdint.h>
#include <wchar.h> /* for mbstate_t */

/* C11 7.28: char16_t/char32_t are uint_least16_t/uint_least32_t */
typedef uint_least16_t char16_t;
typedef uint_least32_t char32_t;

#ifdef __cplusplus
extern "C" {
#endif

size_t c16rtomb(char *__restrict s, char16_t c16, mbstate_t *__restrict ps);
size_t mbrtoc16(char16_t *__restrict pc16, const char *__restrict s,
		size_t n, mbstate_t *__restrict ps);
size_t c32rtomb(char *__restrict s, char32_t c32, mbstate_t *__restrict ps);
size_t mbrtoc32(char32_t *__restrict pc32, const char *__restrict s,
		size_t n, mbstate_t *__restrict ps);

#ifdef __cplusplus
}
#endif

#endif /* _UCHAR_H */
