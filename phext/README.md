# phext/ — the phext library for C

A C99 port of **libphext-rs 0.4.1** (wbic16/libphext-rs, `src/phext.rs`),
giving C developers the same phext capabilities the Rust crate gives Rust
developers: 9-dimensional coordinates, scroll fetch / insert / replace /
remove, phokenize, explode / implode, merge / subtract, expand / contract,
normalize, textmap / navmap / manifest, index / offset, and XXH3-128 scroll
checksums.

Coordinates are 1-based with **no upper bound** (the 999 cap was removed in
libphext-rs 0.4.0). Scrolls are text; the nine phext delimiters are ASCII
control bytes (0x17–0x1F subset plus 0x01), with the line break (0x0A)
counted as a break inside scroll text.

## Files

- `phext.h` — the public header. Everything is documented there.
- `phext.c` — the implementation (single translation unit, no dependencies
  beyond libc).
- `tests/` — the conformance suite: libphext-rs's own `test_lib.rs`,
  `test_phokenize.rs`, and `regressions.rs` ported case-for-case with the
  same vectors and expected values, plus the two regression fixtures.

## Build & test

```sh
cd tests
make test            # builds with $(CC) (default cc) and runs the suite
make CC=../../tcc TCCFLAGS=-B../..   # dogfood: build the suite with phcc itself
```

The test binary takes the fixture directory as an optional argument
(default: the tests directory itself).

```sh
./test_phext /path/to/tests
```

## C idiom mapping (from the parity audit)

| Rust | C |
| --- | --- |
| `String` results | `phext_buffer` out-params (owned, length-authoritative, NUL-terminated) |
| `&str` inputs | `(const unsigned char *ptr, size_t len)` pairs |
| `Vec<PositionedScroll>` | `phext_scrolls` array |
| `HashMap<Coordinate, String>` | the same `phext_scrolls`, kept sorted; `phext_map_get` / `phext_map_insert` |
| `Result<T, E>` / panics on bad input | `phext_status` return codes (`PHEXT_OK`, `PHEXT_ENOMEM`, `PHEXT_EFORMAT`, `PHEXT_ENUMBER`) |
| iterators | index loops over `phext_scrolls` |

Strict coordinate parsing diverges from Rust in one deliberate way: Rust's
`TryFrom` *panics* on non-numeric or overflowing components; the C API
returns `PHEXT_EFORMAT` / `PHEXT_ENUMBER` instead — errors are return
codes, never traps. The full parity matrix and divergence list live with
the audit that produced this port.
