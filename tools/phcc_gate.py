#!/usr/bin/env python3
"""phcc_gate.py — the phcc trace gate, Slice 4: REPORT-ONLY.

Extends the Slice 3 gate (v3.0.0, kept byte-compatible in its
coverage/tier/proof-claims/Design output) with the Slice 4
machine-conformance section (design §A.3): the preprocessor
conditional-stack machine scroll (Design phase, tccpp.c's address)
is re-checked live by tools/check_machine.py; the dynamic trace
results recorded in the Slice 4 machine register (Meta, Vol 2,
Book 10, Sec 10) are reported with their SHA-256 binding to the
machine scroll and the tccpp.c Source scroll re-verified (STALE
if either hash has moved); regressions filed at tccpp.c's
Regressions address are counted. D2 is closed as unnecessary
(Will, 2026-11-07) — the gate stays report-only; conformance is
reported, it never blocks. D4 likewise: the external gate is the
architecture.

Reads a phcc phext and reports, for Volume 2:
  (a) per-Book phase coverage: for Books 1-10, the % of Source
      artifacts with each phase (Collections 1-10) populated at
      their 5D address (same Volume/Book/Chapter/Section, any
      Scroll).
  (b) a tier distribution: "T1-eligible (no receipt yet)" for
      Tests-populated artifacts, receipt-driven T2/T3 overlay from
      the Proofs phase (Slice 2), everything else T0.
  (c) the Design staleness section described above.
  (d) the Slice 4 machine-conformance section described above.
  (e) optionally, a VERDICT scroll written into a COPY of the phext
      (--verdict-out): Meta, Volume 2, Book 10, Ch 1, Sec 9. The
      verdict is REPORT status; it blocks nothing.

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
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

TOOL_VERSION = "phcc_gate.py 4.0.0 (slice4)"
VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 9, 1)  # Slice 4 verdict: Meta, Vol 2, Book 10, Sec 9
SLICE3_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 7, 1)  # Slice 3 verdict (never evidence)
SLICE2_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 5, 1)  # Slice 2 verdict (never evidence)
SLICE1_VERDICT_COORD = (1, 1, 1, 1, 2, 10, 1, 4, 1)  # Slice 1 verdict (never evidence)
ALL_VERDICT_COORDS = (VERDICT_COORD, SLICE3_VERDICT_COORD,
                      SLICE2_VERDICT_COORD, SLICE1_VERDICT_COORD)
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
                machine=None):
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
    return "\n".join(lines)


def verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                 receipted=None, proof_notes=None, design=None,
                 machine=None):
    lines = []
    lines.append("# phcc gate verdict - Slice 4")
    lines.append(f"tool: {TOOL_VERSION}")
    lines.append("mode: REPORT-ONLY")
    lines.append("status: REPORT")
    lines.append("volume: 2")
    lines.append(f"artifacts-checked: {len(artifacts)}")
    lines.append("")
    lines.append(tables_text(per_book, artifacts, gaps, t1_eligible,
                             receipted, proof_notes, design, machine))
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
    if not a.quiet:
        print(f"gate input: {a.phext}")
        print(tables_text(per_book, artifacts, gaps, t1_eligible,
                          receipted, proof_notes, design, machine))
    if a.verdict_out:
        verdict = verdict_text(scrolls, artifacts, per_book, gaps, t1_eligible,
                               receipted, proof_notes, design, machine)
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
