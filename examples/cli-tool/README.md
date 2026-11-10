# cli-tool — a small argument-taking utility

`wordfreq` counts word frequencies. It reads a file named on the
command line, or stdin when no argument is given:

```sh
phcc -o wordfreq wordfreq.c
./wordfreq < input.txt     # count words from stdin
./wordfreq input.txt       # same output, file as argument
```

Output is one `word count` line per word, most frequent first, ties
broken alphabetically — deterministic, so `verify_examples.sh` can
diff it against `expected.txt` byte for byte. Both invocation forms
above are verified and must agree.

The program is plain C11: a fixed-size table, `qsort`, no
dependencies beyond the standard library. It builds unchanged with
phcc, gcc and clang.
