# hello — your first phcc program

One file, one `printf`. This is the whole build:

```sh
tcc -o hello hello.c
./hello            # Hello, world!
```

(`tcc` is the phcc binary's name — phcc is the project, `tcc` is the
program it builds, inherited from upstream TinyCC.)

## The phcc party trick: `-run`

phcc can compile and execute in one step, with no binary left behind:

```sh
tcc -run hello.c   # Hello, world!
```

That makes C usable like a scripting language. The classic form is a
shebang line as the first line of the source:

```c
#!/usr/local/bin/tcc -run
```

— mark the file executable and run it as a script.

## Check it

From the repository root, `examples/verify_examples.sh` builds and
runs this example with phcc, gcc and clang and diffs the output
against `expected.txt`.
