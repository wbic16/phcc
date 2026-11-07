#!/usr/bin/env python3
"""verify_gate_splice.py — prove gate v8's section functions are the
donor gates' own code: extract each section function (and its comment
block) from v8 and from its donor and compare byte-for-byte, allowing
only the documented machine-#3 register relocation."""
import sys

WS = "/home/hatch/workspace"
v8 = open(f"{WS}/phcc-final/tools/phcc_gate.py").read()
builds = open(f"{WS}/phcc-builds-aligned/tools/phcc_gate.py").read()
slice6 = open(f"{WS}/phcc-slice6/tools/phcc_gate.py").read()
slice7 = open(f"{WS}/phcc-slice7/tools/phcc_gate.py").read()


def func(text, name):
    i = text.index(f"def {name}(")
    j = text.index("\ndef ", i + 1) if "\ndef " in text[i + 1:] else len(text)
    # also stop at a top-level comment separator block or main()
    k = text.find("\n# ---", i + 1)
    end = min(x for x in (j, k if k != -1 else len(text)) if x > i)
    return text[i:end].rstrip() + "\n"


checks = [
    ("machine_section", builds, v8, []),
    ("machine2_section", builds, v8, []),
    ("assembly_section", builds, v8, []),
    ("decode_binary_scroll", builds, v8, []),
    ("parse_proof_claims", builds, v8, []),
    ("tiers_from_receipts", builds, v8, []),
    ("parse_design_views", builds, v8, []),
    ("machine4_section", slice7, v8, []),
    ("machine3_section", slice6, v8, [
        ("MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 15, 1)",
         "MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 17, 1)"),
    ]),
]
# machine3's constants live above the function; check them separately
ok = True
for name, donor, mine, subs in checks:
    d, m = func(donor, name), func(mine, name)
    for a, b in subs:
        d = d.replace(a, b)
    same = d == m
    ok &= same
    print(f"{name}: {'IDENTICAL' if same else 'DIFFERS'} "
          f"(donor {len(d)} B, v8 {len(m)} B)")
    if not same:
        import difflib
        print("\n".join(difflib.unified_diff(
            d.splitlines(), m.splitlines(), "donor", "v8", lineterm="")))

# global constants used by machine3 in v8
for token in ("MACHINE3_COORD = (1, 1, 1, 3, 2, 5, 1, 2, 2)",
              "MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 17, 1)",
              "TCCELF_SRC_COORD = (1, 1, 1, 4, 2, 5, 1, 2, 1)",
              "MACHINE4_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 16, 1)",
              "BUILD_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 15, 1)"):
    present = token in v8
    ok &= present
    print(f"const {token[:52]}...: {'present' if present else 'MISSING'}")
print("SPLICE PROOF:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
