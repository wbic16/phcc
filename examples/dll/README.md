# dll — a shared library and its consumer

Two translation units with a boundary between them: `dll.c` builds
into a shared library, `main.c` links against it and calls across.
`shared.h` is the contract both sides include; its `API` macro is
`__declspec(dllexport)` for the library and
`__declspec(dllimport)` for consumers on Windows, and empty on ELF
platforms where no decoration is needed.

On Linux (what `verify_examples.sh` runs):

```sh
tcc -shared -o libtwice.so dll.c
tcc -o app main.c -L. -ltwice
LD_LIBRARY_PATH=. ./app     # twice(21) = 42
```

On Windows the same sources produce a DLL — and phcc can build it
from Linux, with a cross compiler (see `docs/BUILDING.md` for
`make cross-x86_64-win32`):

```sh
x86_64-win32-tcc -shared -o twice.dll dll.c   # no .def file needed
x86_64-win32-tcc -o app.exe main.c twice.dll
```

The Windows form is **compile-verified, not run-verified, here**:
the project's Windows-target readiness pass built exactly this
shape (a `__declspec(dllexport)` DLL with no `.def` file, plus a
dllimport consumer linked directly against it) and inspected the
resulting PE files; no PE binary was executed, because execution
needs a Windows host. MSVC compatibility for the Windows surface
is confirmed by the maintainer's manual attestation — see
`docs/CONFORMANCE.md`.
