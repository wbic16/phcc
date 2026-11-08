#!/usr/bin/env python3
"""test_analyze.py — end-to-end self-check for `phcc analyze`.

Builds a synthetic phext with planted duplicates of every class the
analyzer must distinguish, then drives the real dispatcher:

  planted exact member clusters (shared function across files, a
  gap, a cluster whose canonical lives in lib/libtcc1.c and one
  whose canonical lives in a lower book), a byte-identical file
  pair, a NEAR pair (identical only after comment/whitespace
  normalization), a zero-byte gap cluster (never stubbed), binary
  scrolls (excluded), Library-10000 scrolls (excluded), a Volume 1
  duplicate pair (census-only), a proof receipt + gate verdict +
  design view bound to things apply rewrites (DEMOTED-TO-STALE),
  and a register that merely mentions a changed hash (not demoted).

Asserts: the census counts, the apply stub counts, the demote list,
losslessness (unpack of the deduplicated phext, both routes,
reproduces every planted file byte-for-byte), zero actionable
clusters afterwards, idempotence, and apply's refusal on a phext
whose index hashes do not verify.

    python3 tools/test_analyze.py

Exit 0 = all checks passed. Stdlib only.
"""
import base64, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phext_io
from phext_io import fmt, sha256

PHCC = os.path.join(HERE, "phcc")
FAILURES = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        FAILURES.append(label)


def run(args, cwd):
    r = subprocess.run([sys.executable, PHCC] + args, cwd=cwd,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# ------------------------------------------------------------ fixture
GAP_LICENSE = b"/* fixture license */\n"
FN_SHARED = b"int shared(void)\n{\n    return 42;\n}\n"
FN_LIB = b"int libfn(void)\n{\n    return 7;\n}\n"
FN_ZED = b"int zed(void)\n{\n    return 9;\n}\n"
FN_A_ONLY = b"int a_only(void) { return 1; }\n"
FN_LIBOWN = b"int libown(void) { return 3; }\n"
NEAR_A = b"int near_twin(int x)\n{\n    /* add one */\n    return x + 1;\n}\n"
NEAR_B = b"int near_twin(int x)\n{\n    // add one\n    return  x  +  1;\n}\n"
EMPTY = b""

# path -> (vol2 coord, [(kind, name, payload), ...] or None for file-level)
FILES = {
    "a.c": ((1, 1, 1, 4, 2, 1, 1, 1, 1),
            [("gap", "-", GAP_LICENSE), ("function", "shared", FN_SHARED),
             ("function", "libfn", FN_LIB), ("gap", "-", EMPTY),
             ("function", "a_only", FN_A_ONLY)]),
    "b.c": ((1, 1, 1, 4, 2, 1, 1, 2, 1), None),  # bytes == a.c, no index
    "c.c": ((1, 1, 1, 4, 2, 3, 1, 1, 1),
            [("function", "shared", FN_SHARED), ("gap", "-", EMPTY),
             ("function", "near_twin", NEAR_A)]),
    "lib/libtcc1.c": ((1, 1, 1, 4, 2, 7, 1, 1, 1),
                      [("function", "libfn", FN_LIB),
                       ("function", "zed", FN_ZED),
                       ("function", "libown", FN_LIBOWN)]),
    "z.c": ((1, 1, 1, 4, 2, 10, 1, 1, 1),
            [("gap", "-", GAP_LICENSE), ("function", "shared", FN_SHARED),
             ("function", "zed", FN_ZED),
             ("function", "near_twin", NEAR_B)]),
}
RECEIPT = (1, 1, 1, 10, 2, 7, 1, 1, 1)
VERDICT = (1, 1, 1, 1, 2, 10, 1, 3, 1)
DESIGN = (1, 1, 1, 3, 2, 3, 1, 1, 1)
REGISTER = (1, 1, 1, 1, 2, 10, 1, 4, 1)
BIN1, BIN2 = (1, 1, 1, 6, 2, 1, 1, 1, 1), (1, 1, 1, 6, 2, 1, 1, 2, 1)
REG1, REG2 = (10000, 1, 1, 4, 2, 1, 1, 1, 1), (10000, 1, 1, 4, 2, 1, 1, 1, 2)
V1A, V1B = (1, 1, 1, 1, 1, 1, 1, 1, 1), (1, 1, 1, 1, 1, 1, 1, 1, 2)


def file_bytes(path):
    coord, segs = FILES[path]
    if path == "b.c":
        return file_bytes("a.c")
    return b"".join(p for _, _, p in segs)


def build_fixture(corrupt_index=False):
    scrolls = {}
    man = ["# fixture placement manifest",
           "# columns: path <TAB> coordinate <TAB> sha256 <TAB> size "
           "<TAB> git-mode"]
    for path, (v2, segs) in FILES.items():
        data = file_bytes(path)
        scrolls[v2] = data
        man.append(f"{path}\t{fmt(v2)}\t{sha256(data)}\t{len(data)}\t100644")
        if segs is None:
            continue
        idx = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        lines = ["# phcc file index — importer v3", f"# path: {path}",
                 f"# volume2: {fmt(v2)}",
                 f"# sha256: {sha256(data)}  size: {len(data)}",
                 "# columns: scroll <TAB> kind <TAB> name <TAB> form "
                 "<TAB> span <TAB> sha256"]
        pos = 0
        for i, (kind, name, payload) in enumerate(segs):
            scr = i + 2
            span = f"{pos}-{pos + len(payload)}"
            pos += len(payload)
            psha = sha256(payload)
            shown = ("0" * 64) if (corrupt_index and path == "c.c"
                                   and scr == 2) else psha
            lines.append(f"{scr}\t{kind}\t{name}\t-\t{span}\t{shown}")
            hdr = (f"#phcc-member\tkind={kind}\tname={name}\tform=-\t"
                   f"span={span}\tsha256={psha}").encode()
            scrolls[(1, 1, 1, 4, 3, v2[5], v2[6], v2[7], scr)] = \
                hdr + b"\n" + payload
        scrolls[idx] = ("\n".join(lines) + "\n").encode()
    scrolls[(1, 1, 1, 1, 2, 10, 1, 1, 1)] = \
        ("\n".join(man) + "\n").encode()
    lib_sha = sha256(file_bytes("lib/libtcc1.c"))
    scrolls[RECEIPT] = ("# fixture proof receipt — lib/libtcc1.c\n"
                        f"source-sha256: {lib_sha}\n"
                        "status: FIXTURE\n").encode()
    scrolls[VERDICT] = ("# phcc gate verdict - fixture\n"
                        f"binds payload sha256: {sha256(FN_LIB)}\n"
                        ).encode()
    scrolls[DESIGN] = ("# phcc design view - fixture\n# path: c.c\n"
                       f"members-digest: {'0' * 64}\n").encode()
    scrolls[REGISTER] = ("# fixture register\n"
                         f"notes the payload {sha256(FN_SHARED)} "
                         "here\n").encode()
    blob = b"phext-binary:1:base64\n" + base64.b64encode(b"\x00\x01\x02bin")
    scrolls[BIN1] = scrolls[BIN2] = blob
    scrolls[(10000, 1, 1, 1, 1, 1, 1, 1, 1)] = b"# fixture region manifest\n"
    scrolls[REG1] = scrolls[REG2] = blob
    scrolls[V1A] = scrolls[V1B] = b"historical slurp line\n"
    return phext_io.implode(scrolls)


def read_tree(d):
    return {p: open(os.path.join(d, p), "rb").read() for p in FILES}


def main():
    td = tempfile.mkdtemp(prefix="phcc-analyze-test-")
    fx = os.path.join(td, "fixture.phext")
    with open(fx, "wb") as f:
        f.write(build_fixture())

    # --- census
    rc, out = run(["analyze", "--phext", fx, "--out",
                   os.path.join(td, "census.md")], td)
    check(rc == 0, "census exits 0")
    census = open(os.path.join(td, "census.md")).read()
    check("index hash verification: 15/15" in census,
          "all 15 planted segment hashes verify against the indexes")
    check("- exact member clusters: 4" in census,
          "4 exact member clusters (shared, libfn, zed, license gap)")
    check("- exact whole-scroll clusters (non-segment): 2" in census,
          "2 whole-scroll clusters (file pair + Volume 1 pair)")
    check("manifest-file clusters 1, census-only 1" in census,
          "whole-scroll clusters split actionable vs census-only")
    check("- near clusters (report-only): 1" in census,
          "1 NEAR cluster (comment/whitespace twins)")
    check("binary-format scrolls (2," in census
          and "1 duplicate" in census,
          "binary scrolls tallied as excluded, dup group noted")
    check("3 copies" in census and "shared" in census,
          "shared-function cluster lists its 3 copies")

    # --- unpack the original, both routes
    for route, name in (("vol2", "t0"), ("vol3", "t0v3")):
        rc, out = run(["unpack", "--phext", fx, "--out",
                       os.path.join(td, name), "--from", route], td)
        check(rc == 0, f"unpack original --from {route} exits 0")
        got = read_tree(os.path.join(td, name))
        check(all(got[p] == file_bytes(p) for p in FILES),
              f"unpack original --from {route} byte-exact")

    # --- apply
    dedup = os.path.join(td, "dedup.phext")
    rc, out = run(["analyze", "--phext", fx, "--apply", "--out", dedup,
                   "--report", os.path.join(td, "apply.md")], td)
    check(rc == 0, "apply exits 0")
    apply_rep = open(os.path.join(td, "apply.md")).read()
    check("- stubs written: 5 segment, 1 whole-file" in apply_rep,
          "apply writes exactly the 5 planted segment stubs + 1 file stub")
    check("- stub economics:" in apply_rep,
          "apply report carries the stub-economics accounting")
    demoted = apply_rep.split("DEMOTED-TO-STALE")[1].split("###")[0]
    check(fmt(RECEIPT) in demoted, "proof receipt DEMOTED (libtcc1 stubbed)")
    check(fmt(VERDICT) in demoted, "gate verdict DEMOTED (hash binding)")
    check(fmt(DESIGN) in demoted, "design view DEMOTED (path rule)")
    check(fmt(REGISTER) not in demoted
          and fmt(REGISTER) in apply_rep.split("Also mentions")[1],
          "register that merely mentions a hash is NOT demoted")

    # --- the deduplicated phext: census + unpack proofs
    rc, out = run(["analyze", "--phext", dedup, "--out",
                   os.path.join(td, "census2.md")], td)
    census2 = open(os.path.join(td, "census2.md")).read()
    check("- exact member clusters: 0" in census2,
          "analyze(dedup) reports zero exact member clusters")
    check("manifest-file clusters 0" in census2,
          "analyze(dedup) reports zero manifest-file clusters")
    check("- dedup references already present: 5 segment, "
          "1 whole-scroll" in census2,
          "dedup references counted as references, not clusters")
    before = phext_io.load_phext(fx)
    after = phext_io.load_phext(dedup)
    check(all(after[c] == before[c] for c in (BIN1, BIN2, REG1, REG2,
                                              V1A, V1B)),
          "binary, region, and Volume 1 scrolls byte-untouched by apply")
    for route, name in (("vol2", "t1"), ("vol3", "t1v3")):
        rc, out = run(["unpack", "--phext", dedup, "--out",
                       os.path.join(td, name), "--from", route], td)
        check(rc == 0, f"unpack dedup --from {route} exits 0")
        got = read_tree(os.path.join(td, name))
        check(all(got[p] == file_bytes(p) for p in FILES),
              f"unpack(dedup) --from {route} reproduces every file "
              f"byte-for-byte (LOSSLESS)")
    rc, out = run(["unpack", "--phext", dedup, "--out",
                   os.path.join(td, "t1x"), "--from", "vol2"], td)
    check("dedup stubs expanded: 1" in out,
          "vol2 route reports its stub expansion")
    rc, out = run(["unpack", "--phext", dedup, "--out",
                   os.path.join(td, "t1y"), "--from", "vol3"], td)
    check("dedup stubs expanded: 6" in out,
          "vol3 route expands 5 segment stubs + 1 bridge stub")

    # --- idempotence
    dedup2 = os.path.join(td, "dedup2.phext")
    rc, out = run(["analyze", "--phext", dedup, "--apply", "--out",
                   dedup2, "--report", os.path.join(td, "apply2.md")], td)
    check(rc == 0 and "- stubs written: 0 segment, 0 whole-file"
          in open(os.path.join(td, "apply2.md")).read(),
          "apply on a deduplicated phext writes 0 stubs")
    check(sha256(open(dedup, "rb").read())
          == sha256(open(dedup2, "rb").read()),
          "apply is byte-idempotent")

    # --- refusal on unverifiable hashes
    bad = os.path.join(td, "corrupt.phext")
    with open(bad, "wb") as f:
        f.write(build_fixture(corrupt_index=True))
    rc, out = run(["analyze", "--phext", bad, "--apply", "--out",
                   os.path.join(td, "bad-out.phext")], td)
    check(rc == 1 and not os.path.exists(os.path.join(td,
                                                      "bad-out.phext")),
          "apply REFUSES a phext whose index hashes do not verify")

    print(f"\nfixture dir: {td}")
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
