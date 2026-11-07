# Building phcc

phcc builds like the TinyCC it is forked from: a `configure` script
and a Makefile, no build-system dependencies beyond a working C
compiler and `make`. (The `tools/` utilities additionally need
Python 3; the compiler itself does not.)

## Linux (and other POSIX hosts)

```sh
./configure
make
make test          # expect: ALL TESTS PASSED
```

That produces `./tcc` — the compiler. Two ways to use it:

- **In-tree:** `./tcc -B. …` — the `-B.` tells the uninstalled
  binary where its own headers and runtime (`libtcc1`) live: the
  build tree. Every example in `examples/` is verified this way.
- **Installed:** `make install` (default prefix `/usr/local`;
  choose another with `./configure --prefix=DIR`). An installed
  `tcc` needs no `-B`.

Quick smoke test, in-tree:

```sh
./tcc -B. -run examples/hello/hello.c    # Hello, world!
```

## Windows

phcc is used on Windows as well as Linux; the Windows build is
upstream's and the `win32/` directory is byte-identical to
upstream TinyCC.

From a Windows command prompt with a bootstrap compiler available
(MinGW gcc, MSVC, or an existing tcc — the script's default is
MinGW gcc):

```bat
cd win32
build-tcc.bat
```

`build-tcc.bat` produces `tcc.exe` and `libtcc.dll`; pass
`-c cl` to build with MSVC instead of gcc, and `-b DIR` to install
into `DIR`. Details are in the script's own header and in
`win32/tcc-win32.txt`.

> **Verification status of this section:** the Windows build path
> was verified from its sources on 2026-11-07 (the batch file's
> construction steps and the fork's F3 wiring were traced through
> it — see `docs/CONFORMANCE.md` for how Windows conformance is
> attested). It was **not executed** on the Linux host these docs
> were written on; execution receipts require a Windows host.

## Cross compilers ( PE targets from a Linux host )

The Makefile builds cross compilers that target Windows PE from a
Linux build tree:

```sh
make cross-x86_64-win32    # builds x86_64-win32-tcc + its libtcc1.a
make cross-i386-win32      # builds i386-win32-tcc + its libtcc1.a
make cross                 # all supported cross targets
```

The resulting `x86_64-win32-tcc` / `i386-win32-tcc` binaries
compile and link PE executables and DLLs, e.g. the
`examples/dll/` project:

```sh
x86_64-win32-tcc -shared -o twice.dll dll.c
```

These cross builds were exercised end-to-end (compile + link +
PE inspection) in the 2026-11-07 Windows-target readiness pass.
The PE binaries they produce were **not executed** — there is no
Windows or Wine on the build host — so treat cross output as
compile-verified, exactly as `examples/dll/README.md` states.

## Other targets

Actively used: x86_64 and ARM (Linux), x86_64 (Windows). The tree
also carries upstream's i386, arm64, riscv64 and c67 backends;
their platform status list is upstream's `TODO`/`USES` plus the
project's own platform register inside `phcc.phext`.
