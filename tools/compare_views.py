#!/usr/bin/env python3
"""compare_views.py — consolidation stage 2 audit.

Compares the Design views in lineage A (~/workspace/phcc-slice4/
phcc.phext) against the views regenerated over v4 members
(work/design.phext), and audits the regeneration step itself:
  * design.phext vs work/merged.phext may differ ONLY at the
    coordinates the generator owns (generated Design Scroll-1 views,
    the §A.2 pipeline view, the Design register scroll);
  * each changed view is classified: (a) its own members digest
    changed (file rebuilt by importer v4 — cross-checked against
    the v4 diff's files_rebuilt list), (b) its own digest is
    unchanged but the tree-wide name universes grew (cross-file
    edges / calls / globals sections may move), (c) other.
Writes logs/view-diff.json. Stdlib only.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

HOME = os.path.expanduser("~")
W = os.path.join(HOME, "workspace/phcc-consolidated")
PIPELINE = (1, 1, 1, 3, 2, 10, 1, 90, 1)
REGISTER = (1, 1, 1, 1, 2, 10, 1, 8, 1)
HDR = re.compile(r"^(artifact|source-sha256|members-sha256): (\S+)$", re.M)


def hdr_fields(content):
    head = content[:1500].decode("utf-8", "replace")
    return dict(HDR.findall(head))


def main():
    A = phext_io.load_phext(os.path.join(HOME, "workspace/phcc-slice4/phcc.phext"))
    M = phext_io.load_phext(os.path.join(W, "work/merged.phext"))
    D = phext_io.load_phext(os.path.join(W, "work/design.phext"))
    v4diff = json.load(open(os.path.join(
        HOME, "workspace/phcc-importer-v4/logs/v4-diff.json")))
    rebuilt = set(v4diff.get("files_rebuilt") or [])
    print(f"v4 files_rebuilt entries: {len(rebuilt)}")

    # ---- audit 1: regeneration touched only generator-owned coords
    owned = set()
    for k in set(M) | set(D):
        if M.get(k) != D.get(k):
            if k[3] == 3 and k[4] == 2 and k[8] == 1:
                owned.add(k)          # Design Scroll-1 views
            elif k in (PIPELINE, REGISTER):
                owned.add(k)
            else:
                print(f"UNOWNED CHANGE at {phext_io.fmt(k)}")
                sys.exit(1)
    print(f"regeneration changed coords (all generator-owned): {len(owned)}")

    # ---- audit 2: A views vs regenerated views
    def views(d):
        return {k: v for k, v in d.items()
                if k[3] == 3 and k[4] == 2 and k[8] == 1
                and v.startswith(b"GENERATED")
                and b"source-sha256:" in v[:1500]}
    va, vd = views(A), views(D)
    print(f"generated artifact views: A {len(va)}  regenerated {len(vd)}")
    assert set(va) == set(vd), "view coordinate sets differ!"
    manifest = phext_io.parse_manifest(A)
    by_addr = {(c[5], c[6], c[7]): p for p, c in manifest.items()}
    identical, ch_own, ch_universe, ch_other = [], [], [], []
    details = []
    for k in sorted(va):
        if va[k] == vd[k]:
            identical.append(k)
            continue
        fa, fd = hdr_fields(va[k]), hdr_fields(vd[k])
        path = by_addr.get((k[5], k[6], k[7]), phext_io.fmt(k))
        rec = {"path": path, "coord": phext_io.fmt(k),
               "members_old": fa.get("members-sha256"),
               "members_new": fd.get("members-sha256"),
               "source_same": fa.get("source-sha256") == fd.get("source-sha256"),
               "in_v4_files_rebuilt": path in rebuilt}
        if fa.get("members-sha256") != fd.get("members-sha256"):
            ch_own.append(k)
            rec["class"] = "own-members-changed"
        elif fa.get("source-sha256") == fd.get("source-sha256"):
            ch_universe.append(k)
            rec["class"] = "universe-growth-only"
        else:
            ch_other.append(k)
            rec["class"] = "other"
        details.append(rec)
    print(f"views byte-identical: {len(identical)}")
    print(f"views changed, own members digest changed: {len(ch_own)}")
    print(f"views changed, own bindings unchanged (universe growth): "
          f"{len(ch_universe)}")
    print(f"views changed, other: {len(ch_other)}")
    print(f"pipeline view identical: {A.get(PIPELINE) == D.get(PIPELINE)}")
    print(f"design register changed (expected; new stats + base sha): "
          f"{A.get(REGISTER) != D.get(REGISTER)}")
    out = {"views_total": len(va), "identical": len(identical),
           "changed_own_members": len(ch_own),
           "changed_universe_only": len(ch_universe),
           "changed_other": len(ch_other),
           "pipeline_identical": A.get(PIPELINE) == D.get(PIPELINE),
           "register_changed": A.get(REGISTER) != D.get(REGISTER),
           "regen_owned_coords_changed": len(owned),
           "details": details}
    with open(os.path.join(W, "logs/view-diff.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("report: logs/view-diff.json")


if __name__ == "__main__":
    main()
