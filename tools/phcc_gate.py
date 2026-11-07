#!/usr/bin/env python3
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

Gate v8.1.0 (F5 refresh, 2026-11-07) adds ONE section to v8.0.0:
the conformance section (conformance programme design §6),
checking the Tests Book 11 placement (probe hashes against the
slice-1 manifest, divergence classifications complete, class-(a)
cross-references, the MSVC manual-attestation field). Every prior
section's logic is byte-identical to v8.0.0 (splice proof in the
refresh workdir). The refresh re-bound the tccpp.c/tccgen.c
Source scrolls to the F5 fix (commit e399b212), so the machine
sections' live checkers and register bindings re-verify against
the new source; the verdict moves to Meta Sec 20, and the
grand-merge verdict (Sec 19) joins the historical exclusion set.

Determinism: the verdict content contains no timestamps and no
run-specific data, and its checked-scroll hash list EXCLUDES the
verdict scroll's own coordinate — so re-running the gate on a phext
that already carries this verdict reproduces the identical verdict
content and hash. Tool version is a constant, below.

Usage:
  phcc_gate.py PHEXT [--verdict-out PHEXT] [--quiet]
Prints the tables to stdout; with --verdict-out, also prints the
verdict scroll's SHA-256.
"""
import argparse
import base64
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

# Gate v8.0.0 (grand merge, 2026-11-07): composed from gate v6.0.0
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
# Gate v8.1.0: the grand-merge verdict (Sec 19) joins the set as
# history; this gate's verdict sits at Sec 20.
TOOL_VERSION = "phcc_gate.py 8.1.0 (F5 refresh: source re-bind + conformance section)"
VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 20, 1)  # F5-refresh verdict: Meta, Vol 2, Book 10, Sec 20
GRAND_MERGE_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 19, 1)  # Gate v8.0.0 verdict (never evidence)
SLICE5_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 12, 1)  # Slice 5 verdict (never evidence)
SLICE4_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 9, 1)  # Slice 4 verdict (never evidence)
SLICE3_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 7, 1)  # Slice 3 verdict (never evidence)
SLICE2_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 5, 1)  # Slice 2 verdict (never evidence)
SLICE1_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 4, 1)  # Slice 1 verdict (never evidence)
ALL_VERDICT_COORDS = (VERDICT_COORD, GRAND_MERGE_VERDICT_COORD,
                      SLICE5_VERDICT_COORD, SLICE4_VERDICT_COORD,
                      SLICE3_VERDICT_COORD, SLICE2_VERDICT_COORD,
                      SLICE1_VERDICT_COORD)
PHASE_NAMES = {1: "Meta", 2: "Requirements", 3: "Design", 4: "Source",
               5: "Tests", 6: "Regressions", 7: "Docs", 8: "Whitepapers",
               9: "Training", 10: "Proofs"}
PHASES = [1, 2, 3, 4, 10, 5, 6, 7, 8, 9]  # display order: Proofs beside Source/Tests


def analyse(scrolls):
    manifest = phext_io.parse_manifest(scrolls)
    artifacts = sorted(manifest.items())  # (path, coord), coord: source phase
    # index of populated (collection, volume, book, chapter, section).
    # A phase counts as populated only by a NON-EMPTY scroll: the phext
    # encoding itself creates zero-byte navigation slots at
    # (Collection 1, Vol 2, Book B, Ch 1, Sec 1) for every Book B, and
    # those are not Meta content. Exception: the Source phase is
    # checked by slot existence, because a zero-byte file (e.g. an
    # empty .expect) is a real placed artifact with an empty scroll.
    populated = defaultdict(set)  # (book, chapter, section) -> set(collection) [vol 2]
    for coord, content in scrolls.items():
        if coord in ALL_VERDICT_COORDS:
            continue  # gate verdicts are never evidence in their
            # own coverage computation (it sits at a Book 10 artifact's
            # address and would otherwise inflate Meta coverage by one
            # artifact on every re-run, breaking verdict reproducibility)
        if coord[4] == 2 and (len(content) > 0 or coord[3] == 4):  # volume 2
            populated[(coord[5], coord[6], coord[7])].add(coord[3])
    per_book = {}
    for book in range(1, 11):
        arts = [(p, c) for p, c in artifacts if c[5] == book]
        cov = {}
        for phase in PHASES:
            n = sum(1 for _, c in arts
                    if phase in populated.get((c[5], c[6], c[7]), set()))
            cov[phase] = (n, len(arts))
        tests_ok = [p for p, c in arts
                    if 5 in populated.get((c[5], c[6], c[7]), set())]
        per_book[book] = {"total": len(arts), "cov": cov, "tests_ok": tests_ok}
    gaps = []
    for p, c in artifacts:
        if 5 not in populated.get((c[5], c[6], c[7]), set()):
            gaps.append((p, c))
    t1_eligible = sum(len(v["tests_ok"]) for v in per_book.values())
    return artifacts, per_book, gaps, t1_eligible, populated


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def tables_text(per_book, artifacts, gaps, t1_eligible,
                receipted=None, proof_notes=None, design=None,
                machine=None, machine2=None, machine3=None,
                machine4=None, assembly=None, conformance=None):
    receipted = receipted or {}
    proof_notes = proof_notes or {}
    design = design or {"checked": 0, "current": [], "stale": []}
    lines = []
    lines.append("per-Book phase coverage (Volume 2; % of Source artifacts "
                 "with the phase populated at their 5D address):")
    hdr = f"{'Book':<5}" + "".join(f"{PHASE_NAMES[p]:>13}" for p in PHASES) + f"{'arts':>7}"
    lines.append(hdr)
    tot_cov = {p: 0 for p in PHASES}
    for book in range(1, 11):
        info = per_book[book]
        row = f"{book:<5}"
        for p in PHASES:
            n, d = info["cov"][p]
            tot_cov[p] += n
            row += f"{pct(n, d):>12.1f}%"
        row += f"{info['total']:>7}"
        lines.append(row)
    row = f"{'ALL':<5}"
    for p in PHASES:
        row += f"{pct(tot_cov[p], len(artifacts)):>12.1f}%"
    row += f"{len(artifacts):>7}"
    lines.append(row)
    lines.append("Collection 10 (Proofs): LIVE (D1 ruled YES, Will 2026-11-07); "
                 f"{tot_cov[10]} of {len(artifacts)} Source artifacts have Proofs scrolls")
    lines.append("Population rule: a phase is populated by a non-empty "
                 "scroll at the artifact's address (Source counts by slot "
                 "existence, so zero-byte files still count as placed)")
    lines.append("")
    lines.append("tier distribution:")
    lines.append(f"  T1-eligible (no receipt yet): {t1_eligible}")
    lines.append(f"  T0: {len(artifacts) - t1_eligible - len(receipted)}")
    lines.append(f"  T1/T2/T3 (with receipts): {len(receipted)}")
    for src in sorted(receipted):
        lines.append(f"    T{receipted[src]}: {phext_io.fmt(src)}")
    if proof_notes:
        lines.append("proof claims (Proofs phase receipts):")
        for src in sorted(proof_notes):
            lines.append(f"  {phext_io.fmt(src)} — {proof_notes[src]}")
    lines.append("")
    lines.append("design views (Slice 3 staleness check, design §A.1; "
                 "report-only, flags never block):")
    lines.append(f"  generated Design Scroll-1 views checked: "
                 f"{design['checked']}")
    lines.append(f"  current (recorded Source/members hashes match): "
                 f"{len(design['current'])}")
    lines.append(f"  STALE: {len(design['stale'])}")
    for path, reason in design["stale"]:
        lines.append(f"    STALE\t{path}\t{reason}")
    if machine:
        lines.append("")
        lines.extend(machine)
    if machine2:
        lines.append("")
        lines.extend(machine2)
    if machine3:
        lines.append("")
        lines.extend(machine3)
    if machine4:
        lines.append("")
        lines.extend(machine4)
    if assembly:
        lines.append("")
        lines.extend(assembly)
    if conformance:
        lines.append("")
        lines.extend(conformance)
    return "\n".join(lines)


def verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                 receipted=None, proof_notes=None, design=None,
                 machine=None, machine2=None, machine3=None,
                 machine4=None, assembly=None, conformance=None):
    lines = []
    lines.append("# phcc gate verdict - F5 refresh + conformance placement (gate v8.1.0)")
    lines.append(f"tool: {TOOL_VERSION}")
    lines.append("mode: REPORT-ONLY")
    lines.append("status: REPORT")
    lines.append("volume: 2")
    lines.append(f"artifacts-checked: {len(artifacts)}")
    lines.append("")
    lines.append(tables_text(per_book, artifacts, gaps, t1_eligible,
                             receipted, proof_notes, design, machine, machine2,
                             machine3, machine4, assembly, conformance))
    lines.append("")
    lines.append("per-artifact Tests-phase gaps (artifacts with no Tests "
                 "scroll at their 5D address):")
    for p, c in gaps:
        lines.append(f"gap\t{p}\t{phext_io.fmt(c)}")
    lines.append("")
    lines.append("checked scrolls (every scroll in the phext except this "
                 "verdict scroll): coordinate, sha256, size:")
    checked = [(c, s) for c, s in sorted(scrolls.items()) if c != VERDICT_COORD]
    lines.append(f"checked-scrolls-count: {len(checked)}")
    for c, s in checked:
        lines.append(f"scroll\t{phext_io.fmt(c)}\t{phext_io.sha256(s)}\t{len(s)}")
    return ("\n".join(lines) + "\n").encode()



# ---------------------------------------------------------------------------
# Slice 2: receipts-driven tiers (design B.2/B.5).
# A receipt lives in the Proofs phase (Collection 10) at the artifact's
# own 5D address: Scroll 1 = contracts, Scroll 2 = WP receipt,
# Scroll 4 = CBMC (bounded) receipt, Scroll 5 = differential receipt.
# T3 is granted ONLY when the WP receipt shows vc-undischarged == 0,
# carries no unproven-dependency note, and both hashes it binds to
# (Source scroll, contracts scroll) match the scrolls as they stand.
# A hash mismatch DEMOTES: the claim is stale, the tier falls back.

def _sha(b):
    return phext_io.sha256(b)

def _kv(text):
    out = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out

def parse_proof_claims(scrolls):
    """Return {source_coord: claim-dict} for artifacts with Proofs scrolls."""
    claims = {}
    for coord, content in scrolls.items():
        (li, sb, vb, C, V, B, Ch, Sec, S) = coord
        if C != 10 or S not in (2, 4):
            continue
        src = (li, sb, vb, 4, V, B, Ch, Sec, 1)
        contracts_coord = (li, sb, vb, 10, V, B, Ch, Sec, 1)
        text = content.decode("utf-8", "replace")
        kv = _kv(text)
        claim = claims.setdefault(src, {"wp": None, "cbmc": None})
        if S == 2:
            claim["wp"] = kv
            claim["wp_hash_ok"] = (
                kv.get("source-sha256") == _sha(scrolls.get(src, b""))
                and kv.get("contracts-sha256") == _sha(scrolls.get(contracts_coord, b"")))
        else:
            claim["cbmc"] = kv
            claim["cbmc_hash_ok"] = kv.get("source-sha256") == _sha(scrolls.get(src, b""))
    return claims

def tiers_from_receipts(claims):
    """{source_coord: (tier, note)} — the receipted tier overlay."""
    out = {}
    for src, claim in claims.items():
        wp, cbmc = claim.get("wp"), claim.get("cbmc")
        if wp is not None:
            und = wp.get("vc-undischarged")
            dep = wp.get("dependencies", "")
            if und == "0" and dep.startswith("none") and claim.get("wp_hash_ok"):
                out[src] = (3, "WP receipt: all VCs discharged, hashes current")
            elif not claim.get("wp_hash_ok"):
                out[src] = (None, "STALE: WP receipt hash mismatch — T3 claim demoted")
            else:
                out[src] = (None, "WP partial: %s/%s VCs discharged (undischarged %s; dependencies: %s) — T3 not granted"
                            % (wp.get("vc-discharged", "?"), wp.get("vc-generated", "?"), und, dep))
        if cbmc is not None:
            note = ("CBMC bounded: %s (bounds in receipt; hash %s)"
                    % (cbmc.get("status", "?"), "current" if claim.get("cbmc_hash_ok") else "STALE"))
            prev = out.get(src)
            out[src] = (prev[0] if prev else None,
                        ((prev[1] + " | ") if prev else "") + note)
    return out

# ---------------------------------------------------------------------------
# Slice 3: Design-view staleness (design §A.1).
# A generated Design view (Collection 3, Volume 2, Scroll 1 at an
# artifact's 5D address) records in its header the SHA-256 of the
# Vol 2 Source scroll it was generated from and, when the artifact
# has Vol 3 member structure, a digest over the Vol 3 segment
# scrolls it consumed. The gate recomputes both; a mismatch flags
# the view STALE in the verdict. D2 is closed as unnecessary (Will,
# 2026-11-07): the gate stays report-only — staleness is flagged,
# never blocking. Design scrolls without a source-sha256 header
# field (the §A.2 pipeline system view) are not generated artifact
# views and are skipped.

import hashlib
import re

_HDR_FIELD = re.compile(r"^(source-sha256|members-sha256|artifact): "
                        r"(\S+)$", re.M)


def _members_digest(scrolls, b, ch, sec):
    """Recompute the extractor's Vol 3 binding digest: SHA-256 over
    the raw bytes of the file's Vol 3 segment scrolls, in the order
    the Vol 3 index table lists them. None if no index exists."""
    idx = scrolls.get((1, 1, 1, 4, 3, b, ch, sec, 1))
    if not idx:
        return None
    digest = hashlib.sha256()
    n = 0
    for line in idx.decode("utf-8", "replace").splitlines():
        p = line.split("\t")
        if len(p) == 6 and p[0].isdigit():
            seg = scrolls.get((1, 1, 1, 4, 3, b, ch, sec, int(p[0])))
            if seg is None:
                return None
            digest.update(seg)
            n += 1
    return digest.hexdigest() if n else None


def parse_design_views(scrolls):
    """Return {'checked': n, 'current': [path], 'stale': [(path,
    reason)]} over generated Design Scroll-1 views."""
    manifest = phext_io.parse_manifest(scrolls)
    by_addr = {(c[5], c[6], c[7]): p for p, c in manifest.items()}
    out = {"checked": 0, "current": [], "stale": []}
    for coord, content in sorted(scrolls.items()):
        if coord[3] != 3 or coord[4] != 2 or coord[8] != 1:
            continue  # Design phase, Volume 2, Scroll 1 only
        if not content.startswith(b"GENERATED"):
            continue
        head = content[:1500].decode("utf-8", "replace")
        fields = dict(_HDR_FIELD.findall(head))
        if "source-sha256" not in fields:
            continue  # system view (pipeline), not an artifact view
        addr = (coord[5], coord[6], coord[7])
        path = by_addr.get(addr, phext_io.fmt(coord))
        out["checked"] += 1
        reasons = []
        src_coord = (coord[0], coord[1], coord[2], 4, 2,
                     coord[5], coord[6], coord[7], 1)
        cur_src = scrolls.get(src_coord)
        if cur_src is None or _sha(cur_src) != fields["source-sha256"]:
            reasons.append("source-sha256 mismatch (Source scroll "
                           "changed since generation)")
        rec_members = fields.get("members-sha256", "none")
        if rec_members != "none":
            cur_members = _members_digest(scrolls, coord[5], coord[6],
                                          coord[7])
            if cur_members is None:
                reasons.append("members binding broken (Vol 3 index "
                               "or segments missing)")
            elif cur_members != rec_members:
                reasons.append("members-sha256 mismatch (Vol 3 member "
                               "structure changed since generation)")
        if reasons:
            out["stale"].append((path, "; ".join(reasons)))
        else:
            out["current"].append(path)
    out["stale"].sort()
    out["current"].sort()
    return out


# ---------------------------------------------------------------------------
# Slice 4: machine conformance (design §A.3). The static result is
# recomputed live by running tools/check_machine.py on the gate's
# input phext. The dynamic results are read from the Slice 4
# machine register (Meta, Vol 2, Book 10, Sec 10), whose SHA-256
# binding to the machine scroll and the tccpp.c Source scroll is
# re-verified here: a mismatch reports the recorded results STALE.
# Report-only throughout (D2 closed as unnecessary).

MACHINE_COORD = (1, 1, 1, 3, 2, 2, 1, 1, 2)       # Design, tccpp.c, scroll 2
MACHINE_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 10, 1)
TCCPP_SRC_COORD = (1, 1, 1, 4, 2, 2, 1, 1, 1)


def machine_section(scrolls, phext_path):
    lines = ["machine conformance (Slice 4, design §A.3; report-only, "
             "flags never block):"]
    machine = scrolls.get(MACHINE_COORD)
    if not machine:
        lines.append("  machine scroll: absent at "
                     + phext_io.fmt(MACHINE_COORD))
        return lines
    lines.append(f"  machine scroll: {phext_io.fmt(MACHINE_COORD)} "
                 f"(sha256 {phext_io.sha256(machine)[:16]}...)")
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "check_machine.py")
    try:
        r = subprocess.run([sys.executable, checker, phext_path],
                           capture_output=True, text=True, timeout=600)
        out = [l for l in r.stdout.splitlines() if l.strip()]
        counts = next((l for l in out if l.startswith("states:")), "")
        resolved = next((l for l in out if "resolved against" in l), "")
        verdict = next((l for l in out
                        if l.startswith("STATIC CONFORMANCE")), "")
        lines.append(f"  static (recomputed live by "
                     f"tools/check_machine.py): {verdict}")
        lines.append(f"    {counts}; {resolved}")
        for l in out:
            if l.startswith("  VIOLATION:"):
                lines.append("   " + l)
    except Exception as e:  # checker unavailable: report, never block
        lines.append(f"  static: checker could not run ({e})")
    regressions = sum(
        1 for c, s in scrolls.items()
        if c[:8] == (1, 1, 1, 6, 2, 2, 1, 1) and s)
    reg_text = scrolls.get(MACHINE_REGISTER_COORD, b"").decode(
        "utf-8", "replace")
    if reg_text:
        kv = _kv(reg_text)
        bound = (kv.get("machine-sha256") == phext_io.sha256(machine)
                 and kv.get("source-sha256")
                 == phext_io.sha256(scrolls.get(TCCPP_SRC_COORD, b"")))
        lines.append(f"  dynamic (recorded in machine register "
                     f"{phext_io.fmt(MACHINE_REGISTER_COORD)}):")
        lines.append(f"    authored trace tests: "
                     f"{kv.get('dynamic-authored', '?')}")
        lines.append(f"    tests/pp corpus: "
                     f"{kv.get('dynamic-corpus', '?')}")
        lines.append(f"    tcc: {kv.get('tcc-version', '?')}")
        lines.append(f"    exit test: {kv.get('exit-test', '?')}")
        lines.append("  binding: " + (
            "CURRENT (register machine-sha256 and source-sha256 match "
            "the scrolls as they stand)" if bound else
            "STALE (register machine-sha256 or source-sha256 does not "
            "match the scrolls as they stand; recorded dynamic results "
            "are not current)"))
    else:
        lines.append("  dynamic: no machine register recorded")
    lines.append(f"  regressions filed at 1.1.1/6.2.2/1.1.N: "
                 f"{regressions}")
    return lines


# ---------------------------------------------------------------------------
# Slice 5: machine-#2 conformance (design §A.3). Same discipline as
# the Slice 4 section: the static result is recomputed live by
# running tools/check_vstack.py on the gate's input phext; the
# dynamic results are read from the Slice 5 machine register
# (Meta, Vol 2, Book 10, Sec 13), whose SHA-256 binding to the
# machine scroll and the tccgen.c Source scroll is re-verified
# here. Report-only throughout (D2 closed as unnecessary).

MACHINE2_COORD = (1, 1, 1, 3, 2, 3, 1, 1, 2)      # Design, tccgen.c, scroll 2
MACHINE2_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 13, 1)
TCCGEN_SRC_COORD = (1, 1, 1, 4, 2, 3, 1, 1, 1)


def machine2_section(scrolls, phext_path):
    lines = ["machine conformance #2 — value stack (Slice 5, design "
             "§A.3; report-only, flags never block):"]
    machine = scrolls.get(MACHINE2_COORD)
    if not machine:
        lines.append("  machine scroll: absent at "
                     + phext_io.fmt(MACHINE2_COORD))
        return lines
    lines.append(f"  machine scroll: {phext_io.fmt(MACHINE2_COORD)} "
                 f"(sha256 {phext_io.sha256(machine)[:16]}...)")
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "check_vstack.py")
    try:
        r = subprocess.run([sys.executable, checker, phext_path],
                           capture_output=True, text=True, timeout=600)
        out = [l for l in r.stdout.splitlines() if l.strip()]
        counts = next((l for l in out if l.startswith("states:")), "")
        resolved = next((l for l in out if "resolved against" in l), "")
        verdict = next((l for l in out
                        if l.startswith("STATIC CONFORMANCE")), "")
        lines.append(f"  static (recomputed live by "
                     f"tools/check_vstack.py): {verdict}")
        lines.append(f"    {counts}; {resolved}")
        for l in out:
            if l.startswith("  VIOLATION:"):
                lines.append("   " + l)
    except Exception as e:  # checker unavailable: report, never block
        lines.append(f"  static: checker could not run ({e})")
    regressions = sum(
        1 for c, s in scrolls.items()
        if c[:8] == (1, 1, 1, 6, 2, 3, 1, 1) and s)
    reg_text = scrolls.get(MACHINE2_REGISTER_COORD, b"").decode(
        "utf-8", "replace")
    if reg_text:
        kv = _kv(reg_text)
        bound = (kv.get("machine-sha256") == phext_io.sha256(machine)
                 and kv.get("source-sha256")
                 == phext_io.sha256(scrolls.get(TCCGEN_SRC_COORD, b"")))
        lines.append(f"  dynamic (recorded in machine register "
                     f"{phext_io.fmt(MACHINE2_REGISTER_COORD)}):")
        lines.append(f"    authored trace tests: "
                     f"{kv.get('dynamic-authored', '?')}")
        lines.append(f"    tests2 corpus: "
                     f"{kv.get('dynamic-corpus', '?')}")
        lines.append(f"    tcc: {kv.get('tcc-version', '?')}")
        lines.append(f"    exit test: {kv.get('exit-test', '?')}")
        lines.append("  binding: " + (
            "CURRENT (register machine-sha256 and source-sha256 match "
            "the scrolls as they stand)" if bound else
            "STALE (register machine-sha256 or source-sha256 does not "
            "match the scrolls as they stand; recorded dynamic results "
            "are not current)"))
    else:
        lines.append("  dynamic: no machine register recorded")
    lines.append(f"  regressions filed at 1.1.1/6.2.3/1.1.N: "
                 f"{regressions}")
    return lines


# ---------------------------------------------------------------------------
# Slice 6: machine-#3 conformance (design §A.3). Same discipline
# as the Slice 4/5 sections: the static result is recomputed
# live by running tools/check_linker.py on the gate's input
# phext; the dynamic results are read from the Slice 6 machine
# register (Meta, Vol 2, Book 10, Sec 17), whose SHA-256 binding
# to the machine scroll and the tccelf.c Source scroll is
# re-verified here. Report-only throughout (D2 closed as
# unnecessary).
#
# GRAND MERGE (gate v8): in the Slice 6 lineage this register sat
# at Meta Sec 15, which the builds lineage had independently
# claimed for its build register. Content wins by seniority of
# the register pair (addendum Sec 14 + build register Sec 15);
# the machine-#3 register moved to Sec 17, byte-identical, and
# this constant is the only trace of the move.

MACHINE3_COORD = (1, 1, 1, 3, 2, 5, 1, 2, 2)      # Design, tccelf.c, scroll 2
MACHINE3_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 17, 1)
TCCELF_SRC_COORD = (1, 1, 1, 4, 2, 5, 1, 2, 1)


def machine3_section(scrolls, phext_path):
    lines = ["machine conformance #3 — linker symbol resolution "
             "(Slice 6, design §A.3; report-only, flags never "
             "block):"]
    machine = scrolls.get(MACHINE3_COORD)
    if not machine:
        lines.append("  machine scroll: absent at "
                     + phext_io.fmt(MACHINE3_COORD))
        return lines
    lines.append(f"  machine scroll: {phext_io.fmt(MACHINE3_COORD)} "
                 f"(sha256 {phext_io.sha256(machine)[:16]}...)")
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "check_linker.py")
    try:
        r = subprocess.run([sys.executable, checker, phext_path],
                           capture_output=True, text=True, timeout=600)
        out = [l for l in r.stdout.splitlines() if l.strip()]
        counts = next((l for l in out if l.startswith("states:")), "")
        resolved = next((l for l in out if "resolved against" in l), "")
        verdict = next((l for l in out
                        if l.startswith("STATIC CONFORMANCE")), "")
        lines.append(f"  static (recomputed live by "
                     f"tools/check_linker.py): {verdict}")
        lines.append(f"    {counts}; {resolved}")
        for l in out:
            if l.startswith("  VIOLATION:"):
                lines.append("   " + l)
    except Exception as e:  # checker unavailable: report, never block
        lines.append(f"  static: checker could not run ({e})")
    regressions = sum(
        1 for c, s in scrolls.items()
        if c[:8] == (1, 1, 1, 6, 2, 5, 1, 2) and s)
    reg_text = scrolls.get(MACHINE3_REGISTER_COORD, b"").decode(
        "utf-8", "replace")
    if reg_text:
        kv = _kv(reg_text)
        bound = (kv.get("machine-sha256") == phext_io.sha256(machine)
                 and kv.get("source-sha256")
                 == phext_io.sha256(scrolls.get(TCCELF_SRC_COORD, b"")))
        lines.append(f"  dynamic (recorded in machine register "
                     f"{phext_io.fmt(MACHINE3_REGISTER_COORD)}):")
        lines.append(f"    authored trace tests: "
                     f"{kv.get('dynamic-authored', '?')}")
        lines.append(f"    tests2 corpus: "
                     f"{kv.get('dynamic-corpus', '?')}")
        lines.append(f"    tcc: {kv.get('tcc-version', '?')}")
        lines.append(f"    exit test: {kv.get('exit-test', '?')}")
        lines.append("  binding: " + (
            "CURRENT (register machine-sha256 and source-sha256 match "
            "the scrolls as they stand)" if bound else
            "STALE (register machine-sha256 or source-sha256 does not "
            "match the scrolls as they stand; recorded dynamic results "
            "are not current)"))
    else:
        lines.append("  dynamic: no machine register recorded")
    lines.append(f"  regressions filed at 1.1.1/6.2.5/1.2.N: "
                 f"{regressions}")
    return lines


# ---------------------------------------------------------------------------
# Slice 7: machine-#4 conformance (design §A.3). Same discipline:
# the static result is recomputed live by running
# tools/check_regalloc.py on the gate's input phext (it checks
# BOTH instances); the dynamic results are read from the Slice 7
# machine register (Meta, Vol 2, Book 10, Sec 16), whose SHA-256
# binding to BOTH machine scrolls and to all THREE bounded Source
# scrolls (tccgen.c core, x86_64-gen.c, arm64-gen.c) is
# re-verified here. Report-only throughout.

MACHINE4_X64_COORD = (1, 1, 1, 3, 2, 6, 1, 1, 2)   # Design, x86_64-gen.c, scroll 2
MACHINE4_ARM64_COORD = (1, 1, 1, 3, 2, 6, 4, 1, 2)  # Design, arm64-gen.c, scroll 2
MACHINE4_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 16, 1)
X64_SRC_COORD = (1, 1, 1, 4, 2, 6, 1, 1, 1)
ARM64_SRC_COORD = (1, 1, 1, 4, 2, 6, 4, 1, 1)


def machine4_section(scrolls, phext_path):
    lines = ["machine conformance #4 — register allocation "
             "(Slice 7, design §A.3; report-only, flags never "
             "block):"]
    x64 = scrolls.get(MACHINE4_X64_COORD)
    arm = scrolls.get(MACHINE4_ARM64_COORD)
    if not x64 and not arm:
        lines.append("  machine scrolls: absent at "
                     + phext_io.fmt(MACHINE4_X64_COORD) + " and "
                     + phext_io.fmt(MACHINE4_ARM64_COORD))
        return lines
    for label, coord, m in (("x86_64", MACHINE4_X64_COORD, x64),
                            ("arm64", MACHINE4_ARM64_COORD, arm)):
        if m:
            lines.append(f"  machine scroll ({label}): "
                         f"{phext_io.fmt(coord)} "
                         f"(sha256 {phext_io.sha256(m)[:16]}...)")
        else:
            lines.append(f"  machine scroll ({label}): absent at "
                         f"{phext_io.fmt(coord)}")
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "check_regalloc.py")
    try:
        r = subprocess.run([sys.executable, checker, phext_path],
                           capture_output=True, text=True, timeout=600)
        out = [l for l in r.stdout.splitlines() if l.strip()]
        counts = [l for l in out if l.startswith("states:")]
        resolved = [l for l in out if "resolved against" in l]
        verdict = next((l for l in out
                        if l.startswith("STATIC CONFORMANCE")), "")
        lines.append(f"  static (recomputed live by "
                     f"tools/check_regalloc.py): {verdict}")
        for c_line, r_line in zip(counts, resolved):
            lines.append(f"    {c_line}; {r_line}")
        for l in out:
            if l.startswith("  VIOLATION:"):
                lines.append("   " + l)
    except Exception as e:  # checker unavailable: report, never block
        lines.append(f"  static: checker could not run ({e})")
    regressions = sum(
        1 for c, s in scrolls.items()
        if c[:8] == (1, 1, 1, 6, 2, 3, 1, 1) and c[8] >= 6 and s)
    reg_text = scrolls.get(MACHINE4_REGISTER_COORD, b"").decode(
        "utf-8", "replace")
    if reg_text:
        kv = _kv(reg_text)
        bound = (
            kv.get("machine-x64-sha256")
            == phext_io.sha256(scrolls.get(MACHINE4_X64_COORD, b""))
            and kv.get("machine-arm64-sha256")
            == phext_io.sha256(scrolls.get(MACHINE4_ARM64_COORD, b""))
            and kv.get("source-tccgen-sha256")
            == phext_io.sha256(scrolls.get(TCCGEN_SRC_COORD, b""))
            and kv.get("source-x64-sha256")
            == phext_io.sha256(scrolls.get(X64_SRC_COORD, b""))
            and kv.get("source-arm64-sha256")
            == phext_io.sha256(scrolls.get(ARM64_SRC_COORD, b"")))
        lines.append(f"  dynamic (recorded in machine register "
                     f"{phext_io.fmt(MACHINE4_REGISTER_COORD)}):")
        lines.append(f"    authored trace tests: "
                     f"{kv.get('dynamic-authored', '?')}")
        lines.append(f"    tests2 corpus: "
                     f"{kv.get('dynamic-corpus', '?')}")
        lines.append(f"    tcc: {kv.get('tcc-version', '?')}")
        lines.append(f"    exit test: {kv.get('exit-test', '?')}")
        lines.append("  binding: " + (
            "CURRENT (register machine and source hashes match the "
            "scrolls as they stand)" if bound else
            "STALE (register machine or source hash does not match "
            "the scrolls as they stand; recorded dynamic results "
            "are not current)"))
    else:
        lines.append("  dynamic: no machine register recorded")
    lines.append(f"  regressions filed by Slice 7 at "
                 f"1.1.1/6.2.3/1.1.6-8: {regressions}")
    return lines


# ---------------------------------------------------------------------------
# Builds pass: generated-assembly staleness (Will's rulings, 2026-11-07).
# The build register (Meta, Vol 2, Book 10, Sec 15) names each generated
# assembly listing. A listing is a Design scroll whose header binds:
# the Source scroll's SHA-256, the compiler commit, the region object's
# raw SHA-256, and the listing body's own SHA-256. Recompute all of
# them: source or compiler moved -> STALE (report-only, per D2).
# The Library-10000 object itself is ephemeral: absent (wiped) is a
# state, not staleness.

BUILD_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 15, 1)
REGION_LIBRARY = 10000


def _kv_head(content):
    """(header dict, body bytes) split at the first blank line."""
    head, _sep, body = content.partition(b"\n\n")
    kv = {}
    for line in head.decode("utf-8", "replace").splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            kv[k.strip()] = v.strip()
    return kv, body


CANONICAL_BINARY_HEADER = b"phext-binary:1:base64"
LEGACY_BINARY_MAGIC = b"# phcc-binary 1"


def decode_binary_scroll(content):
    """Raw bytes of a binary scroll, or None if undecodable.

    Canonical (libphext-rs 0.5): header line 'phext-binary:1:base64',
    then unwrapped RFC 4648 base64. Legacy fallback (pre-alignment
    project format): '# phcc-binary 1' header, blank line, wrapped
    base64 — decoded and hashed by the caller exactly like the
    canonical form, never trusted via its header fields.
    """
    if content.startswith(CANONICAL_BINARY_HEADER + b"\n"):
        body = content[len(CANONICAL_BINARY_HEADER) + 1:]
        try:
            return base64.b64decode(body, validate=True)
        except Exception:
            return None
    if content.startswith(LEGACY_BINARY_MAGIC):
        _head, sep, body = content.partition(b"\n\n")
        if not sep:
            return None
        try:
            return base64.b64decode(b"".join(body.split()), validate=True)
        except Exception:
            return None
    return None


def assembly_section(scrolls):
    lines = []
    lines.append("generated assembly (builds pass; report-only, flags "
                 "never block):")
    region = [c for c in scrolls if c[0] == REGION_LIBRARY]
    region_bytes = sum(len(scrolls[c]) for c in region)
    lines.append(f"  build region (Library 10000): {len(region)} scrolls, "
                 f"{region_bytes} bytes (wipeable; binaries base64)")
    reg = scrolls.get(BUILD_REGISTER_COORD)
    if reg is None:
        lines.append("  no build register recorded (Meta Sec 15 absent) "
                     "\u2014 no generated assembly in this phext")
        return lines
    reg_kv, entries = {}, []
    for line in reg.decode("utf-8", "replace").splitlines():
        if line.startswith("assembly\t"):
            parts = line.split("\t")
            if len(parts) == 5:
                entries.append(parts[1:])
        elif ": " in line and not line.startswith("#"):
            k, v = line.split(": ", 1)
            reg_kv[k.strip()] = v.strip()
    lines.append(f"  build register: {phext_io.fmt(BUILD_REGISTER_COORD)} "
                 f"(compiler-commit {reg_kv.get('compiler-commit')}; "
                 f"host {reg_kv.get('build-host')}; "
                 f"built-at {reg_kv.get('built-at')})")
    current = stale = 0
    for coord_s, artifact, src_s, target in entries:
        coord = phext_io.parse_coord(coord_s)
        src_coord = phext_io.parse_coord(src_s)
        content = scrolls.get(coord)
        if content is None:
            lines.append(f"  STALE\t{coord_s}\t{artifact} {target}: "
                         f"assembly scroll absent")
            stale += 1
            continue
        kv, body = _kv_head(content)
        problems = []
        if kv.get("kind") != "assembly":
            problems.append("header kind is not 'assembly'")
        if kv.get("listing-sha256") != _sha(body):
            problems.append("listing body hash mismatch")
        src_bytes = scrolls.get(src_coord)
        if src_bytes is None or kv.get("source-sha256") != _sha(src_bytes):
            problems.append("source changed since listing was generated")
        if kv.get("compiler-commit") != reg_kv.get("compiler-commit"):
            problems.append("compiler changed since listing was generated")
        obj_note = "object not referenced"
        obj_coord = None
        if kv.get("object-region-scroll"):
            try:
                obj_coord = phext_io.parse_coord(kv["object-region-scroll"])
            except Exception:
                obj_coord = None
        if obj_coord is not None:
            obj_scroll = scrolls.get(obj_coord)
            if obj_scroll is None:
                obj_note = "object absent (region wiped)"
            else:
                raw = decode_binary_scroll(obj_scroll)
                if raw is None:
                    problems.append("region object is not a decodable "
                                    "binary scroll")
                elif _sha(raw) != kv.get("object-sha256"):
                    problems.append("region object hash does not match "
                                    "the listing's binding")
                else:
                    obj_note = "object present, binding current"
        if problems:
            stale += 1
            lines.append(f"  STALE\t{coord_s}\t{artifact} {target}: "
                         + "; ".join(problems))
        else:
            current += 1
            lines.append(f"  CURRENT\t{coord_s}\t{artifact} {target} "
                         f"({obj_note})")
    lines.append(f"  assembly listings checked: {len(entries)}; "
                 f"CURRENT {current}; STALE {stale}")
    return lines


# ---------------------------------------------------------------------------
# Conformance programme (design §6): report-only section, added in
# gate v8.1.0 — the only new section logic in this gate version.
# Checks the Tests Book 11 placement:
#   (i)   the manifest and results scrolls (Ch 9 Secs 3/4, verbatim)
#         hash to the slice-1 run bindings the receipt names, and
#         every placed probe scroll's bytes hash to the value the
#         manifest records for it (cross-checked against its
#         per-probe record);
#   (ii)  every currently-divergent probe record carries a
#         classification in {(a), (b), (c)} with evidence;
#   (iii) class-(a) records cross-reference a fix commit and a
#         Regression scroll that exists;
#   (iv)  the MSVC attestation field is well-formed: NOT ATTESTED,
#         or ATTESTED with designated signer + date + in-scope
#         manifest hash. The automated gate can only ever REPORT
#         this column (design §4); it never attests.
# Verdict vocabulary (design §6): CURRENT (no current divergences),
# STALE (a binding moved), DIVERGENT-CLASSIFIED (divergences exist,
# all classified — reported, not hidden), UNCLASSIFIED (a divergence
# without classification; refuses CURRENT). Report-only throughout.

CONF_RECEIPT_COORD = (1, 1, 1, 5, 2, 11, 9, 1, 1)
CONF_ATTEST_COORD = (1, 1, 1, 5, 2, 11, 9, 2, 1)
CONF_MANIFEST_COORD = (1, 1, 1, 5, 2, 11, 9, 3, 1)
CONF_RESULTS_COORD = (1, 1, 1, 5, 2, 11, 9, 4, 1)
CONF_MANIFEST_SHA256 = "c6eebb8a0146406373cb8bf9578455586148c696340f3b9b04c6dcbf63539cbb"
CONF_RESULTS_SHA256 = "b3c23baef07298f7b9dea32475533f4bc59666f8814595c112daa3463027cf97"


def conformance_section(scrolls):
    import json as _json
    lines = ["conformance (phcc conformance programme, design §6; "
             "report-only, flags never block):"]
    receipt_b = scrolls.get(CONF_RECEIPT_COORD)
    if receipt_b is None:
        lines.append("  run receipt: absent at "
                     + phext_io.fmt(CONF_RECEIPT_COORD)
                     + " — no conformance corpus placed")
        return lines
    receipt = receipt_b.decode("utf-8", "replace")
    rkv = _kv(receipt)
    problems = []

    # (i) run bindings: manifest / results scrolls vs the receipt
    man_b = scrolls.get(CONF_MANIFEST_COORD)
    res_b = scrolls.get(CONF_RESULTS_COORD)
    man_ok = (man_b is not None
              and phext_io.sha256(man_b) == CONF_MANIFEST_SHA256
              and rkv.get("manifest-sha256") == CONF_MANIFEST_SHA256)
    res_ok = (res_b is not None
              and phext_io.sha256(res_b) == CONF_RESULTS_SHA256
              and rkv.get("results-sha256") == CONF_RESULTS_SHA256)
    lines.append(f"  run receipt: {phext_io.fmt(CONF_RECEIPT_COORD)} "
                 f"(slice 1 run 2 + F5 verification re-run)")
    lines.append(f"  manifest: sha256 {CONF_MANIFEST_SHA256[:16]}... "
                 f"({'MATCH' if man_ok else 'MISMATCH'} — scroll "
                 f"{phext_io.fmt(CONF_MANIFEST_COORD)} verbatim, "
                 f"receipt-named value agrees)")
    lines.append(f"  results: sha256 {CONF_RESULTS_SHA256[:16]}... "
                 f"({'MATCH' if res_ok else 'MISMATCH'} — scroll "
                 f"{phext_io.fmt(CONF_RESULTS_COORD)} verbatim, "
                 f"receipt-named value agrees)")
    if not man_ok:
        problems.append("STALE: manifest scroll hash or receipt-named "
                        "manifest hash does not match the run binding")
    if not res_ok:
        problems.append("STALE: results scroll hash or receipt-named "
                        "results hash does not match the run binding")

    # per-probe records (Ch 9 Sec 1, Scrolls 2+)
    records = {}
    for coord, content in scrolls.items():
        if coord[:8] == (1, 1, 1, 5, 2, 11, 9, 1) and coord[8] >= 2 \
                and content.startswith(
                    b"# phcc conformance probe record"):
            kv = _kv(content.decode("utf-8", "replace"))
            if kv.get("probe"):
                records[kv["probe"]] = (content.decode("utf-8", "replace"),
                                        kv)
    placed = sum(1 for c, s in scrolls.items()
                 if c[:6] == (1, 1, 1, 5, 2, 11) and c[6] in (1, 2, 3)
                 and c[8] >= 2 and s)
    hash_ok = 0
    agree = resolved = divergent = unclassified = 0
    class_count = {"(a)": 0, "(b)": 0, "(c)": 0}
    if man_b is not None:
        try:
            manifest = _json.loads(man_b.decode("utf-8"))
        except Exception:
            manifest = None
            problems.append("STALE: manifest scroll is not parseable JSON")
    else:
        manifest = None
    if manifest is not None:
        for e in manifest:
            name = e["name"]
            rec = records.get(name)
            if rec is None:
                problems.append(f"missing per-probe record: {name}")
                continue
            text, kv = rec
            try:
                pcoord = phext_io.parse_coord(kv.get("coordinate", ""))
            except Exception:
                pcoord = None
            body = scrolls.get(pcoord) if pcoord else None
            if body is not None and phext_io.sha256(body) == e["sha256"] \
                    and kv.get("probe-sha256") == e["sha256"]:
                hash_ok += 1
            else:
                problems.append(f"probe hash mismatch: {name}")
            cur = kv.get("current", "")
            if cur.startswith("agree (divergence resolved"):
                agree += 1
                resolved += 1
            elif cur == "agree":
                agree += 1
            elif cur == "divergent-classified":
                cls = kv.get("classification", "")
                head = cls[:3]
                if head in class_count and "evidence:" in text:
                    class_count[head] += 1
                    divergent += 1
                else:
                    unclassified += 1
                    problems.append(
                        f"UNCLASSIFIED divergence: {name} "
                        f"(classification {cls!r})")
            else:
                unclassified += 1
                problems.append(f"UNCLASSIFIED: record for {name} has "
                                f"no readable current status")
            # (iii) class-(a) cross-references (open or resolved)
            if kv.get("classification", "").startswith("(a)"):
                if "fix:" not in text:
                    problems.append(f"class-(a) record lacks a fix "
                                    f"cross-reference: {name}")
                m = re.search(r"Regressions (\d+\.\d+\.\d+/\d+\.\d+\.\d+/"
                              r"\d+\.\d+\.\d+)", text)
                if not m or not scrolls.get(
                        phext_io.parse_coord(m.group(1))):
                    problems.append(f"class-(a) record's Regression "
                                    f"scroll missing: {name}")
    lines.append(f"  corpus: {placed} probe scrolls placed in Tests "
                 f"Book 11 (Ch 1 Tier A / Ch 2 Tier B / Ch 3 Tier C); "
                 f"probe hashes verified against the manifest: "
                 f"{hash_ok}/{len(manifest) if manifest else 0}")
    lines.append(f"  per-probe records: {len(records)} "
                 f"(Ch 9 Sec 1, Scrolls 2..)")
    lines.append(f"  three-way agreement (current): {agree}/"
                 f"{len(manifest) if manifest else 0} "
                 f"({resolved} class-(a) divergences resolved by F5 "
                 f"commit e399b212 and counted as agreeing)")
    lines.append(f"  divergences: {divergent} current, all "
                 f"classified ((a) open {class_count['(a)']}, "
                 f"(b) {class_count['(b)']}, (c) {class_count['(c)']}); "
                 f"unclassified: {unclassified}")

    # (iv) MSVC attestation field
    att_b = scrolls.get(CONF_ATTEST_COORD)
    if att_b is None:
        problems.append("MSVC attestation scroll absent at "
                        + phext_io.fmt(CONF_ATTEST_COORD))
        lines.append("  MSVC: MANUAL — attestation scroll ABSENT")
    else:
        att = att_b.decode("utf-8", "replace")
        if "mode: manual-attestation" not in att:
            problems.append("MSVC attestation scroll lacks "
                            "'mode: manual-attestation'")
        if "status: NOT ATTESTED" in att:
            lines.append("  MSVC: MANUAL — NOT ATTESTED (attestation "
                         f"scroll {phext_io.fmt(CONF_ATTEST_COORD)}; "
                         "designated signer Will Bickford; scope = "
                         "manifest sha256 + phcc commit 94898ff9; the "
                         "runner never writes this column)")
        elif "status: ATTESTED" in att:
            akv = _kv(att)
            if akv.get("signer") and akv.get("date") and \
                    CONF_MANIFEST_SHA256 in att:
                lines.append(f"  MSVC: MANUAL — ATTESTED "
                             f"({akv.get('signer')}, {akv.get('date')}; "
                             f"scope in-manifest)")
            else:
                problems.append("MSVC attestation claims ATTESTED "
                                "without signer + date + in-scope "
                                "manifest hash")
                lines.append("  MSVC: MANUAL — ATTESTED (MALFORMED)")
        else:
            problems.append("MSVC attestation scroll has no readable "
                            "status")
            lines.append("  MSVC: MANUAL — status unreadable")
    for p in problems:
        lines.append(f"  {p}")
    if unclassified:
        status = "UNCLASSIFIED (a divergence lacks classification; " \
                 "the section refuses CURRENT)"
    elif problems:
        status = "STALE (a conformance binding moved; see above)"
    elif divergent:
        status = ("DIVERGENT-CLASSIFIED (divergences exist, all "
                  "classified — reported, not hidden)")
    else:
        status = "CURRENT (receipt matches the placed corpus; no " \
                 "current divergences)"
    lines.append(f"  status: {status}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phext")
    ap.add_argument("--verdict-out", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    scrolls = phext_io.load_phext(a.phext)
    artifacts, per_book, gaps, t1_eligible, _ = analyse(scrolls)
    claims = parse_proof_claims(scrolls)
    receipt_overlay = tiers_from_receipts(claims)
    receipted = {src: t for src, (t, _n) in receipt_overlay.items() if t is not None}
    proof_notes = {src: n for src, (_t, n) in receipt_overlay.items()}
    design = parse_design_views(scrolls)
    machine = machine_section(scrolls, a.phext)
    machine2 = machine2_section(scrolls, a.phext)
    machine3 = machine3_section(scrolls, a.phext)
    machine4 = machine4_section(scrolls, a.phext)
    assembly = assembly_section(scrolls)
    conformance = conformance_section(scrolls)
    if not a.quiet:
        print(f"gate input: {a.phext}")
        print(tables_text(per_book, artifacts, gaps, t1_eligible,
                          receipted, proof_notes, design, machine, machine2,
                          machine3, machine4, assembly, conformance))
    if a.verdict_out:
        verdict = verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                               receipted, proof_notes, design, machine, machine2,
                               machine3, machine4, assembly, conformance)
        out = dict(scrolls)
        out[VERDICT_COORD] = verdict
        blob = phext_io.implode(out)
        with open(a.verdict_out, "wb") as f:
            f.write(blob)
        print(f"verdict scroll: {phext_io.fmt(VERDICT_COORD)}")
        print(f"verdict sha256: {phext_io.sha256(verdict)}")
        print(f"verdict-out: {a.verdict_out}  {len(blob)} bytes  "
              f"sha256 {phext_io.sha256(blob)}")


if __name__ == "__main__":
    main()
