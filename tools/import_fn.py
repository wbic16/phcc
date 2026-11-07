#!/usr/bin/env python3
"""import_fn.py — importer v3: phcc Source at function/type/object level.

Will ruling #7 (D6 REVERSED, 2026-11-07): Source moves to function-,
type-, and object-level structure; file import is the bridge/legacy
path. Design: phcc-slice3-granularity/REPORT.md.

Reads the Slice 2 phext (base), inherits every scroll byte-identical,
and ADDS:
  Collection 4 (Source), Volume 3 — mirrors Volume 2 placement
  (path -> same Book/Chapter/Section):
    Scroll 1      = the file's index/header scroll (segment table)
    Scrolls 2..   = segment scrolls in source order, tiling the file
                    bytes exactly: member segments (function / type /
                    object) and gap segments (everything else)
  Collection 1 (Meta), Volume 3, Book 10, Ch 1:
    Sec 1 = rebind manifest (old file address -> member addresses)
    Sec 2 = layout notes
    Sec 3 = degradation register (file-level / partial files + why)

Parser: tree-sitter C grammar over raw bytes (spans are original
byte offsets by construction). Losslessness never depends on parse
quality: segments tile [0, size) by construction, asserted per file.

Run with the venv python (tree-sitter installed there):
  work/venv/bin/python tools/import_fn.py [--base PHEXT] [--out PHEXT]
"""
import argparse, hashlib, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from phext_io import walk_bytes, implode, fmt, sha256, parse_coord  # slice1 copy

from tree_sitter import Language, Parser
import tree_sitter_c

PARSER = Parser(Language(tree_sitter_c.language()))
TS_VERSION = "tree-sitter-c 0.24.2 / tree-sitter 0.26.0"

CONTAINERS = {"preproc_if", "preproc_ifdef", "preproc_else", "preproc_elif"}
C_EXTS = {".c", ".h"}


# ------------------------------------------------------------------ names
def node_text(data, node):
    return data[node.start_byte:node.end_byte].decode("utf-8", "replace")


def unwrap_declarator(node):
    """Follow declarator chains; return (outer_type, identifier_node|None)."""
    outer = node.type
    n = node
    while n is not None:
        if n.type in ("identifier", "type_identifier", "field_identifier"):
            return outer, n
        n = n.child_by_field_name("declarator")
        if n is not None and outer in ("init_declarator",):
            outer = n.type
    return outer, None


def declarator_names(data, decl_node):
    """All identifier names declared by a declaration/type_definition node."""
    names, outers = [], []
    for child in decl_node.children:
        if child.type in ("init_declarator", "declarator") or \
           child.type.endswith("_declarator") or child.type == "identifier":
            outer, ident = unwrap_declarator(child)
            outers.append(outer)
            if ident is not None:
                names.append(node_text(data, ident))
    # type_definition: declarators hang off the 'declarator' field chain too
    d = decl_node.child_by_field_name("declarator")
    if d is not None and not names:
        outer, ident = unwrap_declarator(d)
        outers.append(outer)
        if ident is not None:
            names.append(node_text(data, ident))
    return names, outers


def classify(data, node):
    """Return (kind, name, form) for a top-level node, or None -> gap."""
    t = node.type
    if t == "function_definition":
        d = node.child_by_field_name("declarator")
        _, ident = unwrap_declarator(d) if d is not None else (None, None)
        return ("function", node_text(data, ident) if ident else "?", "def")
    if t == "type_definition":
        names, _ = declarator_names(data, node)
        return ("type", ",".join(names) if names else "?", "typedef")
    if t == "preproc_def":
        for c in node.children:
            if c.type == "identifier":
                return ("object", node_text(data, c), "macro")
        return ("object", "?", "macro")
    if t == "preproc_function_def":
        for c in node.children:
            if c.type == "identifier":
                return ("object", node_text(data, c), "macro")
        return ("object", "?", "macro")
    if t == "declaration":
        # struct/union/enum specifier with a body -> type definition
        for c in node.children:
            if c.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                body = c.child_by_field_name("body")
                name_node = c.child_by_field_name("name")
                if body is not None:
                    nm = node_text(data, name_node) if name_node is not None else None
                    if nm is None:
                        names, _ = declarator_names(data, node)
                        nm = names[0] if names else "?"
                    form = {"struct_specifier": "struct", "union_specifier": "union",
                            "enum_specifier": "enum"}[c.type]
                    return ("type", nm, form)
                if name_node is not None and not declarator_names(data, node)[0]:
                    return ("type", node_text(data, name_node), "fwd")
        names, outers = declarator_names(data, node)
        if names and any(o == "function_declarator" for o in outers):
            return ("function", ",".join(names), "decl")
        if names:
            return ("object", ",".join(names), "global")
        return None
    return None


def top_level_nodes(root):
    """Translation-unit children, recursing through preprocessor
    conditional containers (guarded file-scope members) and through
    ERROR nodes (salvage: one early parse error otherwise swallows
    the rest of the file, well-formed members included — observed in
    i386-gen.c and tccrun.c)."""
    out = []

    def rec(n):
        for c in n.children:
            if c.type in CONTAINERS or c.type == "ERROR":
                rec(c)
            else:
                out.append(c)

    rec(root)
    out.sort(key=lambda n: n.start_byte)
    return out


def error_spans(node, acc):
    if node.type == "ERROR":
        acc.append((node.start_byte, node.end_byte))
        return
    for c in node.children:
        error_spans(c, acc)


def segment_file(data):
    """Parse one C file; return (segments, n_members, err_bytes) where
    segments = [(kind, name, form, start, end)] tiling [0, len(data))."""
    tree = PARSER.parse(data)
    members = []
    for node in top_level_nodes(tree.root_node):
        c = classify(data, node)
        if c is not None:
            members.append((c[0], c[1], c[2], node.start_byte, node.end_byte))
    members.sort(key=lambda m: m[3])
    # de-overlap defensively (nested containers could double-see a node)
    clean, last_end = [], -1
    for m in members:
        if m[3] >= last_end:
            clean.append(m)
            last_end = m[4]
    segments, cur = [], 0
    for kind, name, form, s, e in clean:
        if s > cur:
            segments.append(("gap", "-", "-", cur, s))
        segments.append((kind, name, form, s, e))
        cur = e
    if cur < len(data):
        segments.append(("gap", "-", "-", cur, len(data)))
    assert segments and segments[0][3] == 0 and segments[-1][4] == len(data)
    for a, b in zip(segments, segments[1:]):
        assert a[4] == b[3], "tiling hole"
    eb = []
    error_spans(tree.root_node, eb)
    # error bytes = bytes under ERROR nodes that did NOT become
    # members (salvaged members inside an ERROR span are real members)
    err_bytes = 0
    for s, e in eb:
        inside = sum(m[4] - m[3] for m in clean if m[3] >= s and m[4] <= e)
        err_bytes += (e - s) - inside
    return segments, len(clean), err_bytes


# ------------------------------------------------------------------ main
LAYOUT_NOTES = """# phcc.phext — Volume 3 layout notes (importer v3, re-granulation)

Will ruling #7 (D6 reversed): Source is structured below the file.
Volume 2 remains the bridge/legacy path — file import, Scroll 1 =
whole file bytes, untouched. Volume 3 (Collection 4, Source) mirrors
Volume 2 placement path-for-path (same Book/Chapter/Section) and
splits each file at its own address:

- Scroll 1: index/header scroll — path, Volume-2 coordinate, file
  SHA-256/size, parse status, and the segment table.
- Scrolls 2..: segment scrolls in source order, tiling the file bytes
  exactly. kind = function (def = definition, decl = prototype),
  type (struct/union/enum with body, typedef, fwd = forward
  declaration), object (global = file-scope variable, macro = #define),
  gap (everything else: preprocessor lines, comments, whitespace,
  unclassifiable constructs, parse-error regions). Each segment
  scroll = one '#phcc-member' header line (kind/name/form/span/
  sha256 of payload) + the segment's exact bytes.
- Reassembly = concatenate segment payloads in scroll order; the
  Volume-2 scroll is never consulted. Exit test for this volume:
  558/558 files byte-identical after reassembly, then the
  reassembled tree builds and passes upstream's suite on the ranch.

Meta Volume 3, Book 10, Chapter 1: Sec 1 = rebind manifest (Volume-2
file address -> member addresses; Slice 1/2 receipts are NOT
rewritten — this mapping is what a later pass re-binds them with),
Sec 2 = these notes, Sec 3 = degradation register (files kept
file-level, and partial files, each with its reason).
"""


def main():
    ap = argparse.ArgumentParser()
    home = os.path.expanduser("~")
    w = os.path.join(home, "workspace/phcc-slice3-granularity")
    ap.add_argument("--base", default=os.path.join(home, "workspace/phcc-slice2/phcc.phext"))
    ap.add_argument("--out", default=os.path.join(w, "phcc-fn.phext"))
    ap.add_argument("--stats", default=os.path.join(w, "logs/granularity-stats.json"))
    a = ap.parse_args()

    base_bytes = open(a.base, "rb").read()
    scrolls = dict(walk_bytes(base_bytes))
    # byte-identity of the inherited base under re-emission — the
    # additive claim stands or falls on this check.
    assert implode(scrolls) == base_bytes, "BASE ROUND-TRIP FAILED: implode(walk(base)) != base"
    print(f"base: {len(base_bytes)} bytes, {len(scrolls)} scrolls, re-emission byte-identical OK")

    man_coord = (1, 1, 1, 1, 2, 10, 1, 1, 1)
    entries = []
    for line in scrolls[man_coord].decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        path, coord_s, sha, size, mode = line.split("\t")
        entries.append({"path": path, "coord": parse_coord(coord_s),
                        "sha": sha, "size": int(size), "mode": mode})
    print(f"manifest: {len(entries)} files")

    new_scrolls = {}
    map_lines = ["# phcc rebind manifest — importer v3 (Volume 2 file address -> Volume 3 member addresses)",
                 "# base phext: Slice 2 phcc.phext sha256 " + sha256(base_bytes),
                 "# columns: path <TAB> vol2-coordinate <TAB> member-coordinate <TAB> kind <TAB> name <TAB> form <TAB> span <TAB> sha256"]
    reg_lines = ["# degradation register — importer v3",
                 "# columns: path <TAB> status <TAB> reason"]
    stats = {"files_total": len(entries), "files_structured": 0, "files_file_level": 0,
             "files_partial": 0, "members": {"function": 0, "type": 0, "object": 0},
             "segments_total": 0, "gap_segments": 0, "per_book": {},
             "largest_member": None, "smallest_member": None, "degraded": [], "partial": []}

    for e in entries:
        path, v2 = e["path"], e["coord"]
        data = scrolls[v2]
        assert sha256(data) == e["sha"], f"base scroll hash mismatch: {path}"
        book, chapter, section = v2[5], v2[6], v2[7]
        ext = os.path.splitext(path)[1].lower()
        if ext not in C_EXTS:
            reg_lines.append(f"{path}\tfile-level\tnot C source (extension '{ext or 'none'}'); bridge path only")
            map_lines.append(f"# file\t{path}\t{fmt(v2)}\tfile-level (not C source)")
            stats["files_file_level"] += 1
            stats["degraded"].append({"path": path, "reason": f"non-C extension {ext or 'none'}"})
            continue
        segments, n_members, err_bytes = segment_file(data)
        if n_members == 0:
            from collections import Counter
            dom = Counter(n.type for n in top_level_nodes(PARSER.parse(data).root_node)).most_common(1)
            hint = f"dominant top-level node: {dom[0][0]} x{dom[0][1]}" if dom else "empty parse"
            reg_lines.append(f"{path}\tfile-level\tzero members extracted ({hint}); bridge path only")
            map_lines.append(f"# file\t{path}\t{fmt(v2)}\tfile-level (zero members extracted)")
            stats["files_file_level"] += 1
            stats["degraded"].append({"path": path, "reason": f"zero members extracted ({hint})"})
            continue

        err_pct = 100.0 * err_bytes / max(len(data), 1)
        partial = err_bytes > 0
        if partial:
            stats["files_partial"] += 1
            reg_lines.append(f"{path}\tpartial\ttree-sitter error regions cover {err_bytes} bytes ({err_pct:.1f}%); unclassified bytes are gap segments")
            stats["partial"].append({"path": path, "error_bytes": err_bytes, "error_pct": round(err_pct, 1)})
        stats["files_structured"] += 1
        bk = stats["per_book"].setdefault(str(book), {"files": 0, "function": 0, "type": 0, "object": 0})
        bk["files"] += 1

        idx_coord = (1, 1, 1, 4, 3, book, chapter, section, 1)
        idx_lines = [f"# phcc file index — importer v3",
                     f"# path: {path}",
                     f"# volume2: {fmt(v2)}",
                     f"# sha256: {e['sha']}  size: {len(data)}",
                     f"# parse: {TS_VERSION}; members={n_members} error-bytes={err_bytes} ({err_pct:.1f}%)",
                     "# columns: scroll <TAB> kind <TAB> name <TAB> form <TAB> span <TAB> sha256"]
        map_lines.append(f"# file\t{path}\t{fmt(v2)}\tindex {fmt(idx_coord)}")
        for i, (kind, name, form, s, en) in enumerate(segments):
            scr = i + 2
            payload = data[s:en]
            psha = sha256(payload)
            header = f"#phcc-member\tkind={kind}\tname={name}\tform={form}\tspan={s}-{en}\tsha256={psha}\n".encode()
            new_scrolls[(1, 1, 1, 4, 3, book, chapter, section, scr)] = header + payload
            idx_lines.append(f"{scr}\t{kind}\t{name}\t{form}\t{s}-{en}\t{psha}")
            stats["segments_total"] += 1
            if kind == "gap":
                stats["gap_segments"] += 1
            else:
                stats["members"][kind] += 1
                bk[kind] += 1
                mcoord = (1, 1, 1, 4, 3, book, chapter, section, scr)
                map_lines.append(f"{path}\t{fmt(v2)}\t{fmt(mcoord)}\t{kind}\t{name}\t{form}\t{s}-{en}\t{psha}")
                size = en - s
                if stats["largest_member"] is None or size > stats["largest_member"]["size"]:
                    stats["largest_member"] = {"path": path, "name": name, "kind": kind, "size": size}
                if stats["smallest_member"] is None or size < stats["smallest_member"]["size"]:
                    stats["smallest_member"] = {"path": path, "name": name, "kind": kind, "size": size}
        new_scrolls[idx_coord] = ("\n".join(idx_lines) + "\n").encode()

    new_scrolls[(1, 1, 1, 1, 3, 10, 1, 1, 1)] = ("\n".join(map_lines) + "\n").encode()
    new_scrolls[(1, 1, 1, 1, 3, 10, 1, 2, 1)] = LAYOUT_NOTES.encode()
    new_scrolls[(1, 1, 1, 1, 3, 10, 1, 3, 1)] = ("\n".join(reg_lines) + "\n").encode()

    merged = dict(scrolls)
    for k, v in new_scrolls.items():
        assert k not in merged, f"coordinate collision with inherited scroll: {k}"
        merged[k] = v
    blob = implode(merged)
    with open(a.out, "wb") as f:
        f.write(blob)
    # verify inheritance on the written artifact itself
    back = dict(walk_bytes(blob))
    bad = [k for k, v in scrolls.items() if back.get(k) != v]
    assert not bad, f"inherited scrolls altered: {bad[:3]}"
    bad_new = [k for k, v in new_scrolls.items() if back.get(k) != v]
    assert not bad_new, f"added scrolls altered/missing: {bad_new[:3]}"
    # NB: walk counts structural empty scrolls (consecutive delimiters
    # when several levels advance at once) — present in the base too;
    # content equality above, not raw counts, is the invariant.
    print(f"output: {a.out}  {len(blob)} bytes  sha256 {sha256(blob)}")
    print(f"scrolls: {len(back)} total ({len(new_scrolls)} added); inherited byte-identical OK")
    print(json.dumps({k: v for k, v in stats.items() if k not in ("degraded", "partial")}, indent=1))
    print(f"degraded: {len(stats['degraded'])}  partial: {len(stats['partial'])}")
    with open(a.stats, "w") as f:
        json.dump(stats, f, indent=1)


if __name__ == "__main__":
    main()
