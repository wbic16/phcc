#!/usr/bin/env python3
"""run_trace_tests.py — dynamic conformance (design A.3 level 2) for
the Slice 4 preprocessor conditional-stack machine.

For each authored trace test:
  * the independent model (trace_model.py) predicts the emitted
    marker set (or the mandated error) and the frame-state path;
  * the path is checked for legality against the transitions parsed
    out of the machine scroll itself;
  * the real tcc, built on aletheia-core from the rebased tree,
    runs `tcc -E -P` on the input; observed markers (or the error
    and exit code) are compared with the prediction.
A mismatch names the test's mandated path — including the exact
transition line from the machine scroll that the observation
violates.

The tests/pp corpus is also run through the same tcc and compared
with each file's .expect, normalized the way tests/pp/Makefile
does (diff -b; 02 also -w; 16 also -B).

Modes:
  (default)        all tests must pass against --bin-dir's tcc.
  --expect-fail T  exit-test mode: the named tests MUST fail, and
                   the failure output names the violated transition.

Remote execution goes through ~/workspace/ranch-proxy (the direct
ssh ProxyCommand recipe in the slice brief fails in this
environment: the local nc rejects it; ranch-proxy is the
established route used by Slices 0-3).

Writes scratch/dynamic_results.json in the slice directory.
Stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SLICE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import trace_model
from trace_model import Model, ModelError, Unsupported

RANCH = os.path.expanduser("~/workspace/ranch-proxy/ranch")
NODE = "aletheia-core"

# ----------------------------------------------------------------
# authored trace tests. expect: list of markers, or ("error", substr)
TESTS = [
    dict(id="T01", title="#if true, #else shadowed",
         input="#if 1\nMK_T01_A\n#else\nMK_T01_B\n#endif\n",
         expect=["MK_T01_A"]),
    dict(id="T02", title="#if false, #else active",
         input="#if 0\nMK_T02_A\n#else\nMK_T02_B\n#endif\n",
         expect=["MK_T02_B"]),
    dict(id="T03", title="#elif chain: false, false, true, quiet, else",
         input=("#if 0\nMK_T03_A\n#elif 0\nMK_T03_B\n#elif 1\n"
                "MK_T03_C\n#elif 1\nMK_T03_D\n#else\nMK_T03_E\n#endif\n"),
         expect=["MK_T03_C"]),
    dict(id="T04", title="nested: #elif after a taken inner branch "
                         "(exit-test target)",
         input=("#if 1\n#if 1\nMK_T04_A\n#elif 1\nMK_T04_B\n#else\n"
                "MK_T04_C\n#endif\n#endif\n"),
         expect=["MK_T04_A"]),
    dict(id="T05", title="nested directives inside a skipped region "
                         "are counted, not executed",
         input=("#if 0\n#if 1\nMK_T05_A\n#else\nMK_T05_B\n#endif\n"
                "#else\nMK_T05_C\n#endif\n"),
         expect=["MK_T05_C"]),
    dict(id="T06", title="#ifdef/#ifndef and defined() in #if",
         input=("#define FOO 1\n#ifdef FOO\nMK_T06_A\n#endif\n"
                "#ifndef FOO\nMK_T06_B\n#else\nMK_T06_C\n#endif\n"
                "#if defined(FOO) && !defined(BAR)\nMK_T06_D\n#endif\n"
                "#define BAR 1\n#if defined(BAR)\nMK_T06_E\n#endif\n"),
         expect=["MK_T06_A", "MK_T06_C", "MK_T06_D", "MK_T06_E"]),
    dict(id="T07", title="directive-shaped text inside strings and "
                         "comments in a skipped region",
         input=("#if 0\nconst char *s = \"#endif\";\n/* #if 1 */\n"
                "MK_T07_A\n#endif\nMK_T07_B\n"),
         expect=["MK_T07_B"]),
    dict(id="T08", title="#error inside a skipped region does not fire",
         input="#if 0\n#error must not fire\n#endif\nMK_T08_OK\n",
         expect=["MK_T08_OK"]),
    dict(id="T09", title="macro context: object/function-like macros, "
                         "stringize cannot synthesize a directive",
         input=("#define N 2\n#define TWICE(x) ((x) + (x))\n"
                "#define S(x) #x\n#if N == 2\nMK_T09_A\n#endif\n"
                "int v = TWICE(3);\nconst char *w = S(endif);\n"
                "MK_T09_B\n"),
         expect=["MK_T09_A", "MK_T09_B"]),
    dict(id="T10", title="error: #else without matching #if",
         input="#else\n",
         expect=("error", "#else without matching #if")),
    dict(id="T11", title="error: #elif after #else",
         input="#if 0\n#else\n#elif 1\n#endif\n",
         expect=("error", "#elif after #else")),
    dict(id="T12", title="error: #else after #else",
         input="#if 1\n#else\n#else\n#endif\n",
         expect=("error", "#else after #else")),
    dict(id="T13", title="error: missing #endif at end of file",
         input="#if 1\nMK_T13_A\n",
         expect=("error", "missing #endif")),
    dict(id="T14", title="error: #endif without matching #if",
         input="#endif\n",
         expect=("error", "#endif without matching #if")),
    dict(id="T15", title="#elif chain: second true #elif stays quiet",
         input=("#if 0\n#elif 1\nMK_T15_A\n#elif 1\nMK_T15_B\n"
                "#endif\n"),
         expect=["MK_T15_A"]),
    dict(id="T16", title="three-level nesting, innermost #else",
         input=("#if 1\n#if 1\n#if 0\nMK_T16_A\n#else\nMK_T16_B\n"
                "#endif\n#endif\n#endif\n"),
         expect=["MK_T16_B"]),
]


def ranch(cmd, timeout=120):
    r = subprocess.run([RANCH, "exec", NODE, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout


def parse_scroll_transitions(scroll_path):
    text = open(scroll_path).read()
    out = {}
    for line in text.splitlines():
        m = re.match(r"^  (\S+) --(ev_[a-z_]+) \[(.*)\]--> (.+)$", line)
        if m:
            out[(m.group(1), m.group(2), m.group(4).strip())] = line.strip()
    return out


def path_legal(path, transitions):
    """Each model step must correspond to a scroll transition
    (ANY matches any from-state). Returns list of problems."""
    problems = []
    for frm, ev, to in path:
        hit = None
        for (f, e, t), line in transitions.items():
            if e == ev and t == to and (f == frm or f == "ANY"):
                hit = line
                break
        if not hit:
            problems.append(f"no scroll transition for {frm} --{ev}--> {to}")
    return problems


def scroll_lines_for(path, transitions):
    lines = []
    for frm, ev, to in path:
        for (f, e, t), line in transitions.items():
            if e == ev and t == to and (f == frm or f == "ANY"):
                lines.append(line)
                break
    return lines


def normalize(text, mode):
    out = []
    for line in text.splitlines():
        if "w" in mode:
            line = re.sub(r"\s+", "", line)
        else:
            line = re.sub(r"\s+", " ", line).strip()
        out.append(line)
    if "B" in mode:
        out = [l for l in out if l]
    while out and out[-1] == "":
        out.pop()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default="~/phcc-slice4-tree")
    ap.add_argument("--expect-fail", default=None,
                    help="comma-separated test ids that MUST fail")
    ap.add_argument("--scroll", default=os.path.join(
        SLICE, "scratch", "machine_scroll.txt"))
    a = ap.parse_args()
    expect_fail = set((a.expect_fail or "").split(",")) - {""}

    transitions = parse_scroll_transitions(a.scroll)
    tests_dir = os.path.join(SLICE, "scratch", "tests")
    os.makedirs(tests_dir, exist_ok=True)
    for t in TESTS:
        with open(os.path.join(tests_dir, t["id"] + ".c"), "w") as f:
            f.write(t["input"])

    # ship inputs to the ranch and run them
    ranch("mkdir -p ~/phcc-slice4-tests ~/phcc-slice4-out")
    subprocess.run([RANCH, "copy", NODE,
                    os.path.join(SLICE, "scratch", "tests.tar.gz"),
                    "~/tests.tar.gz"], capture_output=True)
    # (re)pack inputs as one tar for a single copy
    subprocess.run(["tar", "-czf",
                    os.path.join(SLICE, "scratch", "tests.tar.gz"),
                    "-C", tests_dir, "."], check=True)
    subprocess.run([RANCH, "copy", NODE,
                    os.path.join(SLICE, "scratch", "tests.tar.gz"),
                    "~/tests.tar.gz"], check=True, capture_output=True)
    bindir = a.bin_dir
    run_cmd = (
        f"rm -rf ~/phcc-slice4-tests ~/phcc-slice4-out; "
        f"mkdir -p ~/phcc-slice4-tests ~/phcc-slice4-out; "
        f"tar -xzf ~/tests.tar.gz -C ~/phcc-slice4-tests; "
        f"for f in ~/phcc-slice4-tests/*.c; do "
        f"b=$(basename $f .c); "
        f"{bindir}/tcc -E -P $f > ~/phcc-slice4-out/$b.out "
        f"2> ~/phcc-slice4-out/$b.err; echo $? > ~/phcc-slice4-out/$b.rc; "
        f"done; "
        f"cd ~/phcc-slice4-tree/tests/pp; "
        f"for f in *.c *.S; do b=$(basename $f); "
        f"{bindir}/tcc -E -P $f > ~/phcc-slice4-out/corpus-$b.out 2>&1; "
        f"echo $? > ~/phcc-slice4-out/corpus-$b.rc; done; "
        f"{bindir}/tcc -version | head -1")
    ver = ranch(run_cmd, timeout=300).strip().splitlines()
    tcc_version = ver[-1] if ver else "unknown"

    # fetch outputs (ranch copy is upload-only; base64 over exec)
    import base64
    ranch("tar -czf ~/out.tar.gz -C ~/phcc-slice4-out .")
    b64 = ranch("base64 -w0 ~/out.tar.gz", timeout=300)
    payload = "".join(l for l in b64.splitlines()
                      if not l.startswith("[ranch:"))
    with open(os.path.join(SLICE, "scratch", "out.tar.gz"), "wb") as f:
        f.write(base64.b64decode(payload))
    outdir = os.path.join(SLICE, "scratch", "out")
    subprocess.run(["rm", "-rf", outdir])
    os.makedirs(outdir)
    subprocess.run(["tar", "--no-same-owner", "-xzf",
                    os.path.join(SLICE, "scratch", "out.tar.gz"),
                    "-C", outdir], check=True)

    def read(name):
        p = os.path.join(outdir, name)
        return open(p, errors="replace").read() if os.path.exists(p) else ""

    results = {"tcc_version": tcc_version, "tests": [], "corpus": []}
    failures = 0
    for t in TESTS:
        model = Model()
        entry = {"id": t["id"], "title": t["title"]}
        try:
            emitted, path = model.run(t["input"])
            model_error = None
        except ModelError as e:
            emitted, path, model_error = None, model.path, str(e)
        except Unsupported as e:
            entry.update(result="MODEL-UNSUPPORTED", detail=str(e))
            results["tests"].append(entry)
            failures += 1
            print(f"{t['id']} MODEL-UNSUPPORTED: {e}")
            continue
        entry["model_path"] = ["%s --%s--> %s" % s for s in path]
        legal = path_legal(path, transitions)
        entry["path_legal"] = not legal
        out = read(t["id"] + ".out")
        err = read(t["id"] + ".err")
        rc = int((read(t["id"] + ".rc").strip() or "-1"))
        observed = [l.strip() for l in out.splitlines()
                    if re.match(r"^MK_[A-Z0-9_]+$", l.strip())]
        entry["observed_markers"] = observed
        entry["rc"] = rc
        if isinstance(t["expect"], tuple):  # error test
            ok = (model_error == t["expect"][1] and rc != 0
                  and t["expect"][1] in err and not legal)
            entry["expected_error"] = t["expect"][1]
            entry["observed_error_in_stderr"] = t["expect"][1] in err
        else:
            ok = (model_error is None and emitted == t["expect"]
                  and observed == t["expect"] and rc == 0
                  and not legal)
            entry["expected_markers"] = t["expect"]
            entry["model_markers"] = emitted
        entry["result"] = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
            named = scroll_lines_for(path, transitions)
            entry["violated_transitions"] = named
            print(f"{t['id']} FAIL: {t['title']}")
            print(f"     model markers={emitted} error={model_error}")
            print(f"     observed markers={observed} rc={rc} "
                  f"stderr={err.strip()[:200]!r}")
            print(f"     mandated path (machine scroll transitions):")
            for ln in named:
                print(f"       {ln}")
            if legal:
                print(f"     path legality problems: {legal}")
        else:
            print(f"{t['id']} PASS: {t['title']}")
        results["tests"].append(entry)

    # corpus: tests/pp vs .expect, Makefile normalization
    pp_dir = os.path.expanduser("~/workspace/phcc-slice0/phcc/tests/pp")
    corpus_fail = 0
    for name in sorted(os.listdir(pp_dir)):
        if not (name.endswith(".c") or name.endswith(".S")):
            continue
        base = name.rsplit(".", 1)[0]
        expect_file = os.path.join(pp_dir, base + ".expect")
        if not os.path.exists(expect_file):
            continue
        mode = "b"
        if base == "02":
            mode += "w"
        if base == "16":
            mode += "B"
        got = normalize(read(f"corpus-{name}.out"), mode)
        exp = normalize(open(expect_file, errors="replace").read(), mode)
        ok = got == exp
        if not ok:
            corpus_fail += 1
        results["corpus"].append(
            {"file": f"tests/pp/{name}", "result": "PASS" if ok else "FAIL"})
        print(f"corpus {name}: {'PASS' if ok else 'FAIL'}")

    npass = sum(1 for e in results["tests"] if e["result"] == "PASS")
    cpass = sum(1 for e in results["corpus"] if e["result"] == "PASS")
    results["summary"] = {
        "authored_pass": npass, "authored_total": len(TESTS),
        "corpus_pass": cpass, "corpus_total": len(results["corpus"])}
    print(f"summary: authored {npass}/{len(TESTS)}  "
          f"corpus {cpass}/{len(results['corpus'])}  ({tcc_version})")
    with open(os.path.join(SLICE, "scratch", "dynamic_results.json"),
              "w") as f:
        json.dump(results, f, indent=1)

    if expect_fail:
        failed_ids = {e["id"] for e in results["tests"]
                      if e["result"] == "FAIL"}
        if failed_ids == expect_fail:
            print(f"exit-test expectation met: exactly {sorted(failed_ids)} "
                  f"failed, naming the violated transition(s) above")
            return 0
        print(f"exit-test expectation NOT met: expected failures "
              f"{sorted(expect_fail)}, got {sorted(failed_ids)}")
        return 1
    return 0 if failures == 0 and corpus_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
