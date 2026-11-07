#!/bin/sh
# verify_examples.sh — prove the examples are live.
#
# Builds phcc from this tree (if not already built), then builds and
# runs every example in examples/ with phcc, gcc and clang (each
# when present), diffing program output against the example's
# expected.txt. A compiler that is not installed is reported as an
# explicit SKIP line — never silently. Any mismatch is a FAIL and
# makes the script exit 1.
#
# Usage:  sh examples/verify_examples.sh
# Output: one PASS/FAIL/SKIP line per (compiler, example) check,
#         then a summary. Suitable to save as a receipt.
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EX="$ROOT/examples"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/phcc-examples.XXXXXX")
trap 'rm -rf "$WORK"' EXIT INT TERM

npass=0; nfail=0; nskip=0
pass() { npass=$((npass+1)); echo "PASS  $1"; }
fail() { nfail=$((nfail+1)); echo "FAIL  $1"; }
skip() { nskip=$((nskip+1)); echo "SKIP  $1"; }

# check <label> <expected-file> <actual-file>
check() {
    if diff -u "$2" "$3" > "$WORK/last.diff" 2>&1; then
        pass "$1"
    else
        fail "$1"
        sed 's/^/      /' "$WORK/last.diff"
    fi
}

echo "== phcc examples verification =="
echo "date:      $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "host:      $(uname -srm)"
echo "tree:      $ROOT"

# --- build phcc from this tree -------------------------------------
if [ ! -x "$ROOT/tcc" ]; then
    echo "building phcc (./configure && make) ..."
    ( cd "$ROOT" && ./configure > "$WORK/configure.log" 2>&1 \
      && make > "$WORK/make.log" 2>&1 ) \
        || { echo "FAIL  phcc build (see $WORK logs)"; exit 1; }
fi
PHCC="$ROOT/tcc -B$ROOT"
echo "phcc:      $($ROOT/tcc --version | head -n 1)"

COMPILERS="phcc"
for c in gcc clang; do
    if command -v "$c" > /dev/null 2>&1; then
        COMPILERS="$COMPILERS $c"
        echo "$c:  $(command -v $c) — $($c --version | head -n 1)"
    else
        skip "$c (not installed)"
    fi
done

cc_of() { # compiler command for a short name
    case "$1" in
        phcc)  echo "$PHCC" ;;
        gcc)   echo "gcc" ;;
        clang) echo "clang" ;;
    esac
}

for comp in $COMPILERS; do
    CC=$(cc_of "$comp")
    W="$WORK/$comp"; mkdir -p "$W"

    # --- hello -----------------------------------------------------
    d="$W/hello"; mkdir -p "$d"; cp "$EX/hello/hello.c" "$d/"
    if ( cd "$d" && $CC -o hello hello.c > build.log 2>&1 ); then
        ( cd "$d" && ./hello > out.txt 2>&1 )
        check "$comp hello" "$EX/hello/expected.txt" "$d/out.txt"
    else
        fail "$comp hello (build)"; sed 's/^/      /' "$d/build.log"
    fi
    # -run is a phcc-only mode.
    if [ "$comp" = phcc ]; then
        ( cd "$d" && $PHCC -run hello.c > run.txt 2>&1 )
        check "phcc hello -run" "$EX/hello/expected.txt" "$d/run.txt"
    fi

    # --- cli-tool --------------------------------------------------
    d="$W/cli-tool"; mkdir -p "$d"
    cp "$EX/cli-tool/wordfreq.c" "$EX/cli-tool/input.txt" "$d/"
    if ( cd "$d" && $CC -o wordfreq wordfreq.c > build.log 2>&1 ); then
        ( cd "$d" && ./wordfreq < input.txt > out-stdin.txt 2>&1 )
        check "$comp cli-tool (stdin)" "$EX/cli-tool/expected.txt" "$d/out-stdin.txt"
        ( cd "$d" && ./wordfreq input.txt > out-argv.txt 2>&1 )
        check "$comp cli-tool (argv file)" "$EX/cli-tool/expected.txt" "$d/out-argv.txt"
    else
        fail "$comp cli-tool (build)"; sed 's/^/      /' "$d/build.log"
    fi

    # --- multifile -------------------------------------------------
    d="$W/multifile"; mkdir -p "$d"
    cp "$EX/multifile/stats.h" "$EX/multifile/stats.c" \
       "$EX/multifile/main.c" "$EX/multifile/Makefile" "$d/"
    if ( cd "$d" && make CC="$CC" > build.log 2>&1 ); then
        ( cd "$d" && ./app > out.txt 2>&1 )
        check "$comp multifile" "$EX/multifile/expected.txt" "$d/out.txt"
    else
        fail "$comp multifile (build)"; sed 's/^/      /' "$d/build.log"
    fi

    # --- dll -------------------------------------------------------
    d="$W/dll"; mkdir -p "$d"
    cp "$EX/dll/shared.h" "$EX/dll/dll.c" "$EX/dll/main.c" "$d/"
    if ( cd "$d" && $CC -shared -o libtwice.so dll.c > build.log 2>&1 \
         && $CC -o app main.c -L. -ltwice >> build.log 2>&1 ); then
        ( cd "$d" && LD_LIBRARY_PATH=. ./app > out.txt 2>&1 )
        check "$comp dll" "$EX/dll/expected.txt" "$d/out.txt"
    else
        fail "$comp dll (build)"; sed 's/^/      /' "$d/build.log"
    fi
done

# --- phext-pack (transport is compiler-independent; the unpacked
# --- project is then built with each compiler) ---------------------
d="$WORK/phext-pack"; mkdir -p "$d/stage/examples/phext-pack" "$d/out"
cp "$EX/phext-pack/project/"* "$d/stage/examples/phext-pack/"
if [ ! -f "$ROOT/phcc.phext" ]; then
    fail "phext-pack (repo phcc.phext missing — cannot lend a Volume 1)"
elif python3 "$ROOT/tools/phcc" pack --tree "$d/stage" \
        --out "$d/project.phext" --base "$ROOT/phcc.phext" \
        --no-vol3 > "$d/pack.log" 2>&1 \
  && python3 "$ROOT/tools/phcc" unpack --phext "$d/project.phext" \
        --out "$d/out" > "$d/unpack.log" 2>&1; then
    src="$d/out/examples/phext-pack"
    for comp in $COMPILERS; do
        CC=$(cc_of "$comp")
        b="$d/build-$comp"; mkdir -p "$b"
        cp "$src/main.c" "$src/greet.c" "$src/greet.h" "$b/"
        if ( cd "$b" && $CC -o app main.c greet.c > build.log 2>&1 ); then
            ( cd "$b" && ./app > out.txt 2>&1 )
            check "$comp phext-pack" "$EX/phext-pack/expected.txt" "$b/out.txt"
        else
            fail "$comp phext-pack (build)"; sed 's/^/      /' "$b/build.log"
        fi
    done
else
    fail "phext-pack (pack/unpack)"
    sed 's/^/      /' "$d/pack.log" "$d/unpack.log" 2>/dev/null | head -n 30
fi

echo "== summary: $npass passed, $nfail failed, $nskip skipped =="
[ "$nfail" -eq 0 ]
