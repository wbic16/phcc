#!/usr/bin/env python3
"""consolidate.py — phcc lineage consolidation, stage 1 (the merge).

Merges the two phcc phext lineages into one canonical phext:
  lineage A (phases):  ~/workspace/phcc-slice4/phcc.phext
                       SHA-256 de1ac0c6edcd33fcd082392ea8bbd28b17f5a6fdd7d8587cbf87211177f09eb1
  lineage B (members): ~/workspace/phcc-importer-v4/phcc-fn.phext
                       SHA-256 bfdf93ed602415c954b990455ab57c3449dc8830b571e1c3bbecf98ae3566e76

Rule: A everywhere, except Volume 3, which is taken from B in full
(importer v4 is a strict refinement of v3: every v3 member keeps its
exact address and payload; B's Vol 3 coordinate set is a superset of
A's). PROOF, not assertion: the merged scroll set is diffed against
both inputs in full —
  * every scroll with volume != 3 must equal A's byte-for-byte, and
    the merged set must contain no non-Vol-3 coordinate A lacks;
  * every scroll with volume == 3 must equal B's byte-for-byte, and
    the merged set must contain no Vol-3 coordinate B lacks.
The written file is then re-loaded and the same diff is run against
the bytes on disk. Any mismatch aborts with exit 1.

Usage: consolidate.py [--out FILE] [--report JSON]
Stdlib only.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

HOME = os.path.expanduser("~")
A_PATH = os.path.join(HOME, "workspace/phcc-slice4/phcc.phext")
B_PATH = os.path.join(HOME, "workspace/phcc-importer-v4/phcc-fn.phext")
A_SHA = "de1ac0c6edcd33fcd082392ea8bbd28b17f5a6fdd7d8587cbf87211177f09eb1"
B_SHA = "bfdf93ed602415c954b990455ab57c3449dc8830b571e1c3bbecf98ae3566e76"


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def diff_proof(merged, A, B):
    """Full scroll-set diff of the merge against both inputs."""
    out = {}
    non_a = {k: v for k, v in A.items() if k[4] != 3}
    non_m = {k: v for k, v in merged.items() if k[4] != 3}
    out["nonvol3_A"] = len(non_a)
    out["nonvol3_merged"] = len(non_m)
    out["nonvol3_missing_vs_A"] = sorted(
        phext_io.fmt(k) for k in set(non_a) - set(non_m))
    out["nonvol3_extra_vs_A"] = sorted(
        phext_io.fmt(k) for k in set(non_m) - set(non_a))
    out["nonvol3_differing"] = sorted(
        phext_io.fmt(k) for k in set(non_a) & set(non_m)
        if non_a[k] != non_m[k])
    vol_b = {k: v for k, v in B.items() if k[4] == 3}
    vol_m = {k: v for k, v in merged.items() if k[4] == 3}
    vol_a = {k: v for k, v in A.items() if k[4] == 3}
    out["vol3_B"] = len(vol_b)
    out["vol3_merged"] = len(vol_m)
    out["vol3_missing_vs_B"] = sorted(
        phext_io.fmt(k) for k in set(vol_b) - set(vol_m))
    out["vol3_extra_vs_B"] = sorted(
        phext_io.fmt(k) for k in set(vol_m) - set(vol_b))
    out["vol3_differing_vs_B"] = sorted(
        phext_io.fmt(k) for k in set(vol_b) & set(vol_m)
        if vol_b[k] != vol_m[k])
    # context counts: how A's Vol 3 relates to B's Vol 3
    common = set(vol_a) & set(vol_b)
    out["vol3_A"] = len(vol_a)
    out["vol3_common_coords_AB"] = len(common)
    out["vol3_common_identical_AB"] = sum(
        1 for k in common if vol_a[k] == vol_b[k])
    out["vol3_common_differing_AB"] = sum(
        1 for k in common if vol_a[k] != vol_b[k])
    out["vol3_only_in_B"] = len(set(vol_b) - set(vol_a))
    out["vol3_only_in_A"] = len(set(vol_a) - set(vol_b))
    ok = (not out["nonvol3_missing_vs_A"] and not out["nonvol3_extra_vs_A"]
          and not out["nonvol3_differing"]
          and not out["vol3_missing_vs_B"] and not out["vol3_extra_vs_B"]
          and not out["vol3_differing_vs_B"])
    out["proof_ok"] = ok
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        HOME, "workspace/phcc-consolidated/work/merged.phext"))
    ap.add_argument("--report", default=os.path.join(
        HOME, "workspace/phcc-consolidated/logs/merge-diff.json"))
    a = ap.parse_args()

    for path, want in ((A_PATH, A_SHA), (B_PATH, B_SHA)):
        got = file_sha(path)
        print(f"input {path}: sha256 {got}")
        assert got == want, f"INPUT HASH MISMATCH for {path}"
    print("input hashes verified")

    A = phext_io.load_phext(A_PATH)
    B = phext_io.load_phext(B_PATH)
    print(f"A scrolls: {len(A)}   B scrolls: {len(B)}")

    merged = {k: v for k, v in A.items() if k[4] != 3}
    merged.update({k: v for k, v in B.items() if k[4] == 3})
    proof = diff_proof(merged, A, B)
    print(json.dumps({k: (v if not isinstance(v, list) else
                          f"<{len(v)} coords>") for k, v in proof.items()},
                     indent=1))
    assert proof["proof_ok"], "MERGE DIFF PROOF FAILED (in memory)"

    blob = phext_io.implode(merged)
    with open(a.out, "wb") as f:
        f.write(blob)
    print(f"merged written: {a.out}  {len(blob)} bytes  "
          f"sha256 {hashlib.sha256(blob).hexdigest()}")

    back = phext_io.load_phext(a.out)
    proof2 = diff_proof(back, A, B)
    assert proof2["proof_ok"], "MERGE DIFF PROOF FAILED (on disk)"
    print("on-disk re-load diff proof: OK")
    proof["merged_bytes"] = len(blob)
    proof["merged_sha256"] = hashlib.sha256(blob).hexdigest()
    proof["merged_scrolls"] = len(back)
    with open(a.report, "w") as f:
        json.dump(proof, f, indent=1)
    print(f"report: {a.report}")


if __name__ == "__main__":
    main()
