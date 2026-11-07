#!/usr/bin/env python3
"""assemble_reissue.py — assemble step of the F1 receipt re-issue:
stage1 + the regenerated libtcc1.c Design view + the three re-issued
Proofs receipts + the Proofs register note (Sec 6) + the Sec 22
re-issue resolution (hold CLOSED). The gate verdict is NOT written
here — gate v8.1.0 regenerates it at Meta Sec 20.
"""
import json
import os
import sys

WS = os.path.expanduser("~/workspace")
sys.path.insert(0, os.path.join(WS, "phcc-reissue/tools"))
import phext_io

R = os.path.join(WS, "phcc-reissue")
NEW1 = "69879e2a6117abe1dba7ddcf5539d9b816f18bea3e80452b96c1c0c991069aab"
COMMIT = "e399b212271b7e1277371b4b7ac6a34095e13363"


def sha(b):
    return phext_io.sha256(b)


def main():
    out = phext_io.load_phext(os.path.join(R, "work/stage1.phext"))
    design = phext_io.load_phext(os.path.join(R, "work/stage2-design.phext"))
    base = phext_io.load_phext(os.path.join(WS, "phcc-catchup/phcc.phext"))
    wp = json.load(open(os.path.join(R, "work/wp_counts.json")))

    view = (1, 1, 1, 3, 2, 7, 1, 2, 1)
    assert design[view] != base[view]
    out[view] = design[view]

    # ---- receipts ----
    wp_coord = (1, 1, 1, 10, 2, 7, 1, 2, 2)
    cb_coord = (1, 1, 1, 10, 2, 7, 1, 2, 4)
    df_coord = (1, 1, 1, 10, 2, 7, 1, 2, 5)
    wp_text = open(os.path.join(R, "work/receipt-wp-new.txt")).read()
    assert "__WP_REPRO__" not in wp_text, "WP placeholder not yet substituted"
    out[wp_coord] = wp_text.encode()
    out[cb_coord] = open(os.path.join(R, "work/receipt-cbmc-new.txt"), "rb").read()
    out[df_coord] = open(os.path.join(R, "work/receipt-diff-new.txt"), "rb").read()
    rc_sha = {c: sha(out[c]) for c in (wp_coord, cb_coord, df_coord)}

    # ---- Proofs register (Sec 6): re-issue note ----
    reg6 = (1, 1, 1, 1, 2, 10, 1, 6, 1)
    t = out[reg6].decode()
    assert "Re-issue (2026-11-07" not in t
    t += (f"\nRe-issue (2026-11-07, F1 receipt re-issue pass): Scrolls 2, 4 and 5 "
          f"re-issued against the F1 source bytes ({NEW1[:12]}...) — WP re-run on the "
          f"unchanged h6 contracts artifact reproduced {wp['discharged']}/{wp['generated']} VCs; "
          f"CBMC and the float differential re-run on the F1 file with identical outcomes "
          f"(5/5 harnesses successful; 0 divergences on 94 defined inputs); artifact<->F1-source "
          f"equivalence established by a three-way differential (7,242,324 comparisons, "
          f"0 divergences). Scrolls 1 and 3 unchanged. The catch-up hold (Meta Sec 22) is CLOSED.\n")
    out[reg6] = t.encode()

    # ---- Sec 22: re-issue resolution — hold CLOSED ----
    sec22 = (1, 1, 1, 1, 2, 10, 1, 22, 1)
    t = out[sec22].decode()
    assert "re-issue resolution" not in t
    t += f"""re-issue resolution (2026-11-07, F1 receipt re-issue pass; gate v8.1.0 verdict regenerated at Meta Sec 20): the lib/libtcc1.c HOLD recorded in the catch-up resolution above is CLOSED by re-issue, not by refresh. (a) Source: Vol 2 scroll refreshed to the repo F1 bytes {NEW1} (13067 B; Slice 0 manifest spliced); Vol 3 re-segmented via the importer v3 -> v4 pipeline (92 scrolls, 55 members, members_changed 0, error-bytes 0, reassembly byte-exact; 25 segment scrolls changed — the two cast lines plus every span after them); the libtcc1.c Design view regenerated (the full-regeneration diff is exactly this one view). (b) Receipts re-issued at their existing coordinates against the F1 bytes: WP receipt (1.1.1/10.2.7/1.2.2, sha {rc_sha[wp_coord][:12]}...) — WP re-run on aletheia-core on the UNCHANGED h6 contracts artifact (1fa00dab...) at the hardening config (alt-ergo+z3+cvc5, 120 s/goal, duty-cycled) reproduced {wp['discharged']}/{wp['generated']} VCs discharged, {wp['undischarged']} open, per-function outcomes identical to the hardening issue ({wp['detail']}); CBMC receipt (1.2.4, sha {rc_sha[cb_coord][:12]}...) — re-run with the F1 file verbatim in the harness: VERIFICATION SUCCESSFUL, 5/5 harnesses, 5/5 properties each; differential receipt (1.2.5, sha {rc_sha[df_coord][:12]}...) — corpus re-run: 0 divergences on the 94 C-defined inputs, 34 undefined inputs recorded-not-asserted. The artifact<->source link is re-established, not assumed: the artifact's transcription delta against a verbatim F1 extraction is exactly the two F1 cast lines (diff-verified), and a three-way differential (artifact vs F1 extraction vs pre-F1 extraction; gcc; edge grid + 400,000 random inputs per family; contract envelope) gave 7,242,324 comparisons, 0 divergences. (c) Artifacts: libtcc1 .o/.a rebuilt on aletheia-core from the F1 bytes with the builds method (tree at {COMMIT[:9]}...) — all four binaries are BYTE-IDENTICAL to the previous build (x86_64 .o 48d23e83..., arm64 .o ed5c1bcd..., x86_64 .a 7fac7e6c..., arm64 .a beebb4ee...), so the Library-10000 scrolls are unchanged and the F1 claim (the cast changes no emitted code) is now verified on both backends; both assembly listings regenerated with fresh provenance (source-sha256 {NEW1[:12]}..., compiler-commit {COMMIT[:12]}...; listing bodies byte-identical to the previous issues, as the objects are). (d) phext addendum: phext/phext.c and phext/phext.h refreshed to the repo F4 bytes (cfdab3fd... / 144653da...) in Source and in the Sec 14 addendum; phext.o rebuilt from the F4 source (df1105cf..., replacing 2c66f71c... in the region), its listing regenerated, manifest + build register (Sec 15) provenance updated. Carried tree is now byte-identical to the repo tree at e399b212 for ALL 558 files, lib/libtcc1.c included (acceptance receipts in the pass report).
"""
    out[sec22] = t.encode()

    blob = phext_io.implode(out)
    path = os.path.join(R, "work/phcc-pre-verdict.phext")
    with open(path, "wb") as f:
        f.write(blob)
    print(f"pre-verdict: {path}  {len(blob)} bytes  sha256 {sha(blob)}")
    print(f"scrolls: {len(out)} (catchup base {len(base)})")
    back = phext_io.load_phext(path)
    changed = [c for c in back if back[c] != base.get(c)]
    added = [c for c in back if c not in base]
    removed = [c for c in base if c not in back]
    print(f"vs catchup base: changed {len(changed)} added {len(added)} removed {len(removed)}")


if __name__ == "__main__":
    main()
