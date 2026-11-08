#!/usr/bin/env python3
"""test_stmt.py — statement tier checks for phcc analyze.

Covers: the statement splitter (partition invariant + expected
segmentation on adversarial inputs), the statement-reference
grammar (phext_io), expansion (phcc_migrate.resolve_stmt_seq),
and a miniature end-to-end: a synthetic phext with one structured
file is built into a statement-level phext, verified, and
unpacked; the exported file must be byte-identical.

Run: python3 tools/test_stmt.py   (stdlib only, no network)
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phext_io
from phext_io import (fmt, implode, sha256, parse_stmt_seq,
                      stmt_ref, stmt_ref_empty, STMT_SEQ_MAGIC)
import phcc_analyze
import phcc_migrate

CHECKS = [0, 0]                     # [passed, failed]


def check(name, cond, detail=""):
    if cond:
        CHECKS[0] += 1
        print(f"  ok  {name}")
    else:
        CHECKS[1] += 1
        print(f"FAIL  {name}  {detail}")


def cores(data):
    parts = phcc_analyze.split_segments(data)
    joined = b"".join(ind + core for ind, core, _ in parts)
    assert joined == data, f"partition failed for {data!r}"
    return [(core, term) for _ind, core, term in parts]


# ------------------------------------------------------------ splitter
print("== splitter: partition + expected segmentation")
check("partition: function",
      cores(b"int f(void)\n{\n    int a = 1;\n    return a;\n}\n")
      == [(b"int f(void)\n{", "open"), (b"int a = 1;", "semi"),
          (b"return a;", "semi"), (b"}", "close"), (b"", "tail")])
check("partition: for-header semicolons do not cut",
      cores(b"for (i = 0; i < 3; i++)\n    x += i;\n")
      == [(b"for (i = 0; i < 3; i++)\n    x += i;", "semi"),
          (b"", "tail")])
check("partition: string with structural chars",
      cores(b'const char *s = ";{}";\n')
      == [(b'const char *s = ";{}";', "semi"), (b"", "tail")])
check("partition: char literal semicolon",
      cores(b"int c = ';';\n")
      == [(b"int c = ';';", "semi"), (b"", "tail")])
check("partition: comments carry semicolons safely",
      cores(b"/* a;b */ x = 1; // ;\n y = 2;")
      == [(b"/* a;b */ x = 1;", "semi"),
          (b"// ;\n y = 2;", "semi")])
check("partition: directives inside a function",
      cores(b"a = 1;\n#ifdef X\nb = 2;\n#endif\nc = 3;\n")
      == [(b"a = 1;", "semi"), (b"#ifdef X", "pp"),
          (b"b = 2;", "semi"), (b"#endif", "pp"),
          (b"c = 3;", "semi"), (b"", "tail")])
check("partition: struct declaration + close-semi merge",
      cores(b"struct S { int a; int b; };\nint x;\n")
      == [(b"struct S {", "open"), (b"int a;", "semi"),
          (b"int b;", "semi"), (b"};", "close-semi"),
          (b"int x;", "semi"), (b"", "tail")])
check("partition: do-while tail is its own segment (documented)",
      cores(b"do { x++; } while (x < 3);\n")
      == [(b"do {", "open"), (b"x++;", "semi"), (b"}", "close"),
          (b"while (x < 3);", "semi"), (b"", "tail")])
check("partition: directive continuation swallows its semicolon",
      cores(b"#define M(a) \\\n    f(a);\ng = 1;\n")
      == [(b"#define M(a) \\\n    f(a);", "pp"),
          (b"g = 1;", "semi"), (b"", "tail")])
check("partition: unterminated literal fragment still partitions",
      cores(b'x = "abc\ny = 2;') == [(b'x = "abc\ny = 2;', "tail")])
check("partition: case labels bind to their statements",
      cores(b"switch (x) {\ncase 1: y = 1; break;\ndefault: break;\n}\n")
      == [(b"switch (x) {", "open"), (b"case 1: y = 1;", "semi"),
          (b"break;", "semi"), (b"default: break;", "semi"),
          (b"}", "close"), (b"", "tail")])
check("partition: close-semi across a newline",
      cores(b"struct T {\n int a;\n}\n;\n")
      == [(b"struct T {", "open"), (b"int a;", "semi"),
          (b"}\n;", "close-semi"), (b"", "tail")])
check("partition: directive splitting a declaration (split class)",
      cores(b"int\n#define X 1\nx;\n")
      == [(b"int", "split"), (b"#define X 1", "pp"),
          (b"x;", "semi"), (b"", "tail")])
check("partition: empty payload", cores(b"") == [])
check("partition: whitespace-only payload is one EMPTY segment",
      cores(b"\n  \n") == [(b"", "tail")])

# ------------------------------------------------------------ grammar
print("== statement reference grammar")
C1 = (20000, 3, 4, 5, 6, 7, 8, 9, 10)
H1 = sha256(b"return a;")
seq = (STMT_SEQ_MAGIC + stmt_ref(C1, H1, b"\n    ")
       + stmt_ref_empty(b"\n"))
parsed = parse_stmt_seq(seq)
check("grammar: round-trip",
      parsed == [(C1, H1, b"\n    "), (None, None, b"\n")])
check("grammar: empty sequence parses", parse_stmt_seq(
    STMT_SEQ_MAGIC) == [])
check("grammar: plain payload is not a sequence",
      parse_stmt_seq(b"int a = 1;\n") is None)
check("grammar: magic + garbage line does not parse",
      parse_stmt_seq(STMT_SEQ_MAGIC + b"garbage\n") is None)
check("grammar: missing trailing newline does not parse",
      parse_stmt_seq(STMT_SEQ_MAGIC
                     + stmt_ref(C1, H1, b"")[:-1]) is None)

print("== expansion via phcc_migrate.resolve_stmt_seq")
scrolls = {C1: b"return a;"}
out = phcc_migrate.resolve_stmt_seq(scrolls, seq)
check("expansion: indent + core in order",
      out == b"\n    return a;\n")
try:
    phcc_migrate.resolve_stmt_seq({}, seq)
    check("expansion: missing target raises", False)
except ValueError:
    check("expansion: missing target raises", True)
try:
    phcc_migrate.resolve_stmt_seq({C1: b"tampered;"}, seq)
    check("expansion: hash mismatch raises", False)
except ValueError:
    check("expansion: hash mismatch raises", True)
try:
    phcc_migrate.resolve_stmt_seq(
        scrolls, STMT_SEQ_MAGIC + b"garbage\n")
    check("expansion: corrupt sequence raises (never literal)", False)
except ValueError:
    check("expansion: corrupt sequence raises (never literal)", True)
check("expansion: non-sequence returns None",
      phcc_migrate.resolve_stmt_seq(scrolls, b"plain;\n") is None)

# ------------------------------------------------------------ end-to-end
print("== miniature end-to-end: build -> verify -> unpack")
FILE = (b"int f(void)\n{\n    int a = 1;\n    a += 2;\n"
        b"    a += 2;\n    return a;\n}\n")
P1, P2 = FILE[:31], FILE[31:]
V2 = (1, 1, 1, 4, 2, 3, 1, 1, 1)
IDX = (1, 1, 1, 4, 3, 3, 1, 1, 1)


def seg_scroll(kind, name, form, span, payload):
    hdr = (f"#phcc-member\tkind={kind}\tname={name}\tform={form}"
           f"\tspan={span}\tsha256={sha256(payload)}")
    return hdr.encode() + b"\n" + payload


synthetic = {
    V2: FILE,
    (1, 1, 1, 1, 2, 10, 1, 1, 1):
        f"mini.c\t{fmt(V2)}\t{sha256(FILE)}\t{len(FILE)}\t100644\n"
        .encode(),
    IDX: ("# phcc file index\n# path: mini.c\n"
          f"# sha256: {sha256(FILE)} (synthetic test)\n"
          f"2\tfunction\tf\tdef\t0-{len(P1)}\t{sha256(P1)}\n"
          f"3\tgap\t-\t-\t{len(P1)}-{len(FILE)}\t{sha256(P2)}\n")
        .encode(),
    (1, 1, 1, 4, 3, 3, 1, 1, 2):
        seg_scroll("function", "f", "def", f"0-{len(P1)}", P1),
    (1, 1, 1, 4, 3, 3, 1, 1, 3):
        seg_scroll("gap", "-", "-", f"{len(P1)}-{len(FILE)}", P2),
}

with tempfile.TemporaryDirectory(prefix="phcc-stmt-test-") as td:
    src = os.path.join(td, "mini.phext")
    dst = os.path.join(td, "mini-stmt.phext")
    with open(src, "wb") as f:
        f.write(implode(synthetic))
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "phcc_analyze.py"),
         "--phext", src, "--build-stmt", "--out", dst,
         "--report", os.path.join(td, "build.md")],
        capture_output=True, text=True)
    check("e2e: build-stmt exits 0", r.returncode == 0,
          r.stdout + r.stderr)
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "phcc_analyze.py"),
         "--phext", dst, "--verify-stmt"],
        capture_output=True, text=True)
    check("e2e: verify-stmt exits 0", r.returncode == 0,
          r.stdout + r.stderr)
    check("e2e: verify reports each statement held exactly once",
          "held exactly once: YES" in r.stdout)
    stmt_scrolls = dict(phext_io.walk_bytes(open(dst, "rb").read()))
    lib = {c: b for c, b in stmt_scrolls.items()
           if c[0] == phcc_analyze.STMT_LIBRARY}
    check("e2e: duplicated statement held once "
          "(a += 2; referenced twice)",
          list(lib.values()).count(b"a += 2;") == 1,
          f"library values: {sorted(lib.values())}")
    for route, name in (("vol3", "from-vol3"), ("vol2", "from-vol2")):
        outdir = os.path.join(td, name)
    outdir = os.path.join(td, "unpacked")
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "phcc_migrate.py"),
         "export", "--phext", dst, "--out", outdir, "--from",
         "vol3"], capture_output=True, text=True)
    check("e2e: unpack --from vol3 exits 0", r.returncode == 0,
          r.stdout + r.stderr)
    got = open(os.path.join(outdir, "mini.c"), "rb").read() \
        if os.path.exists(os.path.join(outdir, "mini.c")) else None
    check("e2e: unpacked file byte-identical", got == FILE)
    check("e2e: unpack reports statement expansions",
          "statement references expanded:" in r.stdout)

print(f"\n{CHECKS[0]} passed, {CHECKS[1]} failed")
sys.exit(1 if CHECKS[1] else 0)
