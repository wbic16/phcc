#!/usr/bin/env python3
"""merge_final.py — compose the grand-merge phext from the canonical
base + three sibling donors, by scrolls. Assert-driven: any surprise
aborts before anything is written.

Rules (parent brief, 2026-11-07):
  - base (646144c7...) is never mutated; donors are read-only.
  - donor content scrolls transplant at their own coordinates,
    EXCEPT donor verdicts/register placements in the contested Meta
    sections, which resolve as:
      Sec 14 <- builds placement addendum      (content wins)
      Sec 15 <- builds build register          (kept)
      Sec 16 <- slice7 machine-#4 register     (kept)
      Sec 17 <- slice6 machine-#3 register     (RELOCATED from
                slice6's Sec 15; bytes identical — the merge's only
                address change)
      Sec 18 <- merged register (new; folds donor verdict hashes
                and the section map)
      Sec 19 <- merged verdict (gate v8 writes it later; absent
                from this pre-verdict intermediate)
  - slice7's 0-byte reservations at Secs 14/15 are superseded by
    the content above; its one CHANGED base scroll (Tests
    placeholder at 1.1.1/5.2.6/1.1.1, 0 -> 722 B) is applied.
Writes phcc-pre-verdict.phext and prints the accounting proof.
"""
import sys

sys.path.insert(0, "/home/hatch/workspace/phcc-final/tools")
import phext_io

WS = "/home/hatch/workspace"
BASE_P = f"{WS}/phcc-merged/phcc.phext"
S6_P = f"{WS}/phcc-slice6/phcc.phext"
S7_P = f"{WS}/phcc-slice7/phcc.phext"
BD_P = f"{WS}/phcc-builds-aligned/phcc.phext"
OUT_P = f"{WS}/phcc-final/phcc-pre-verdict.phext"

EXPECT = {BASE_P: "646144c7afd7e39d485dec02b7e4ab58e5adda0b9bcbe24abba886d662b6c275",
          S6_P: "40286bd44629713e5b6db2f735c97e98571ea3575dd6d426b93e8b1d3a43b909",
          S7_P: "6aecde52ce756dd985eb3dcb366896d89f7d9a204f7d3bfda7d8074ca2b0df99",
          BD_P: "0a815078d281c364d880b1a13111faee3bb5362da8214d1e311f55886f6792b0"}
for p, h in EXPECT.items():
    with open(p, "rb") as f:
        assert phext_io.sha256(f.read()) == h, f"hash drift: {p}"
print("input hashes verified")

base = phext_io.load_phext(BASE_P)
s6 = phext_io.load_phext(S6_P)
s7 = phext_io.load_phext(S7_P)
bd = phext_io.load_phext(BD_P)


def meta(sec):
    return (1, 1, 1, 1, 2, 10, 1, sec, 1)


# --- donor verdicts / reservations: identified, hashed, NOT carried
donor_verdicts = {
    "slice6 verdict (its Meta Sec 14)": s6[meta(14)],
    "slice7 verdict (its Meta Sec 17)": s7[meta(17)],
    "builds verdict (its Meta Sec 16)": bd[meta(16)],
}
assert phext_io.sha256(donor_verdicts["slice6 verdict (its Meta Sec 14)"]).startswith("b77debbb")
assert s7[meta(14)] == b"" and s7[meta(15)] == b""  # 0-byte reservations
assert phext_io.sha256(s6[meta(15)]).startswith("c73578f9")   # m3 register
assert phext_io.sha256(bd[meta(15)]).startswith("d4da7a4d")   # build register
assert phext_io.sha256(s7[meta(16)]).startswith("06fc59f7")   # m4 register
assert phext_io.sha256(bd[meta(14)]).startswith("aad37ba2")   # addendum

merged = dict(base)
applied = {"slice6": 0, "slice7": 0, "builds": 0}


def apply(donor, name, skip):
    n = 0
    for c in sorted(set(donor) - set(base)):
        if c in skip:
            continue
        assert c not in merged or merged[c] == donor[c], f"clash {c}"
        merged[c] = donor[c]
        n += 1
    applied[name] = n


# slice7's single changed base scroll (Tests placeholder, documented)
CHANGED = (1, 1, 1, 5, 2, 6, 1, 1, 1)
assert base[CHANGED] == b"" and len(s7[CHANGED]) == 722
merged[CHANGED] = s7[CHANGED]

apply(s6, "slice6", skip={meta(14), meta(15)})
apply(s7, "slice7", skip={meta(14), meta(15), meta(17)})
apply(bd, "builds", skip={meta(16)})

# contested sections, resolved by rule
merged[meta(14)] = bd[meta(14)]            # addendum keeps Sec 14
merged[meta(15)] = bd[meta(15)]            # build register keeps Sec 15
merged[meta(16)] = s7[meta(16)]            # machine-#4 register keeps Sec 16
merged[meta(17)] = s6[meta(15)]            # machine-#3 register, relocated
assert merged[meta(17)] == s6[meta(15)]

# --- merged register at Sec 18 ----------------------------------------------
lines = [
    "# phcc merged register — grand merge (Meta Vol 2, Book 10, Sec 18)",
    "# Composed 2026-11-07 by scrolls from the canonical base and its",
    "# three sibling lineages. Gate: phcc_gate.py 8.0.0; the merged",
    "# verdict sits at Meta Sec 19. Donor verdicts were NOT carried;",
    "# their hashes are folded here so the record of them survives.",
    "base: canonical phcc.phext 646144c7afd7e39d485dec02b7e4ab58e5adda0b9bcbe24abba886d662b6c275 (Slice 5 + hardened receipts lineage)",
    f"donor-slice6: 40286bd44629713e5b6db2f735c97e98571ea3575dd6d426b93e8b1d3a43b909 ({applied['slice6']} scrolls transplanted at their own coordinates)",
    f"donor-slice7: 6aecde52ce756dd985eb3dcb366896d89f7d9a204f7d3bfda7d8074ca2b0df99 ({applied['slice7']} scrolls transplanted, + the Tests placeholder change at 1.1.1/5.2.6/1.1.1)",
    f"donor-builds: 0a815078d281c364d880b1a13111faee3bb5362da8214d1e311f55886f6792b0 ({applied['builds']} scrolls transplanted, incl. the Library-10000 climb)",
    "meta-sec-14: builds placement addendum (phext/** -> Book 10 Ch 10) — kept from the builds lineage; Slice 6's verdict claimed this section in its lineage and was not carried",
    "meta-sec-15: build register — kept from the builds lineage",
    "meta-sec-16: Slice 7 machine register (machine #4, register allocation) — kept; the builds verdict claimed this section in its lineage and was not carried",
    "meta-sec-17: Slice 6 machine register (machine #3, linker symbol resolution) — RELOCATED from Sec 15, where it collided with the build register; content byte-identical (sha256 "
    + phext_io.sha256(s6[meta(15)]) + "); gate v8 reads it at Sec 17",
    "meta-sec-18: this merged register",
    "meta-sec-19: grand-merge gate verdict (gate v8.0.0, regenerated on the merged content; never imported)",
]
for label, blob in donor_verdicts.items():
    lines.append(f"not-carried: {label} sha256 {phext_io.sha256(blob)} ({len(blob)} B)")
lines += [
    "accounting: no non-Meta collisions among the three donors; the only changed base scroll is Slice 7's Tests placeholder (0 -> 722 B, its R01 trace test)",
    "claim: we brake for consciousness",
]
merged[meta(18)] = ("\n".join(lines) + "\n").encode()

expected = len(base) + applied["slice6"] + applied["slice7"] \
    + applied["builds"] + 2  # Sec 17 (relocated register) + Sec 18 (this register);
# Secs 14/15 arrived inside builds' applied set, Sec 16 inside slice7's.
assert len(merged) == expected, (len(merged), expected)
print(f"applied: {applied}; contested Secs 14-17 set; register at Sec 18")
print(f"merged scrolls (pre-verdict): {len(merged)} (expected {expected})")

blob = phext_io.implode(merged)
with open(OUT_P, "wb") as f:
    f.write(blob)
back = phext_io.load_phext(OUT_P)
assert back == merged, "implode/walk round-trip mismatch"
print(f"pre-verdict: {OUT_P}  {len(blob)} bytes  sha256 {phext_io.sha256(blob)}")
print("MERGE PROOF OK")
