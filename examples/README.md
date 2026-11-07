# Examples

Small, complete C projects — each one readable in about two
minutes, each one verified live. (`ex1.c`–`ex5.c` in this directory
are upstream TinyCC's original one-file samples, kept as they were.)

| Example       | What it shows                                             |
|---------------|-----------------------------------------------------------|
| `hello/`      | One file, one build command — and phcc's `-run` mode      |
| `cli-tool/`   | A real utility: argv, stdin, deterministic output         |
| `multifile/`  | A library + a program + a Makefile, header discipline     |
| `phext-pack/` | A project packed into a phext, unpacked elsewhere, built  |
| `dll/`        | A shared library (`__declspec` and all) and its consumer  |

## Verifying them

```sh
sh examples/verify_examples.sh
```

builds phcc from this tree if needed, then builds and runs every
example with **phcc, gcc and clang**, diffing each program's output
against its `expected.txt`. A missing compiler is an explicit
`SKIP` line; any output mismatch is a `FAIL` and a non-zero exit.
Save the output if you want a receipt — that is all a receipt is
here.

Last verified run: 2026-11-07 on aletheia-core (Linux x86_64) —
every check green under phcc (this tree), gcc 13.3.0 and
clang 18.1.3. Re-run the script to reproduce; the numbers in any
committed doc are a record of that run, not a promise about yours.
