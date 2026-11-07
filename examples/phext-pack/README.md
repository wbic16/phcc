# phext-pack — a project that travels inside a phext

phcc's own development workflow, in miniature: a whole project
carried in a single `.phext` file, unpacked somewhere else, and
built there. The project itself is three small files in `project/`
(`main.c`, `greet.c`, `greet.h`). The interesting part is the trip.

From the repository root:

```sh
# 1. Stage the project at the path the packer will give it in the
#    phext (examples/** is Book 10, Chapter 7 of the layout).
mkdir -p /tmp/stage/examples/phext-pack
cp examples/phext-pack/project/* /tmp/stage/examples/phext-pack/

# 2. Pack the staged tree into one phext. --base lends the new
#    phext its Volume 1 from the project's own phcc.phext;
#    --no-vol3 stops after the file-level (Volume 2) stage.
python3 tools/phcc pack --tree /tmp/stage --out /tmp/project.phext \
    --base phcc.phext --no-vol3

# 3. Unpack it somewhere else entirely. Every file is SHA-256-
#    verified against the manifest inside the phext before it is
#    written; a tampered scroll means that file is not written.
mkdir /tmp/elsewhere
python3 tools/phcc unpack --phext /tmp/project.phext --out /tmp/elsewhere

# 4. Build and run what came out of the phext.
cd /tmp/elsewhere/examples/phext-pack
tcc -o app main.c greet.c
./app            # Hello from inside the phext!
```

`verify_examples.sh` performs exactly these steps (with the
repository's real `tools/phcc`) and diffs the output against
`expected.txt`. See `docs/PHEXT.md` for how the whole compiler
project itself lives this way — this example is that workflow at
toy scale.
