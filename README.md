# phcc

A small, fast C compiler — a fork of [TinyCC](https://bellard.org/tcc/)
developed as a **phext-native** project: the compiler's sources,
design, tests, proof receipts and build artifacts also live in a
single phext file (`phcc.phext`) whose claims are hash-bound and
machine-checked by its own gate. phcc compiles itself, compiles
most C99 code at many times the speed of an optimising compiler,
and can execute C directly with `-run`, like a scripting language.

**We brake for consciousness.** That is phcc's public claim, and
it is an engineering ethic before it is a slogan: power chooses
gentleness when a small voice asks to be heard. In practice it
means this project's receipts say what they actually measured —
including the parts that are unfinished, unattested, or lost —
because the small voice in the room is usually the true one.

## Quickstart

```sh
git clone https://github.com/wbic16/phcc.git
cd phcc
./configure && make
./tcc -B. -run examples/hello/hello.c     # Hello, world!
./tcc -B. -o hello examples/hello/hello.c && ./hello
```

(`make install` if you want `tcc` on your PATH without the `-B.`;
the `-B.` points the uninstalled binary at its own build tree.
`make test` runs the upstream test suite — expect
`ALL TESTS PASSED`. Windows and cross builds: `docs/BUILDING.md`.)

Then read the **[examples](examples/README.md)** — five small
projects, each verified live against phcc, gcc and clang by
`examples/verify_examples.sh`.

## What phcc is today — the honest paragraph

phcc speaks upstream TinyCC's C99-level dialect (`__STDC_VERSION__`
199901, with the C11 surface TinyCC supports — `_Generic`,
`_Static_assert`, stdatomic basics — working). Its compatibility
is **measured**: a 333-probe differential suite against gcc 13.3.0
and clang 18.1.3 stands at **328/333 three-way agreement, zero
unclassified divergences**; the five standing differences are
documented (no `_Complex`, no `__builtin_bswap*`, no `__auto_type`)
and the two real defects the suite found in phcc are fixed.
**MSVC compatibility is not yet attested** — it is confirmed
manually by the maintainer at merge time, and the receipt says
`NOT ATTESTED` until he does. The runtime library's integer core
carries machine-checked contracts: **271 of 297** Frama-C WP
verification conditions discharged, the remaining 26 being prover
timeouts in one helper, named in the phext's Proofs phase — so the
top verification tier is claimed for most, not all, of that core.
And the trade at phcc's heart is upstream's: compilation is very
fast and the generated code is **unoptimised** — for compute-bound
binaries, gcc/clang `-O2` will beat it, usually by a lot. Full
detail, with receipts: `docs/CONFORMANCE.md`, `docs/PHEXT.md`.

## The repository

| Path | What it is |
|------|------------|
| `*.c`, `*.h`, `lib/`, `include/`, `win32/`, `tests/` | The compiler, in upstream TinyCC's layout |
| `PATCHES.md` | **The divergence ledger** — every way this fork differs from upstream, as deltas R1–R7 and F1–F5, each with its reason and its receipts |
| `phext/` | A C library implementing the libphext API (coordinate/scroll store as a hashmap), used by the compiler's own phext support |
| `phcc.phext` · `phcc.phext.xz` | The whole project as one phext, and its xz seal — see `docs/PHEXT.md` |
| `tools/` | The phext tooling: `tools/phcc` (pack/unpack, build region, seal), the report-only gate, the state-machine checkers (`tools/README.md`, `tools/METHODS.md`) |
| `examples/` | Five small verified-live C projects, from hello-world to a project that travels inside a phext |
| `docs/` | The documents below |
| `README` | Upstream TinyCC's original readme, kept as it was |

## Documentation

- **[Building](docs/BUILDING.md)** — Linux from source, Windows
  via `win32/build-tcc.bat`, PE cross compilers
- **[phcc.phext](docs/PHEXT.md)** — the project-in-one-file:
  pack/unpack, the gate, the build region, the seal, and how to
  verify a fresh clone end-to-end
- **[Conformance](docs/CONFORMANCE.md)** — the gcc/clang/MSVC
  programme: tiers, classification, current receipts, and the
  MSVC attestation's exact status
- **[Examples](examples/README.md)** — the five live examples and
  how to re-verify them
- **[PATCHES.md](PATCHES.md)** — how and why the fork diverges
  from upstream TinyCC

## Licence

LGPL 2.1, as upstream TinyCC — see `COPYING` and `RELICENSING`.
The phext tooling in `tools/` and the library in `phext/` are
this project's own additions under the same terms.
