#!/usr/bin/env python3
"""segment_files.py — re-run the importer v3 -> v4 segmentation pipeline
for exactly the files named on the command line, against NEW file
bytes, and emit their Volume 3 scrolls + rebind-manifest lines +
degradation-register line as JSON (base64 payloads).

This is import_v4.py's own logic, composed per file: fresh v3
segmentation (import_fn.segment_file) followed by import_v4's
refinement branch (extract_v4 candidates splitting v3 gaps in
place). Files whose gaps gain no members keep the v3 index verbatim
— exactly what the v4 pass did to untouched files.

Run with the granularity venv python (tree-sitter):
  work/venv/bin/python segment_files.py BASE.phext OUT.json path=NEWFILE ...
"""
import base64
import json
import os
import sys

WS = os.path.expanduser("~/workspace")
sys.path.insert(0, os.path.join(WS, "phcc-importer-v4/tools"))
sys.path.insert(0, os.path.join(WS, "phcc-slice3-granularity/tools"))
import import_v4 as v4
import import_fn as v3
from phext_io import walk_bytes, fmt, sha256, parse_coord

FILES_META = {  # path -> (book, chapter, section) of its Vol 2 address
    "lib/libtcc1.c": (7, 1, 2),
}


def segment_one(path, data, v2coord_s):
    b, ch, sec = FILES_META[path]
    # ---- stage 1: fresh v3 segmentation
    segments, n_members, err3 = v3.segment_file(data)
    v3_segs = []
    for i, (kind, name, form, s, e) in enumerate(segments):
        payload = data[s:e]
        v3_segs.append({"scroll": i + 2, "kind": kind, "name": name,
                        "form": form, "s": s, "e": e, "sha": sha256(payload)})
    # ---- stage 2: v4 refinement (import_v4's rebuild branch)
    cand, err_bytes = v4.extract_v4(data)
    cand_by_span = {(m[3], m[4]): m for m in cand}
    v3_members = [sg for sg in v3_segs if sg["kind"] != "gap"]
    members_changed = []
    members_untouched = 0
    for sg in v3_members:
        m = cand_by_span.get((sg["s"], sg["e"]))
        if m is None or m[0] != sg["kind"] or m[1] != sg["name"] or m[2] != sg["form"]:
            members_changed.append({"span": f"{sg['s']}-{sg['e']}",
                                    "v3": [sg["kind"], sg["name"], sg["form"]],
                                    "v4": list(m) if m else None})
        else:
            members_untouched += 1
    v3_member_spans = {(sg["s"], sg["e"]) for sg in v3_members}
    new_cands = [m for m in cand if (m[3], m[4]) not in v3_member_spans]
    gap_segs = [sg for sg in v3_segs if sg["kind"] == "gap"]
    split = {}
    stray = []
    for m in new_cands:
        host = [g for g in gap_segs if g["s"] <= m[3] and m[4] <= g["e"]]
        if len(host) == 1:
            split.setdefault(host[0]["scroll"], []).append(m)
        else:
            stray.append(m)
    assert not stray, f"{path}: new candidates not inside exactly one v3 gap: {stray[:2]}"

    scrolls = {}
    map_lines = []
    if not split:
        numbered = [(sg["scroll"], sg["kind"], sg["name"], sg["form"],
                     sg["s"], sg["e"]) for sg in v3_segs]
        header = "# phcc file index — importer v3"
        rebuilt = False
    else:
        max_scroll = max(sg["scroll"] for sg in v3_segs)
        next_scroll = max_scroll + 1
        pieces = []
        for sg in v3_segs:
            if sg["kind"] != "gap" or sg["scroll"] not in split:
                pieces.append((sg["scroll"], sg["kind"], sg["name"],
                               sg["form"], sg["s"], sg["e"]))
                continue
            inside = sorted(split[sg["scroll"]], key=lambda m: m[3])
            sub, cur = [], sg["s"]
            for kind, name, form, s, en in inside:
                if s > cur:
                    sub.append(("gap", "-", "-", cur, s))
                sub.append((kind, name, form, s, en))
                cur = en
            if cur < sg["e"]:
                sub.append(("gap", "-", "-", cur, sg["e"]))
            for j, (k2, n2, f2, s2, e2) in enumerate(sub):
                if j == 0:
                    pieces.append((sg["scroll"], k2, n2, f2, s2, e2))
                else:
                    pieces.append((next_scroll, k2, n2, f2, s2, e2))
                    next_scroll += 1
        numbered = pieces
        header = "# phcc file index — importer v4"
        rebuilt = True

    idx_lines = [header,
                 f"# path: {path}",
                 f"# volume2: {v2coord_s}",
                 f"# sha256: {sha256(data)}  size: {len(data)}",
                 f"# parse: {v3.TS_VERSION}; members={sum(1 for x in numbered if x[1] != 'gap')} error-bytes={err_bytes} ({100.0 * err_bytes / max(len(data), 1):.1f}%)",
                 "# columns: scroll <TAB> kind <TAB> name <TAB> form <TAB> span <TAB> sha256"]
    for scr, kind, name, form, s, e in numbered:
        payload = data[s:e]
        psha = sha256(payload)
        hdr = (f"#phcc-member\tkind={kind}\tname={name}\tform={form}"
               f"\tspan={s}-{e}\tsha256={psha}\n").encode()
        coord = (1, 1, 1, 4, 3, b, ch, sec, scr)
        scrolls[fmt(coord)] = base64.b64encode(hdr + payload).decode()
        idx_lines.append(f"{scr}\t{kind}\t{name}\t{form}\t{s}-{e}\t{psha}")
        if kind != "gap":
            mc = (1, 1, 1, 4, 3, b, ch, sec, scr)
            map_lines.append(f"{path}\t{v2coord_s}\t{fmt(mc)}\t{kind}\t{name}\t{form}\t{s}-{e}\t{psha}")
    idx_coord = (1, 1, 1, 4, 3, b, ch, sec, 1)
    scrolls[fmt(idx_coord)] = base64.b64encode(
        ("\n".join(idx_lines) + "\n").encode()).decode()
    # reassembly proof: payloads in index order == file bytes
    reasm = b"".join(data[s:e] for _scr, _k, _n, _f, s, e in numbered)
    assert reasm == data, f"{path}: reassembly mismatch"
    counts = {}
    for _scr, kind, _n, _f, _s, _e in numbered:
        counts[kind] = counts.get(kind, 0) + 1
    reg_line = None
    if err_bytes > 0:
        pct = 100.0 * err_bytes / max(len(data), 1)
        reg_line = (f"{path}\tpartial\ttree-sitter error regions cover "
                    f"{err_bytes} bytes ({pct:.1f}%); unclassified bytes "
                    f"are gap segments")
    return {"scrolls": scrolls, "map_lines": map_lines, "reg_line": reg_line,
            "err_bytes": err_bytes, "err_bytes_v3": err3,
            "members_changed": members_changed,
            "members_untouched": members_untouched,
            "gaps_split": len(split), "rebuilt": rebuilt,
            "counts": counts, "n_segments": len(numbered),
            "sha256": sha256(data), "size": len(data)}


def main():
    base_path, out_path = sys.argv[1], sys.argv[2]
    specs = [a.split("=", 1) for a in sys.argv[3:]]
    scrolls = dict(walk_bytes(open(base_path, "rb").read()))
    man = {}
    for line in scrolls[(1, 1, 1, 1, 2, 10, 1, 1, 1)].decode().splitlines():
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 2:
            man[p[0]] = p[1]
    result = {}
    for path, newfile in specs:
        data = open(newfile, "rb").read()
        result[path] = segment_one(path, data, man[path])
        r = result[path]
        print(f"{path}: segments={r['n_segments']} counts={r['counts']} "
              f"gaps_split={r['gaps_split']} rebuilt={r['rebuilt']} "
              f"err_bytes={r['err_bytes']} members_changed={len(r['members_changed'])} "
              f"members_untouched={r['members_untouched']}")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=1)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
