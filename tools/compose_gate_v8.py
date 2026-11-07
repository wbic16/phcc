#!/usr/bin/env python3
"""compose_gate_v8.py — compose phcc_gate.py v8.0.0 (grand merge) from
the three donor gate copies, by splicing, so every section function
is the donor's own code:

  chassis + coverage/tiers/proofs/design/machine-#1/machine-#2 +
  assembly (canonical binary decode)  <- builds gate v6.0.1
  machine-#3 section                   <- slice6 gate v6.0.0
      (one constant changed: its register moved Meta Sec 15 -> 17,
       the merge's sole address relocation; comment updated to say so)
  machine-#4 section                   <- slice7 gate v7.0.0 (verbatim)

Header, TOOL_VERSION, VERDICT_COORD (Meta Sec 19) and the verdict
exclusion set are the merged lineage's own. Writes the composed gate
to phcc-final/tools/phcc_gate.py and asserts every splice landed.
"""
import re

WS = "/home/hatch/workspace"
builds = open(f"{WS}/phcc-builds-aligned/tools/phcc_gate.py").read()
slice6 = open(f"{WS}/phcc-slice6/tools/phcc_gate.py").read()
slice7 = open(f"{WS}/phcc-slice7/tools/phcc_gate.py").read()


def extract(text, start_marker, end_marker):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j]


SEP = "# ---------------------------------------------------------------------------\n"
m3_block = extract(slice6, SEP + "# Slice 6: machine-#3 conformance",
                   "\n\ndef main():")
m4_block = extract(slice7, SEP + "# Slice 7: machine-#4 conformance",
                   "\n\ndef main():")

# machine-#3 register relocation: Sec 15 -> Sec 17 (build register keeps
# Sec 15 in the merged lineage). Content of the register is unchanged;
# only the gate constant and its comment move.
assert "MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 15, 1)" in m3_block
m3_block = m3_block.replace(
    "MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 15, 1)",
    "MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 17, 1)")
assert "(Meta, Vol 2, Book 10, Sec 15), whose SHA-256 binding" in m3_block
m3_block = m3_block.replace(
    "(Meta, Vol 2, Book 10, Sec 15), whose SHA-256 binding",
    "(Meta, Vol 2, Book 10, Sec 17), whose SHA-256 binding")
m3_block = m3_block.replace(
    "# unnecessary).",
    "# unnecessary).\n#\n# GRAND MERGE (gate v8): in the Slice 6 lineage this register sat\n"
    "# at Meta Sec 15, which the builds lineage had independently\n"
    "# claimed for its build register. Content wins by seniority of\n"
    "# the register pair (addendum Sec 14 + build register Sec 15);\n"
    "# the machine-#3 register moved to Sec 17, byte-identical, and\n"
    "# this constant is the only trace of the move.")

g = builds

# --- docstring -------------------------------------------------------------
new_doc = '''#!/usr/bin/env python3
"""phcc_gate.py — the phcc trace gate, GRAND MERGE: REPORT-ONLY.

Gate v8.0.0 composes the three sibling gate copies that grew on the
canonical base (646144c7...) into one gate for the merged lineage:

  chassis: coverage / tiers / proof claims / Design staleness /
    machine-#1 (Slice 4, preprocessor) / machine-#2 (Slice 5,
    value stack) — the common core, byte-compatible output with
    every prior gate since v5.0.0;
  machine-#3 (Slice 6, linker symbol resolution): section code from
    gate v6.0.0 (slice6); its machine register sits at Meta Sec 17
    in the merged lineage (Sec 15 in the Slice 6 lineage — the
    builds lineage's build register keeps Sec 15; see the note at
    MACHINE3_REGISTER_COORD);
  machine-#4 (Slice 7, register allocation): section code from
    gate v7.0.0 (slice7), verbatim; register at Meta Sec 16;
  generated assembly (builds pass): section code from gate v6.0.1
    (builds; canonical binary scrolls), verbatim; build register
    at Meta Sec 15, listings hash-bound to Source scroll, compiler
    commit, and the Library-10000 region object.

Sections run in slice order: coverage, tiers, proof claims, Design,
machine #1, #2, #3, #4, assembly. The verdict is written at Meta,
Volume 2, Book 10, Ch 1, Sec 19 — the merged lineage's own section,
continuing the Meta sequence (Secs 14-18: builds addendum, build
register, Slice 7 machine register, Slice 6 machine register,
merged register). Historical verdicts (Secs 4, 5, 7, 9, 12) stay
excluded from coverage, as in every prior gate. D2 is closed as
unnecessary (Will, 2026-11-07) — the gate stays report-only;
conformance is reported, it never blocks. D4 likewise: the
external gate is the architecture.

Determinism: the verdict content contains no timestamps and no
run-specific data, and its checked-scroll hash list EXCLUDES the
verdict scroll's own coordinate — so re-running the gate on a phext
that already carries this verdict reproduces the identical verdict
content and hash. Tool version is a constant, below.

Usage:
  phcc_gate.py PHEXT [--verdict-out PHEXT] [--quiet]
Prints the tables to stdout; with --verdict-out, also prints the
verdict scroll's SHA-256.
"""'''
i = g.index('"""', g.index('"""') + 3) + 3
g = new_doc + g[i:]

# --- version / verdict coordinate / exclusion set --------------------------
old = '''# Gate 6.0.1 (phcc-builds-aligned, 2026-11-07): the assembly section's
# region-object check now decodes CANONICAL binary scrolls
# ('phext-binary:1:base64' + unwrapped RFC 4648 base64, libphext-rs
# 0.5 / PR #9) and verifies the SHA-256 of the DECODED raw bytes
# against the listing's object-sha256 binding. Gate 6.0.0 instead
# compared the 'raw-sha256' field of the project-local
# '# phcc-binary 1' in-scroll header. The legacy format is still
# accepted as a fallback (its body is decoded and hashed the same
# way — a strictly stronger check than trusting its header), so
# pre-alignment phexts gate with identical results. NOTHING else in
# the gate changed: every other section's output is byte-identical
# to 6.0.0.
TOOL_VERSION = "phcc_gate.py 6.0.1 (builds; canonical binary scrolls)"
VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 16, 1)  # Builds verdict: Meta, Vol 2, Book 10, Sec 16
SLICE5_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 12, 1)  # Slice 5 verdict (never evidence)
SLICE4_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 9, 1)  # Slice 4 verdict (never evidence)
SLICE3_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 7, 1)  # Slice 3 verdict (never evidence)
SLICE2_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 5, 1)  # Slice 2 verdict (never evidence)
SLICE1_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 4, 1)  # Slice 1 verdict (never evidence)
ALL_VERDICT_COORDS = (VERDICT_COORD, SLICE5_VERDICT_COORD, SLICE4_VERDICT_COORD,
                      SLICE3_VERDICT_COORD, SLICE2_VERDICT_COORD,
                      SLICE1_VERDICT_COORD)'''
new = '''# Gate v8.0.0 (grand merge, 2026-11-07): composed from gate v6.0.0
# (slice6), v7.0.0 (slice7) and v6.0.1 (builds) — see the module
# docstring. The assembly section keeps the v6.0.1 canonical-binary
# decode ('phext-binary:1:base64' + unwrapped RFC 4648 base64,
# libphext-rs 0.5 / PR #9; legacy '# phcc-binary 1' scrolls still
# accepted as a fallback and hashed from their decoded bytes).
# The verdict exclusion set names exactly the verdict scrolls the
# merged lineage carries: the historical Slice 1-5 verdicts plus
# this gate's own. The sibling verdicts (slice6 Sec 14, builds
# Sec 16, slice7 Sec 17) were NOT carried into the merged file —
# those sections hold content here (addendum, machine-#4 register,
# machine-#3 register) and must count as the content they are.
TOOL_VERSION = "phcc_gate.py 8.0.0 (grand merge: slice6 + slice7 + builds)"
VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 19, 1)  # Grand-merge verdict: Meta, Vol 2, Book 10, Sec 19
SLICE5_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 12, 1)  # Slice 5 verdict (never evidence)
SLICE4_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 9, 1)  # Slice 4 verdict (never evidence)
SLICE3_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 7, 1)  # Slice 3 verdict (never evidence)
SLICE2_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 5, 1)  # Slice 2 verdict (never evidence)
SLICE1_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 4, 1)  # Slice 1 verdict (never evidence)
ALL_VERDICT_COORDS = (VERDICT_COORD, SLICE5_VERDICT_COORD, SLICE4_VERDICT_COORD,
                      SLICE3_VERDICT_COORD, SLICE2_VERDICT_COORD,
                      SLICE1_VERDICT_COORD)'''
assert old in g
g = g.replace(old, new)

# --- tables_text plumbing ---------------------------------------------------
old = """def tables_text(per_book, artifacts, gaps, t1_eligible,
                receipted=None, proof_notes=None, design=None,
                machine=None, machine2=None, assembly=None):"""
new = """def tables_text(per_book, artifacts, gaps, t1_eligible,
                receipted=None, proof_notes=None, design=None,
                machine=None, machine2=None, machine3=None,
                machine4=None, assembly=None):"""
assert old in g
g = g.replace(old, new)

old = """    if machine2:
        lines.append("")
        lines.extend(machine2)
    if assembly:"""
new = """    if machine2:
        lines.append("")
        lines.extend(machine2)
    if machine3:
        lines.append("")
        lines.extend(machine3)
    if machine4:
        lines.append("")
        lines.extend(machine4)
    if assembly:"""
assert old in g
g = g.replace(old, new)

# --- verdict_text plumbing --------------------------------------------------
old = """def verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                 receipted=None, proof_notes=None, design=None,
                 machine=None, machine2=None, assembly=None):
    lines = []
    lines.append("# phcc gate verdict - Builds")"""
new = """def verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                 receipted=None, proof_notes=None, design=None,
                 machine=None, machine2=None, machine3=None,
                 machine4=None, assembly=None):
    lines = []
    lines.append("# phcc gate verdict - Grand merge (Slice 6 + Slice 7 + builds)")"""
assert old in g
g = g.replace(old, new)

old = """    lines.append(tables_text(per_book, artifacts, gaps, t1_eligible,
                             receipted, proof_notes, design, machine, machine2,
                             assembly))"""
new = """    lines.append(tables_text(per_book, artifacts, gaps, t1_eligible,
                             receipted, proof_notes, design, machine, machine2,
                             machine3, machine4, assembly))"""
assert old in g
g = g.replace(old, new)

# --- splice machine-#3 and machine-#4 sections before the assembly section --
anchor = SEP + "# Builds pass: generated-assembly staleness"
assert anchor in g
g = g.replace(anchor, m3_block + "\n\n" + m4_block + "\n\n" + anchor)

# --- main() plumbing ---------------------------------------------------------
old = """    machine = machine_section(scrolls, a.phext)
    machine2 = machine2_section(scrolls, a.phext)
    assembly = assembly_section(scrolls)"""
new = """    machine = machine_section(scrolls, a.phext)
    machine2 = machine2_section(scrolls, a.phext)
    machine3 = machine3_section(scrolls, a.phext)
    machine4 = machine4_section(scrolls, a.phext)
    assembly = assembly_section(scrolls)"""
assert old in g
g = g.replace(old, new)

old = """        print(tables_text(per_book, artifacts, gaps, t1_eligible,
                          receipted, proof_notes, design, machine, machine2,
                          assembly))"""
new = """        print(tables_text(per_book, artifacts, gaps, t1_eligible,
                          receipted, proof_notes, design, machine, machine2,
                          machine3, machine4, assembly))"""
assert old in g
g = g.replace(old, new)

old = """        verdict = verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                               receipted, proof_notes, design, machine, machine2,
                               assembly)"""
new = """        verdict = verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                               receipted, proof_notes, design, machine, machine2,
                               machine3, machine4, assembly)"""
assert old in g
g = g.replace(old, new)

compile(g, "phcc_gate.py", "exec")
out = f"{WS}/phcc-final/tools/phcc_gate.py"
with open(out, "w") as f:
    f.write(g)
print(f"composed {out}: {g.count(chr(10))+1} lines")
for token in ("8.0.0 (grand merge", "machine3_section", "machine4_section",
              "assembly_section", "1, 17, 1)", "1, 19, 1)"):
    print(f"  {token!r}: {g.count(token)} occurrence(s)")
