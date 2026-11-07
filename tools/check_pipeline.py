#!/usr/bin/env python3
"""check_pipeline.py — conformance test for the §A.2 pipeline view.

Design §A.2: the interaction view is *tested prose*. This checker
verifies, against the extractor-derived call graph (the same
name-based extraction the Design views use — Vol 3 member payloads,
never hand-maintained data):

  1. every function NAMED in the view's claims block exists as a
     function member in the file the view names for it;
  2. every claimed call edge `path: caller -> callee` exists: the
     caller's definition payload in that file calls the callee by
     name, and the callee exists as a function member somewhere in
     Source.

Mismatches are reported BY NAME, one line each; exit code is 1 if
any claim fails. Stdlib only.

Usage: check_pipeline.py PHEXT
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

PIPELINE_COORD = (1, 1, 1, 3, 2, 10, 1, 90, 1)
KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "case",
            "do", "else", "defined", "typedef", "struct", "union", "enum"}
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
NAME_RE = re.compile(r"^- ([A-Za-z_]\w*) @ (\S+)$")
EDGE_RE = re.compile(r"^- (\S+): ([A-Za-z_]\w*) -> ([A-Za-z_]\w*)$")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    scrolls = phext_io.load_phext(sys.argv[1])
    view = scrolls.get(PIPELINE_COORD)
    if not view:
        print(f"FAIL: no pipeline view at {phext_io.fmt(PIPELINE_COORD)}")
        return 1
    text = view.decode("utf-8", "replace")
    names, edges = [], []
    in_block = False
    for line in text.splitlines():
        if line.startswith("## machine-checked claims"):
            in_block = True
            continue
        if in_block:
            m = NAME_RE.match(line)
            if m:
                names.append((m.group(1), m.group(2)))
            m = EDGE_RE.match(line)
            if m:
                edges.append((m.group(1), m.group(2), m.group(3)))
    if not names or not edges:
        print("FAIL: claims block missing or empty "
              f"(names={len(names)}, edges={len(edges)})")
        return 1

    manifest = phext_io.parse_manifest(scrolls)
    members_in = defaultdict(set)      # path -> function member names
    defined_somewhere = set()
    calls = {}                         # (path, caller) -> set(callee)
    for path, coord in manifest.items():
        b, ch, sec = coord[5], coord[6], coord[7]
        idx = scrolls.get((1, 1, 1, 4, 3, b, ch, sec, 1))
        if not idx:
            continue
        for line in idx.decode("utf-8", "replace").splitlines():
            p = line.split("\t")
            if len(p) != 6 or p[1] != "function":
                continue
            fn_names = [n.strip() for n in p[2].split(",")]
            for nm in fn_names:
                members_in[path].add(nm)
                if p[3] == "def":
                    defined_somewhere.add(nm)
            if p[3] == "def":
                raw = scrolls[(1, 1, 1, 4, 3, b, ch, sec, int(p[0]))]
                body = raw.split(b"\n", 1)[1].decode("utf-8", "replace")
                called = {c for c in CALL_RE.findall(body)
                          if c not in KEYWORDS}
                for nm in fn_names:
                    calls.setdefault((path, nm), set()).update(called)

    failures = []
    for nm, path in names:
        if nm in members_in.get(path, set()):
            print(f"PASS name: {nm} @ {path}")
        else:
            failures.append(f"name: {nm} @ {path} — no such function "
                            f"member in that file")
            print(f"FAIL name: {nm} @ {path}")
    for path, caller, callee in edges:
        ok_edge = callee in calls.get((path, caller), set())
        ok_def = callee in defined_somewhere
        if ok_edge and ok_def:
            print(f"PASS edge: {path}: {caller} -> {callee}")
        else:
            why = []
            if not ok_edge:
                why.append(f"{caller}'s definition in {path} does not "
                           f"call {callee} by name")
            if not ok_def:
                why.append(f"{callee} is not defined in any Source "
                           f"artifact")
            failures.append(f"edge: {path}: {caller} -> {callee} — "
                            + "; ".join(why))
            print(f"FAIL edge: {path}: {caller} -> {callee}")
    print(f"\nconformance: {len(names)} names, {len(edges)} edges, "
          f"{len(failures)} mismatches")
    for f in failures:
        print(f"MISMATCH {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
