#!/usr/bin/env python3
"""import_v4.py — importer v4: fix v3's gap-type classification defect.

Root cause (diagnosed in tools/diagnose.py against phcc-fn.phext;
Slice 3 REPORT.md deviation (b)) — v3's classifier missed 723 type
definitions, for exactly two reasons:

  A. Bare specifier nodes (242 of 723). tree-sitter-c emits a
     struct/union/enum definition WITHOUT declarators
     (`struct TCCState { ... };`) as a bare *_specifier node at file
     scope, with the terminating ';' as a separate sibling node.
     v3's classify() only recognised specifiers nested inside a
     `declaration` node, so every such definition fell into a gap —
     TCCState/SymAttr/FuncAttr in tcc.h included, plus 37 types
     nested inside those bodies as collateral.
  B. linkage_specification not recursed (481 of 723). The bundled
     win32 headers wrap declarations in extern "C" { ... }, which
     tree-sitter-c parses as ONE linkage_specification node. v3
     recursed through preproc containers and ERROR nodes but not
     linkage blocks, so each whole block became a single gap.

Fix: classify_v4 = v3's classify + bare-specifier handling (member
span extended through the sibling ';'), and top_level_nodes_v4
additionally recurses through linkage_specification /
declaration_list.

Placement = REFINEMENT of v3's segmentation, not a re-run:
  - every v3 member keeps its exact scroll address and payload;
  - a v3 gap that gains members is split in place: the first piece
    keeps the gap's scroll number, later pieces (members and
    sub-gaps) take fresh scroll numbers appended after the file's
    current maximum. The index scroll lists pieces in source order;
    order is index-authoritative (as reassemble.py and the Slice 3
    extractor already read it), scroll numbers need not be monotonic.
  - files with no new candidates keep their whole Volume 3 section
    byte-identical; only the three Meta V3 scrolls (manifest,
    layout notes, degradation register) are regenerated globally.

Base: phcc-fn.phext (importer v3 output) — never mutated.
Run with the granularity venv python (tree-sitter installed there).
"""
import argparse, hashlib, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser("~/workspace/phcc-slice3-granularity/tools"))
from phext_io import walk_bytes, implode, fmt, sha256, parse_coord
import import_fn as v3

TS_VERSION = v3.TS_VERSION
SPECIFIERS = {"struct_specifier": "struct", "union_specifier": "union",
              "enum_specifier": "enum"}
CONTAINERS_V4 = v3.CONTAINERS | {"linkage_specification", "declaration_list"}


# ------------------------------------------------------------ extraction
def top_level_nodes_v4(root):
    out = []

    def rec(n):
        for c in n.children:
            if c.type in CONTAINERS_V4 or c.type == "ERROR":
                rec(c)
            else:
                out.append(c)

    rec(root)
    out.sort(key=lambda n: n.start_byte)
    return out


_WS_COMMENT_RE = re.compile(r"(\s|//[^\n]*|/\*.*?\*/)*", re.S)


def only_ws_comments(data, s, e):
    return _WS_COMMENT_RE.fullmatch(data[s:e].decode("utf-8", "replace")) is not None


def classify_v4(data, node, next_node):
    """(kind, name, form, end_override) or None. end_override extends
    the member span (bare specifier through its ';' sibling)."""
    t = node.type
    if t in SPECIFIERS:
        body = node.child_by_field_name("body")
        name_node = node.child_by_field_name("name")
        nm = v3.node_text(data, name_node) if name_node is not None else "?"
        if body is not None:
            form = SPECIFIERS[t]
        else:
            form = "fwd"
        end = node.end_byte
        if next_node is not None and next_node.type == ";" and \
                only_ws_comments(data, node.end_byte, next_node.start_byte):
            end = next_node.end_byte
        return ("type", nm, form, end)
    c = v3.classify(data, node)
    if c is None:
        return None
    return (c[0], c[1], c[2], node.end_byte)


def extract_v4(data):
    """All candidate members of one file: [(kind,name,form,s,e)]."""
    tree = v3.PARSER.parse(data)
    nodes = top_level_nodes_v4(tree.root_node)
    members = []
    for i, node in enumerate(nodes):
        nxt = nodes[i + 1] if i + 1 < len(nodes) else None
        c = classify_v4(data, node, nxt)
        if c is not None:
            members.append((c[0], c[1], c[2], node.start_byte, c[3]))
    members.sort(key=lambda m: m[3])
    clean, last_end = [], -1
    for m in members:
        if m[3] >= last_end:
            clean.append(m)
            last_end = m[4]
    # error bytes under the v3 rule, against the v4 member set
    eb = []
    v3.error_spans(tree.root_node, eb)
    err_bytes = 0
    for s, e in eb:
        inside = sum(m[4] - m[3] for m in clean if m[3] >= s and m[4] <= e)
        err_bytes += (e - s) - inside
    return clean, err_bytes


# ------------------------------------------------------------ v3 reading
def read_v3_index(scrolls, b, ch, sec):
    raw = scrolls.get((1, 1, 1, 4, 3, b, ch, sec, 1))
    if raw is None or not raw.startswith(b"# phcc file index"):
        return None
    segs = []
    for line in raw.decode("utf-8", "replace").splitlines():
        p = line.split("\t")
        if len(p) != 6 or not p[0].isdigit():
            continue
        s0, e0 = p[4].split("-")
        segs.append({"scroll": int(p[0]), "kind": p[1], "name": p[2],
                     "form": p[3], "s": int(s0), "e": int(e0), "sha": p[5]})
    return segs


LAYOUT_NOTES_V4 = """# phcc.phext — Volume 3 layout notes (importer v4)

Importer v4 is a REFINEMENT of importer v3's Volume 3 (Will ruling
#7 structure, unchanged): same placement, same segment scheme, same
index format. It fixes v3's classifier, which left type definitions
in gap segments for two reasons: (A) struct/union/enum definitions
without declarators parse as bare *_specifier nodes at file scope,
which v3 did not recognise outside a `declaration` node; (B) extern
"C" { ... } blocks parse as one linkage_specification node, which
v3 did not recurse into.

Refinement rules (the v3->v4 diff is auditable from the manifest):
- every v3 member keeps its exact scroll address and payload bytes;
- a v3 gap segment that gains members is split in place: the first
  piece keeps the gap's scroll number; subsequent pieces (members
  and sub-gaps) take fresh scroll numbers appended after the file's
  current maximum. Segment ORDER is defined by the file's index
  scroll (source order), not by scroll number — the same reading
  reassemble.py and generated-view extractors already use.
- files with no reclassified bytes keep their Volume 3 section
  byte-identical to importer v3's output.

Reassembly = concatenate segment payloads in index order; the
Volume-2 scroll is never consulted for structured files.
"""


def main():
    ap = argparse.ArgumentParser()
    home = os.path.expanduser("~")
    w = os.path.join(home, "workspace/phcc-importer-v4")
    ap.add_argument("--base", default=os.path.join(
        home, "workspace/phcc-slice3-granularity/phcc-fn.phext"))
    ap.add_argument("--out", default=os.path.join(w, "phcc-fn.phext"))
    ap.add_argument("--stats", default=os.path.join(w, "logs/v4-stats.json"))
    ap.add_argument("--diff", default=os.path.join(w, "logs/v4-diff.json"))
    a = ap.parse_args()

    base_bytes = open(a.base, "rb").read()
    scrolls = dict(walk_bytes(base_bytes))
    assert implode(scrolls) == base_bytes, "BASE ROUND-TRIP FAILED on phcc-fn.phext"
    print(f"base phcc-fn.phext: {len(base_bytes)} bytes sha256 {sha256(base_bytes)}; "
          f"re-emission byte-identical OK")

    entries = []
    for line in scrolls[(1, 1, 1, 1, 2, 10, 1, 1, 1)].decode().splitlines():
        if not line or line.startswith("#"):
            continue
        p, c, sha, size, mode = line.split("\t")
        entries.append({"path": p, "coord": parse_coord(c), "sha": sha,
                        "size": int(size), "mode": mode})
    print(f"manifest: {len(entries)} files")

    out_scrolls = dict(scrolls)
    map_lines = ["# phcc rebind manifest — importer v4 (Volume 2 file address -> Volume 3 member addresses)",
                 "# base phext: importer v3 phcc-fn.phext sha256 " + sha256(base_bytes),
                 "# refinement of v3 segmentation: v3 members keep address + payload; split gaps append scroll numbers",
                 "# columns: path <TAB> vol2-coordinate <TAB> member-coordinate <TAB> kind <TAB> name <TAB> form <TAB> span <TAB> sha256"]
    reg_lines = ["# degradation register — importer v4",
                 "# columns: path <TAB> status <TAB> reason"]

    diff = {"members_added": [], "members_changed": [], "members_untouched": 0,
            "member_payloads_verified": 0, "gaps_split": 0, "files_rebuilt": [],
            "files_newly_structured": [], "index_scrolls_rewritten": 0,
            "v3_members_total": 0, "v4_members_total": 0}
    stats = {"members": Counter(), "v3_members": Counter(), "per_file_added": {}}

    for e in entries:
        path, v2 = e["path"], e["coord"]
        data = scrolls[v2]
        assert sha256(data) == e["sha"], f"base scroll hash mismatch: {path}"
        b, ch, sec = v2[5], v2[6], v2[7]
        ext = os.path.splitext(path)[1].lower()
        v3_segs = read_v3_index(scrolls, b, ch, sec)
        if ext not in v3.C_EXTS:
            reg_lines.append(f"{path}\tfile-level\tnot C source (extension '{ext or 'none'}'); bridge path only")
            map_lines.append(f"# file\t{path}\t{fmt(v2)}\tfile-level (not C source)")
            continue

        cand, err_bytes = extract_v4(data)
        cand_by_span = {(m[3], m[4]): m for m in cand}

        if v3_segs is None:
            # file-level under v3: structure it only if v4 finds members
            if not cand:
                reg_lines.append(f"{path}\tfile-level\tzero members extracted (v4 classifier); bridge path only")
                map_lines.append(f"# file\t{path}\t{fmt(v2)}\tfile-level (zero members extracted)")
                continue
            pieces = []
            cur = 0
            for kind, name, form, s, en in cand:
                if s > cur:
                    pieces.append(("gap", "-", "-", cur, s, None))
                pieces.append((kind, name, form, s, en, None))
                cur = en
            if cur < len(data):
                pieces.append(("gap", "-", "-", cur, len(data), None))
            numbered = [(i + 2, k, n, f, s, en) for i, (k, n, f, s, en, _) in enumerate(pieces)]
            diff["files_newly_structured"].append(path)
            old_members = []
        else:
            v3_members = [sg for sg in v3_segs if sg["kind"] != "gap"]
            diff["v3_members_total"] += len(v3_members)
            stats["v3_members"].update(sg["kind"] for sg in v3_members)
            # sanity: v4 must reproduce every v3 member identically
            for sg in v3_members:
                m = cand_by_span.get((sg["s"], sg["e"]))
                if m is None or m[0] != sg["kind"] or m[1] != sg["name"] or m[2] != sg["form"]:
                    diff["members_changed"].append(
                        {"path": path, "span": f"{sg['s']}-{sg['e']}",
                         "v3": [sg["kind"], sg["name"], sg["form"]],
                         "v4": list(m) if m else None})
                else:
                    diff["members_untouched"] += 1
            v3_member_spans = {(sg["s"], sg["e"]) for sg in v3_members}
            new_cands = [m for m in cand if (m[3], m[4]) not in v3_member_spans]
            # every new candidate must lie inside ONE v3 gap
            gap_segs = [sg for sg in v3_segs if sg["kind"] == "gap"]
            split = {}  # gap scroll -> [new candidate members inside]
            stray = []
            for m in new_cands:
                host = [g for g in gap_segs if g["s"] <= m[3] and m[4] <= g["e"]]
                if len(host) == 1:
                    split.setdefault(host[0]["scroll"], []).append(m)
                else:
                    stray.append(m)
            assert not stray, f"{path}: new candidates not inside exactly one v3 gap: {stray[:2]}"

            if not split:
                # untouched file: copy v3 index lines into the manifest
                for sg in v3_members:
                    mc = (1, 1, 1, 4, 3, b, ch, sec, sg["scroll"])
                    map_lines.append(f"{path}\t{fmt(v2)}\t{fmt(mc)}\t{sg['kind']}\t{sg['name']}\t{sg['form']}\t{sg['s']}-{sg['e']}\t{sg['sha']}")
                    stats["members"][sg["kind"]] += 1
                    diff["v4_members_total"] += 1
                if err_bytes > 0:
                    pct = 100.0 * err_bytes / max(len(data), 1)
                    reg_lines.append(f"{path}\tpartial\ttree-sitter error regions cover {err_bytes} bytes ({pct:.1f}%); unclassified bytes are gap segments")
                continue

            # rebuild this file's section by splitting the affected gaps
            diff["files_rebuilt"].append(path)
            max_scroll = max(sg["scroll"] for sg in v3_segs)
            next_scroll = max_scroll + 1
            pieces = []  # (scroll, kind, name, form, s, e, is_new)
            for sg in v3_segs:
                if sg["kind"] != "gap" or sg["scroll"] not in split:
                    pieces.append((sg["scroll"], sg["kind"], sg["name"], sg["form"],
                                   sg["s"], sg["e"], False))
                    continue
                diff["gaps_split"] += 1
                inside = sorted(split[sg["scroll"]], key=lambda m: m[3])
                sub, cur, first = [], sg["s"], True
                for kind, name, form, s, en in inside:
                    if s > cur:
                        sub.append(("gap", "-", "-", cur, s))
                    sub.append((kind, name, form, s, en))
                    cur = en
                if cur < sg["e"]:
                    sub.append(("gap", "-", "-", cur, sg["e"]))
                for k2, n2, f2, s2, e2 in sub:
                    if first:
                        pieces.append((sg["scroll"], k2, n2, f2, s2, e2, k2 != "gap"))
                        first = False
                    else:
                        pieces.append((next_scroll, k2, n2, f2, s2, e2, k2 != "gap"))
                        next_scroll += 1
            numbered = pieces

        # write the (re)built section
        idx_lines = ["# phcc file index — importer v4",
                     f"# path: {path}",
                     f"# volume2: {fmt(v2)}",
                     f"# sha256: {e['sha']}  size: {len(data)}",
                     f"# parse: {TS_VERSION}; members={sum(1 for x in numbered if x[1] != 'gap')} error-bytes={err_bytes} ({100.0 * err_bytes / max(len(data), 1):.1f}%)",
                     "# columns: scroll <TAB> kind <TAB> name <TAB> form <TAB> span <TAB> sha256"]
        # drop any v3 segment scrolls of this file beyond the new set
        new_scroll_ids = set()
        n_added_here = 0
        for scr, kind, name, form, s, en, *rest in numbered:
            is_new = rest[0] if rest else True
            payload = data[s:en]
            psha = sha256(payload)
            header = f"#phcc-member\tkind={kind}\tname={name}\tform={form}\tspan={s}-{en}\tsha256={psha}\n".encode()
            coord = (1, 1, 1, 4, 3, b, ch, sec, scr)
            out_scrolls[coord] = header + payload
            new_scroll_ids.add(coord)
            idx_lines.append(f"{scr}\t{kind}\t{name}\t{form}\t{s}-{en}\t{psha}")
            if kind != "gap":
                stats["members"][kind] += 1
                diff["v4_members_total"] += 1
                map_lines.append(f"{path}\t{fmt(v2)}\t{fmt(coord)}\t{kind}\t{name}\t{form}\t{s}-{en}\t{psha}")
                if v3_segs is not None and is_new:
                    diff["members_added"].append(
                        {"path": path, "coord": fmt(coord), "kind": kind,
                         "name": name, "form": form, "span": f"{s}-{en}", "sha256": psha})
                    n_added_here += 1
        if n_added_here:
            stats["per_file_added"][path] = n_added_here
        # remove stale v3 segment scrolls of rebuilt files not reused
        if v3_segs is not None:
            for sg in v3_segs:
                coord = (1, 1, 1, 4, 3, b, ch, sec, sg["scroll"])
                if coord not in new_scroll_ids:
                    del out_scrolls[coord]
        idx_coord = (1, 1, 1, 4, 3, b, ch, sec, 1)
        out_scrolls[idx_coord] = ("\n".join(idx_lines) + "\n").encode()
        if v3_segs is not None:
            diff["index_scrolls_rewritten"] += 1
        if err_bytes > 0:
            pct = 100.0 * err_bytes / max(len(data), 1)
            reg_lines.append(f"{path}\tpartial\ttree-sitter error regions cover {err_bytes} bytes ({pct:.1f}%); unclassified bytes are gap segments")

    # Residual gap types: constructs where tree-sitter-c produces NO
    # specifier node at all, so no classifier rule can extract a
    # member (diagnosed individually, phcc-importer-v4 REPORT.md).
    # Recorded, never silently left: 5 recovered types in 3 files.
    RESIDUAL = [
        ("il-gen.c", "enum ILOPCodes (span 2573-2671): enum body is "
         "#define/#include/#undef lines — grammar fragments it into "
         "flat tokens, no enum_specifier node exists to classify"),
        ("win32/include/winapi/winnt.h", "anonymous union + anonymous "
         "struct nested in the CONTEXT64 typedef (spans 44381-44738, "
         "44457-44731): parse truncates the typedef inside the file's "
         "ERROR region and spills the remaining fields as loose "
         "tokens; no containing member exists"),
        ("tests/tests2/60_errors_and_warnings.c", "struct y / struct z "
         "(spans 3695-3741, 3799-3902): struct bodies contain "
         "_Static_assert instead of field declarations — grammar "
         "fragments them, no struct_specifier node exists"),
    ]
    for pth, why in RESIDUAL:
        reg_lines.append(f"{pth}\tresidual-gap-types\t{why}")

    out_scrolls[(1, 1, 1, 1, 3, 10, 1, 1, 1)] = ("\n".join(map_lines) + "\n").encode()
    out_scrolls[(1, 1, 1, 1, 3, 10, 1, 2, 1)] = LAYOUT_NOTES_V4.encode()
    out_scrolls[(1, 1, 1, 1, 3, 10, 1, 3, 1)] = ("\n".join(reg_lines) + "\n").encode()

    blob = implode(out_scrolls)
    with open(a.out, "wb") as f:
        f.write(blob)

    # ---- verification against the base, on the written artifact
    back = dict(walk_bytes(blob))
    rebuilt_secs = set()
    for pth in diff["files_rebuilt"] + diff["files_newly_structured"]:
        ent = next(x for x in entries if x["path"] == pth)
        c = ent["coord"]
        rebuilt_secs.add((c[5], c[6], c[7]))
    meta_v3 = {(1, 1, 1, 1, 3, 10, 1, 1, 1), (1, 1, 1, 1, 3, 10, 1, 2, 1),
               (1, 1, 1, 1, 3, 10, 1, 3, 1)}

    def is_rebuilt(k):
        return k in meta_v3 or (len(k) == 9 and k[3] == 4 and k[4] == 3 and
                                (k[5], k[6], k[7]) in rebuilt_secs)

    altered = [k for k, v in scrolls.items()
               if not is_rebuilt(k) and back.get(k) != v]
    assert not altered, f"non-rebuilt scrolls altered: {altered[:3]}"
    missing = [k for k in scrolls if k not in back and not is_rebuilt(k)]
    assert not missing, f"scrolls lost: {missing[:3]}"
    # v3 member payloads byte-identical at identical addresses
    verified = 0
    for ent in entries:
        c = ent["coord"]
        if (c[5], c[6], c[7]) in rebuilt_secs:
            old = read_v3_index(scrolls, c[5], c[6], c[7])
            if old is None:
                continue
            for sg in old:
                if sg["kind"] == "gap":
                    continue
                coord = (1, 1, 1, 4, 3, c[5], c[6], c[7], sg["scroll"])
                raw = back[coord]
                payload = raw.split(b"\n", 1)[1]
                assert sha256(payload) == sg["sha"], f"member payload changed: {ent['path']} scroll {sg['scroll']}"
                verified += 1
    diff["member_payloads_verified"] = verified
    print(f"output: {a.out}  {len(blob)} bytes  sha256 {sha256(blob)}")
    print(f"non-rebuilt scrolls byte-identical OK; v3 member payloads verified at same address: {verified}")
    print(f"members: v3 {dict(stats['v3_members'])} -> v4 added "
          f"{dict(Counter(m['kind'] for m in diff['members_added']))}; changed: {len(diff['members_changed'])}")
    print(f"gaps split: {diff['gaps_split']}; files rebuilt: {len(diff['files_rebuilt'])}; "
          f"newly structured: {len(diff['files_newly_structured'])}; members untouched: {diff['members_untouched']}")
    with open(a.stats, "w") as f:
        json.dump({"members_v4_total": dict(stats["members"]),
                   "members_v3": dict(stats["v3_members"]),
                   "per_file_added": stats["per_file_added"]}, f, indent=1)
    with open(a.diff, "w") as f:
        json.dump(diff, f, indent=1)


if __name__ == "__main__":
    main()
