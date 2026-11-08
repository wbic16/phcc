#!/usr/bin/env python3
"""test_prune.py — fixture tests for phcc_prune (phcc -O2 rung A).

Builds a miniature carried phext in memory (six files: an exe
source, a library source, a helper source, a header, a keep-whole
test file, a non-source data file, and one uncompiled source) plus
a miniature harvest, runs the pruner, and asserts the graph
semantics end to end:

  - unreferenced statics and unreferenced exe globals drop;
  - library-surface globals are rooted even when unreferenced
    (the archive asymmetry: a library's globals are its exports);
  - a symbol no payload names textually is force-kept by the
    undefined-symbol closure, with the forcing recorded;
  - unreferenced types/macros drop, referenced ones stay;
  - uncompiled source files drop whole; keep-whole classes ride;
  - the emitted phext verifies under load_carried AND unpacks
    under the stock phcc_migrate with byte-exact expectations.

Run: python3 tools/test_prune.py   (stdlib only)
"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phext_io import implode, fmt, sha256
import phcc_prune as P

FAILS = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def seg_header(kind, name, form, span, psha):
    return (f"#phcc-member\tkind={kind}\tname={name}\tform={form}\t"
            f"span={span[0]}-{span[1]}\tsha256={psha}\n").encode()


def structured_file(path, coord, rows):
    """rows: [(kind, name, form, payload)] -> (vol2 bytes, scrolls dict)
    Scrolls dict holds the Vol 3 index (scroll 1) + segments (2..)."""
    vol2 = b"".join(r[3] for r in rows)
    sha = sha256(vol2)
    head = ["# phcc file index — importer v3 (fixture)",
            f"# path: {path}",
            f"# volume2: {fmt(coord)}",
            f"# sha256: {sha}  size: {len(vol2)}",
            f"# parse: fixture; members={len(rows)} error-bytes=0",
            "# columns: scroll\tkind\tname\tform\tspan\tsha256"]
    lines, scrolls, cursor = list(head), {}, 0
    for i, (kind, name, form, payload) in enumerate(rows):
        scr = i + 2
        span = (cursor, cursor + len(payload))
        cursor = span[1]
        psha = sha256(payload)
        lines.append(f"{scr}\t{kind}\t{name}\t{form}\t"
                     f"{span[0]}-{span[1]}\t{psha}")
        seg_coord = (1, 1, 1, 4, 3, coord[5], coord[6], coord[7], scr)
        scrolls[seg_coord] = seg_header(kind, name, form, span, psha) \
            + payload
    idx_coord = (1, 1, 1, 4, 3, coord[5], coord[6], coord[7], 1)
    scrolls[idx_coord] = ("\n".join(lines) + "\n").encode()
    return vol2, sha, scrolls


GAP = lambda text: ("gap", "-", "-", text.encode())
FN = lambda name, form, text: ("function", name, form, text.encode())
OBJ = lambda name, form, text: ("object", name, form, text.encode())
TYP = lambda name, form, text: ("type", name, form, text.encode())

TOK = [GAP("/* token table: rows are positional */\n"),
       OBJ("TOK_ASM_int", "object", "DEF_ASM(int)\n"),
       OBJ("TOK_ASM_mov", "object", "DEF_ASM(mov)\n")]
ONLYHERE = [GAP("/* reached only via an angle include */\n"),
            OBJ("ANGLE_MACRO", "macro", "#define ANGLE_MACRO 5\n")]
NOTUSED = [GAP("/* angle-included textually, but the build graph "
               "does not vouch for it (an #ifdef'd-out include) */\n"),
           OBJ("NOTUSED_MACRO", "macro", "#define NOTUSED_MACRO 6\n")]
APP = [GAP('#include "hdr.h"\n#include "x86-tok.h"\n'
           '#include <onlyhere.h>\n#include <notused.h>\n'),
       FN("main", "def", "int main(void){ s_used(); api_used(); "
                         "use(g_used, (UsedType*)0, MACRO_USED, MODE_B, "
                         "ANGLE_MACRO); }\n"),
       FN("s_used", "def", "static void s_used(void){}\n"),
       FN("s_dead", "def", "static void s_dead(void){}\n"),
       OBJ("g_used", "global", "int g_used;\n"),
       OBJ("g_dead", "global", "int g_dead;\n")]
LIBX = [GAP("/* libx */\n"),
        FN("api_used", "def", "void api_used(void){ ELFW(R_INFO); }\n"),
        FN("api_dead", "def", "void api_dead(void){}\n"),
        FN("x_dead_static", "def", "static void x_dead_static(void){}\n")]
HELPER = [GAP("/* helper */\n"),
          FN("ext_needed", "def", "void ext_needed(void){}\n"),
          FN("forced_sym", "def", "void forced_sym(void){}\n"),
          OBJ("helper_dead_global", "global", "int helper_dead_global;\n")]
LIBY = [GAP("/* liby: archived, never pulled */\n"),
        FN("y_unused", "def", "void y_unused(void){}\n")]
LIBX2 = [GAP("/* libx2: exists only as an archive member */\n"),
         FN("x2_api", "def", "void x2_api(void){}\n"),
         FN("x2_dead", "def", "static void x2_dead(void){}\n")]
HDR = [GAP("/* hdr */\n"),
       TYP("UsedType", "typedef", "typedef struct { int a; } UsedType;\n"),
       TYP("DeadType", "typedef", "typedef struct { int b; } DeadType;\n"),
       OBJ("MACRO_USED", "macro", "#define MACRO_USED 1\n"),
       OBJ("MACRO_DEAD", "macro", "#define MACRO_DEAD 2\n"),
       OBJ("PP_OPEN", "macro", "#ifdef NEVER_DEFINED\n"),
       OBJ("PP_CLOSE", "macro", "#endif\n"),
       OBJ("ELF32_R_INFO", "macro", "#define ELF32_R_INFO(s,t) ((s)<<8)\n"),
       OBJ("ELF64_R_INFO", "macro", "#define ELF64_R_INFO(s,t) ((s)<<32)\n"),
       OBJ("R_INFO_EXTRA", "macro", "#define R_INFO_EXTRA 9\n"),
       TYP("Mode", "enum", "typedef enum { MODE_A, MODE_B } Mode;\n"),
       TYP("UnusedMode", "enum",
           "typedef enum { UNUSED_X, UNUSED_Y } UnusedMode;\n")]
DEADC = [GAP("/* never compiled */\n"),
         FN("dead_fn", "def", "void dead_fn(void){}\n")]
DEAD2C = [GAP("/* uncompiled, but the Makefile names it */\n"),
          FN("dead2_fn", "def", "void dead2_fn(void){}\n")]
GENINH = [GAP("/* a build template: generated-from, never compiled */\n"),
          OBJ("GEN_MACRO", "macro", "#define GEN_MACRO 1\n")]
TESTC = [GAP("/* a compiled test program: keep-whole by class */\n"),
         FN("tmain", "def", "int tmain(void){ return 0; }\n"),
         FN("t_dead", "def", "static void t_dead(void){}\n")]

FILES = [  # path, vol2 coord, rows or None (bridge file), data
    ("app.c", (1, 1, 1, 4, 2, 1, 1, 1, 1), APP),
    ("libx.c", (1, 1, 1, 4, 2, 1, 1, 2, 1), LIBX),
    ("helper.c", (1, 1, 1, 4, 2, 1, 1, 3, 1), HELPER),
    ("liby.c", (1, 1, 1, 4, 2, 1, 1, 5, 1), LIBY),
    ("libx2.c", (1, 1, 1, 4, 2, 1, 1, 6, 1), LIBX2),
    ("hdr.h", (1, 1, 1, 4, 2, 1, 1, 4, 1), HDR),
    ("x86-tok.h", (1, 1, 1, 4, 2, 1, 1, 7, 1), TOK),
    ("sub/onlyhere.h", (1, 1, 1, 4, 2, 6, 6, 4, 1), ONLYHERE),
    ("sub/notused.h", (1, 1, 1, 4, 2, 6, 6, 5, 1), NOTUSED),
    ("dead.c", (1, 1, 1, 4, 2, 6, 6, 1, 1), DEADC),
    ("dead2.c", (1, 1, 1, 4, 2, 6, 6, 2, 1), DEAD2C),
    ("sub/gen.in.h", (1, 1, 1, 4, 2, 6, 6, 3, 1), GENINH),
    ("Makefile", (1, 1, 1, 4, 2, 11, 1, 1, 1), None),
    ("tests/t1.c", (1, 1, 1, 4, 2, 10, 2, 1, 1), None),
    ("tests/t2.c", (1, 1, 1, 4, 2, 10, 2, 2, 1), TESTC),
    ("data.txt", (1, 1, 1, 4, 2, 10, 1, 9, 1), None),
]

HARVEST = {
    "objects": {
        "app.o": {"source": "app.c",
                  "defined_global": ["main", "g_used", "g_dead"],
                  "defined_local": ["s_used", "s_dead"],
                  "undefined": ["api_used", "ext_needed"]},
        "libx.o": {"source": "libx.c",
                   "defined_global": ["api_used", "api_dead"],
                   "defined_local": ["x_dead_static"], "undefined": []},
        "helper.o": {"source": "helper.c",
                     "defined_global": ["ext_needed", "forced_sym",
                                        "helper_dead_global"],
                     "defined_local": [], "undefined": []},
        "liby.o": {"source": "liby.c",
                   "defined_global": ["y_unused"],
                   "defined_local": [], "undefined": []},
        "t2.o": {"source": "tests/t2.c",
                 "defined_global": ["tmain"],
                 "defined_local": ["t_dead"], "undefined": []},
    },
    "archives": {
        "libx.a": {"libx.o": {"defined_global": ["api_used", "api_dead"],
                              "defined_local": ["x_dead_static"],
                              "undefined": []},
                   "libx2.o": {"defined_global": ["x2_api"],
                               "defined_local": ["x2_dead"],
                               "undefined": ["forced_sym"]}},
        "liby.a": {"liby.o": {"defined_global": ["y_unused"],
                              "defined_local": [],
                              "undefined": []}},
    },
    "collisions": [], "n_objects": 4, "n_archives": 2,
    "build_prereqs": ["sub/gen.in.h", "sub/onlyhere.h"],
}


def build_fixture(td):
    scrolls = {(1, 1, 1, 1, 1, 1, 1, 1, 1): b"fixture slurp\n"}
    man = ["# fixture placement manifest",
           "# columns: path\tcoordinate\tsha256\tsize\tgit-mode"]
    for path, coord, rows in FILES:
        if rows is None:
            data = ("fixture payload for " + path + "\n").encode()
            if path == "Makefile":
                data = (b"all: dead2.c\n\tcp dead2.c dead2.o\n"
                        b"out.h: sub/gen.in.h\n\tsed s/@x@/1/ sub/gen.in.h > out.h\n")
            sha = sha256(data)
        else:
            data, sha, v3 = structured_file(path, coord, rows)
            scrolls.update(v3)
        scrolls[coord] = data
        man.append(f"{path}\t{fmt(coord)}\t{sha}\t{len(data)}\t100644")
    scrolls[P.phcc_migrate.MANIFEST_COORD] = \
        ("\n".join(man) + "\n").encode()
    scrolls[P.phcc_migrate.NOTES_COORD] = b"# fixture layout notes\n"
    phext_path = os.path.join(td, "fixture.phext")
    with open(phext_path, "wb") as f:
        f.write(implode(scrolls))
    hv_path = os.path.join(td, "harvest.json")
    with open(hv_path, "w") as f:
        json.dump(HARVEST, f)
    return phext_path, hv_path


def main():
    with tempfile.TemporaryDirectory(prefix="phcc-prune-test-") as td:
        phext_path, hv_path = build_fixture(td)
        res = P.prune(phext_path, hv_path, [], [])
        dropped_names = set()
        for mid in res["dropped"]:
            dropped_names.update(res["members"][mid].names)
        kept_names = set()
        for mid in res["kept"]:
            kept_names.update(res["members"][mid].names)

        for name in ("s_dead", "g_dead", "x_dead_static",
                     "helper_dead_global", "DeadType", "MACRO_DEAD",
                     "api_dead"):
            check(name in dropped_names, f"drops {name}")
        for name in ("main", "s_used", "g_used", "api_used",
                     "UsedType", "MACRO_USED", "Mode"):
            check(name in kept_names, f"keeps {name}")
        check("TOK_ASM_int" in kept_names and "TOK_ASM_mov" in kept_names,
              "tok-table rows rooted as a unit (positional)")
        check("PP_OPEN" in kept_names and "PP_CLOSE" in kept_names,
              "pp-conditional halves rooted as units")
        check(res["classes"]["sub/onlyhere.h"] == "graph" and
              "ANGLE_MACRO" in kept_names,
              "angle-included header vouched by the build graph "
              "joins the graph")
        check(res["classes"]["sub/notused.h"] == "drop",
              "angle-included header the build graph does not vouch "
              "for stays dropped")
        check("ELF32_R_INFO" in kept_names and
              "ELF64_R_INFO" in kept_names,
              "paste family kept via suffix edge (ELFW(R_INFO))")
        check("R_INFO_EXTRA" in dropped_names,
              "drops R_INFO_EXTRA (suffix is EXTRA, not R_INFO)")
        check("UnusedMode" in dropped_names,
              "drops UnusedMode (unreferenced enum, enumerators and all)")
        check("Mode" in kept_names,
              "keeps Mode via provider edge (enumerator MODE_B)")
        check("api_dead" in dropped_names,
              "drops api_dead (pulled object, undemanded global)")
        check("ext_needed" in kept_names, "keeps ext_needed (demanded)")
        check("forced_sym" in kept_names, "keeps forced_sym (closure)")
        check("y_unused" in dropped_names,
              "drops y_unused (unpulled archive member's global)")
        check("x2_api" in dropped_names and "x2_dead" in dropped_names,
              "drops libx2.c's undemanded members (archive-only source)")
        check(res["classes"]["libx2.c"] == "graph",
              "libx2.c is a graph file via its archive member")
        forced_recs = {f["symbol"]: f["required_by"]
                       for f in res["forced"]}
        check(forced_recs.get("forced_sym") == "libx2.c",
              "closure forcing recorded: forced_sym required by libx2.c")
        check("dead.c" in {cf.path for cf in res["files"]
                           if res["classes"][cf.path] == "drop"},
              "dead.c classified drop-whole")
        check(res["classes"]["tests/t1.c"] == "keep",
              "tests/t1.c keep-whole")
        check(res["classes"]["tests/t2.c"] == "keep" and
              "t_dead" not in dropped_names,
              "compiled test program keep-whole (members exempt)")
        check(res["classes"]["data.txt"] == "keep", "data.txt keep-whole")
        check(res["classes"]["dead2.c"] == "keep" and
              "dead2.c" in res["buildref_keeps"],
              "dead2.c rescued by build-reference (Makefile names it)")
        check(res["classes"]["sub/gen.in.h"] == "keep" and
              "sub/gen.in.h" in res["buildref_keeps"],
              "sub/gen.in.h rescued via the configured build graph "
              "(harvest build_prereqs)")

        # per-project classes: with no keep-whole prefixes, the
        # compiled test program becomes a graph file and its dead
        # member is prunable (the coreutils configuration)
        res2 = P.prune(phext_path, hv_path, [], [], keep_prefixes=())
        check(res2["classes"]["tests/t2.c"] == "graph",
              "keep_prefixes=() makes tests/t2.c a graph file")
        dropped2 = set()
        for mid in res2["dropped"]:
            dropped2.update(res2["members"][mid].names)
        check("t_dead" in dropped2,
              "keep_prefixes=() drops the test program's dead member")
        check(res2["classes"]["tests/t1.c"] == "drop",
              "keep_prefixes=() drops the uncompiled test file whole")

        out, stats = P.emit(res, phext_path)
        out[P.PRUNE_MANIFEST_COORD] = P.prune_manifest_text(res, stats)
        out_path = os.path.join(td, "pruned.phext")
        with open(out_path, "wb") as f:
            f.write(implode(out))
        sc2, files2 = P.load_carried(out_path)
        by_path = {cf.path: cf for cf in files2}
        check("dead.c" not in by_path, "emitted phext omits dead.c")
        check(by_path["dead2.c"].data == b"".join(r[3] for r in DEAD2C),
              "emitted dead2.c byte-identical (build-referenced)")
        check(by_path["tests/t2.c"].data ==
              b"".join(r[3] for r in TESTC),
              "emitted tests/t2.c byte-identical (keep-whole)")
        expect_app = b"".join(r[3] for r in APP
                              if r[1] not in ("s_dead", "g_dead"))
        check(by_path["app.c"].data == expect_app,
              "emitted app.c = original minus dropped members")
        check(by_path["libx.c"].data ==
              b"".join(r[3] for r in LIBX
                       if r[1] not in ("x_dead_static", "api_dead")),
              "emitted libx.c = original minus dropped members")
        # stock unpacker accepts the emitted phext, both routes
        import phcc_migrate
        for route in ("vol2", "vol3"):
            dest = os.path.join(td, "unpack-" + route)
            rc = phcc_migrate.cli(["export", "--phext", out_path,
                                   "--out", dest, "--from", route])
            check(rc == 0, f"stock unpack --from {route} rc=0")
            with open(os.path.join(dest, "app.c"), "rb") as fh:
                check(fh.read() == expect_app,
                      f"stock unpack {route}: app.c bytes exact")
    print(f"\n{len(FAILS)} failures" if FAILS else "\nall checks passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
