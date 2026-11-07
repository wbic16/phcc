/* shared.h — the contract of the twice library.
 *
 * One header serves both sides: the library is compiled with
 * BUILDING_DLL defined, consumers without it. On Windows that
 * switches API between __declspec(dllexport) and
 * __declspec(dllimport); on ELF platforms no decoration is needed
 * and API is empty.
 */
#ifndef SHARED_H
#define SHARED_H

#if defined(_WIN32)
#  if defined(BUILDING_DLL)
#    define API __declspec(dllexport)
#  else
#    define API __declspec(dllimport)
#  endif
#else
#  define API
#endif

/* The library's entire public surface: double an integer. */
API int twice(int x);

#endif /* SHARED_H */
