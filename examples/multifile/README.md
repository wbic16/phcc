# multifile — a library and a program, with a Makefile

The first example most real projects grow into: more than one `.c`
file, a header as the contract between them, and a Makefile.

```sh
make            # builds stats.o, libstats.a, then app
./app
# mean = 4.000
# max = 8.000
```

Layout:

| File      | Role                                            |
|-----------|-------------------------------------------------|
| `stats.h` | The library's public contract (include-guarded) |
| `stats.c` | The implementation                              |
| `main.c`  | The program — includes the header, nothing else |
| `Makefile`| Compiles the library, archives it, links `app`  |

The compiler is the Makefile's `CC` variable, so the identical
build runs under every compiler the examples support:

```sh
make CC=tcc     # phcc
make CC=gcc
make CC=clang
```

(`verify_examples.sh` runs all three and diffs the output against
`expected.txt`. When it drives phcc from the build tree it passes
`CC="tcc -B<tree>"` so the in-tree compiler finds its own headers
and runtime.)
