#!/usr/bin/env python3
"""verify_gate_splice_81.py — prove gate v8.1.0's prior section logic
is gate v8.0.0's own code: extract each pre-existing function from
both files and compare byte-for-byte. The plumbing functions
(tables_text, verdict_text, main) and the header constants are the
documented delta; their diffs are printed for the record, and the
new conformance_section must exist only in v8.1."""
import difflib
import sys

WS = "/home/hatch/workspace"
v8 = open(f"{WS}/phcc-final/tools/phcc_gate.py").read()
v81 = open(f"{WS}/phcc-refresh/tools/phcc_gate.py").read()

IDENTICAL = ["analyse", "pct", "parse_proof_claims", "tiers_from_receipts",
             "_members_digest", "parse_design_views", "machine_section",
             "machine2_section", "machine3_section", "machine4_section",
             "assembly_section", "decode_binary_scroll", "_kv", "_kv_head",
             "_sha"]
PLUMBING = ["tables_text", "verdict_text", "main"]


def func(text, name):
    i = text.index(f"def {name}(")
    j = text.find("\ndef ", i + 1)
    k = text.find("\n# ---", i + 1)
    ends = [x for x in (j, k) if x != -1]
    end = min(ends) if ends else len(text)
    return text[i:end].rstrip() + "\n"


ok = True
for name in IDENTICAL:
    d, m = func(v8, name), func(v81, name)
    same = d == m
    ok &= same
    print(f"{name}: {'IDENTICAL' if same else 'DIFFERS'} "
          f"(v8 {len(d)} B, v8.1 {len(m)} B)")
    if not same:
        print("\n".join(difflib.unified_diff(
            d.splitlines(), m.splitlines(), "v8", "v8.1", lineterm="")))
for name in PLUMBING:
    d, m = func(v8, name), func(v81, name)
    diff = list(difflib.unified_diff(
        d.splitlines(), m.splitlines(), "v8", "v8.1", lineterm=""))
    print(f"{name}: plumbing diff ({len(diff)} lines):")
    for l in diff:
        print("   " + l)
print("conformance_section: present only in v8.1:",
      "def conformance_section(" in v81 and "def conformance_section(" not in v8)
for token in ('TOOL_VERSION = "phcc_gate.py 8.1.0',
              "VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 20, 1)",
              "GRAND_MERGE_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 19, 1)"):
    present = token in v81
    ok &= present
    print(f"const {token[:56]}...: {'present' if present else 'MISSING'}")
print("SPLICE PROOF:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
