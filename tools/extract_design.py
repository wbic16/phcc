#!/usr/bin/env python3
"""extract_design.py — phcc Slice 3 structure extractor (design §A.1).

Generates Design-phase (Collection 3) Scroll-1 views for phcc
artifacts and places them, additively, into a copy of the base phext
(Slice 3 granularity output, phcc-fn.phext). Every inherited scroll is
byte-identical in the output; the base file is never modified.

A view is DERIVED, never hand-written:
  - members (functions / types / objects, with signatures and struct
    fields) come from the Volume 3 member structure placed by
    importer v3 — segment payloads are consumed, never re-parsed
    from files. Segment payload hashes are re-verified against the
    Vol 3 index table while reading.
  - type definitions the granularity pass left inside gap segments
    (its classifier returns None for some multi-struct regions —
    e.g. struct TCCState in tcc.h) are recovered by a brace-matching
    scan of the gap payloads and are LABELLED "recovered from gap"
    in the view. Recovery is part of extraction, recorded here and
    in the register scroll, not hidden.
  - files that stayed file-level in Vol 3 (the Vol 2 bridge) get a
    view derived from the bridge scroll alone: includes/dependencies
    plus an explicit "no member structure" statement. Non-C files
    get no view (recorded in the register).

Each generated view carries, in its header, the SHA-256 of the Vol 2
Source scroll it was generated from and a digest of the Vol 3
segment scrolls it consumed — the staleness binding the gate checks
(design §A.1: a view whose recorded hash != current Source hash is
stale). The generator owns Scroll 1 only; Scroll 2+ at a Design
address is human commentary and is never touched (an existing
Scroll 1 that is not a generated view aborts the run).

Also placed:
  - the §A.2 pipeline interaction view at Design, Vol 2, Book 10,
    Ch 1, Sec 90 (a project section used by no artifact — asserted).
    Its names/edges block is machine-checked by check_pipeline.py.
  - a generator register at Meta, Vol 2, Book 10, Ch 1, Sec 8:
    coverage per Book, integrity results, and the extractor's blind
    spots (the §A.1 trust-ledger entry for a ctags-grade extractor).

Stdlib only. Usage:
  extract_design.py [--base PHEXT] [--out PHEXT] [--books 1,2,3]
                    [--stats JSON]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

GENERATOR = "extract_design.py 1.0.0 (slice3)"
PIPELINE_COORD = (1, 1, 1, 3, 2, 10, 1, 90, 1)   # Design, Vol 2, B10 Ch1 Sec 90
REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 8, 1)    # Meta, Vol 2, B10 Ch1 Sec 8
C_EXTS = {".c", ".h"}
BOOK_NAMES = {1: "Driver & public API", 2: "Preprocessor & tokenizer",
              3: "Parser & codegen core", 4: "Assembler",
              5: "Object formats & linker", 6: "Target backends",
              7: "Runtime & execution", 8: "Debug info & tools",
              9: "Shipped headers", 10: "Build & project"}
KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "case",
            "do", "else", "defined", "typedef", "struct", "union", "enum"}
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
INCLUDE_RE = re.compile(r"^[ \t]*#[ \t]*include[ \t]*([<\"])([^>\"]+)[>\"]",
                        re.M)
COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def sha(b):
    return phext_io.sha256(b)


def collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def strip_comments(text):
    return COMMENT_RE.sub(" ", text)


def trunc(s, n=240):
    return s if len(s) <= n else s[:n - 3] + "..."


# ------------------------------------------------------------------ Vol 3
def read_vol3(scrolls, b, ch, sec):
    """Return (segments, index_coord, digest) or None if the file
    stayed file-level. segments: list of dicts in scroll order with
    kind/name/form/span/payload. Verifies each payload's SHA-256
    against the index table; raises on mismatch."""
    idx_coord = (1, 1, 1, 4, 3, b, ch, sec, 1)
    raw = scrolls.get(idx_coord)
    if not raw:
        return None
    segs = []
    digest = hashlib.sha256()
    for line in raw.decode("utf-8", "replace").splitlines():
        p = line.split("\t")
        if len(p) != 6 or not p[0].isdigit():
            continue
        scr = int(p[0])
        seg_coord = (1, 1, 1, 4, 3, b, ch, sec, scr)
        seg_raw = scrolls[seg_coord]
        digest.update(seg_raw)
        payload = seg_raw.split(b"\n", 1)[1]
        if sha(payload) != p[5]:
            raise AssertionError(
                f"Vol 3 payload hash mismatch at {phext_io.fmt(seg_coord)}")
        segs.append({"scroll": scr, "kind": p[1], "name": p[2],
                     "form": p[3], "span": p[4], "payload": payload})
    return segs, idx_coord, digest.hexdigest()


# ------------------------------------------------------- gap type recovery
def brace_body(text, open_idx):
    """text[open_idx] == '{'; return (body, end_idx_after_close)."""
    depth = 0
    i = open_idx
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i], i + 1
        i += 1
    return None, len(text)


def split_fields(body):
    """Split a struct/union/enum body at top-level ';'."""
    fields, depth, cur = [], 0, []
    for c in body:
        if c in "{(":
            depth += 1
        elif c in "})":
            depth -= 1
        if c == ";" and depth == 0:
            f = collapse("".join(cur))
            if f and not f.startswith("#"):
                fields.append(f)
            cur = []
        else:
            cur.append(c)
    tail = collapse("".join(cur))
    if tail and not tail.startswith("#"):
        fields.append(tail)
    return fields


TYPE_HEAD_RE = re.compile(
    r"(?:^|\n)[ \t]*(typedef[ \t]+)?(struct|union|enum)[ \t]+"
    r"([A-Za-z_]\w*)?[ \t]*\{")


def recover_types(gap_text):
    """Find struct/union/enum definitions in gap text. Returns a list
    of dicts like member types: name (tag or typedef alias), form,
    fields, decl (collapsed full text)."""
    out = []
    text = strip_comments(gap_text)
    for m in TYPE_HEAD_RE.finditer(text):
        open_idx = text.index("{", m.start())
        body, end = brace_body(text, open_idx)
        if body is None:
            continue
        # after the closing brace: optional declarator names up to ';'
        tail = text[end:end + 120]
        semi = tail.find(";")
        if semi < 0:
            continue
        declarators = collapse(tail[:semi])
        decl = collapse(text[m.start():end + semi + 1])
        kind = m.group(2)
        tag = m.group(3)
        if m.group(1):  # typedef ... { } Alias;
            name = declarators.split(",")[0].strip().lstrip("*").strip()
            name = name or tag or "?"
            form = "typedef"
        else:
            name = tag or declarators.split(",")[0].strip() or "?"
            form = kind
        out.append({"kind": "type", "name": name, "form": form,
                    "fields": split_fields(body), "decl": trunc(decl, 400),
                    "recovered": True})
    return out


# ------------------------------------------------------------- signatures
def signature(payload_text, form):
    t = strip_comments(payload_text)
    if form == "def":
        i = t.find("{")
        sig = t[:i] if i >= 0 else t
    else:
        i = t.find(";")
        sig = t[:i] if i >= 0 else t
    return trunc(collapse(sig))


def is_static(sig):
    # Only a leading `static` token counts. ST_FUNC / ST_INLN are
    # visibility/inline macros in this codebase, not linkage: the
    # ST_FUNC functions are exactly the cross-module internal API
    # (e.g. tccgen_compile, called from libtcc.c), so treating them
    # as static would hide the artifact's real exports.
    return bool(re.match(r"\s*static\b", sig))


def type_fields(payload_text):
    t = strip_comments(payload_text)
    i = t.find("{")
    if i < 0:
        return None
    body, _ = brace_body(t, i)
    if body is None:
        return None
    return split_fields(body)


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    home = os.path.expanduser("~")
    ap.add_argument("--base",
                    default=os.path.join(home, "workspace/phcc-slice3-granularity/phcc-fn.phext"))
    ap.add_argument("--out",
                    default=os.path.join(home, "workspace/phcc-slice3/phcc.design.phext"))
    ap.add_argument("--books", default=None,
                    help="comma list; default = all books")
    ap.add_argument("--stats",
                    default=os.path.join(home, "workspace/phcc-slice3/logs/design-stats.json"))
    a = ap.parse_args()
    books = None
    if a.books:
        books = {int(x) for x in a.books.split(",")}

    base_bytes = open(a.base, "rb").read()
    scrolls = phext_io.load_phext(a.base)
    assert phext_io.implode(scrolls) == base_bytes, "BASE ROUND-TRIP FAILED"
    print(f"base: {len(base_bytes)} bytes sha256 {sha(base_bytes)[:16]}... "
          f"round-trip OK")

    manifest = phext_io.parse_manifest(scrolls)
    artifacts = sorted(manifest.items())  # (path, vol2 Source coord)

    # ---- pass 1: read members for every artifact, build universes
    per_file = {}
    func_universe = defaultdict(list)    # name -> [(path, form)]
    global_universe = set()
    for path, coord in artifacts:
        b, ch, sec = coord[5], coord[6], coord[7]
        src = scrolls[coord]
        info = {"path": path, "coord": coord, "book": b,
                "src_sha": sha(src), "src": src,
                "members": [], "gaps": [], "vol3": None,
                "members_digest": None, "recovered": []}
        v3 = read_vol3(scrolls, b, ch, sec)
        if v3 is not None:
            segs, idx_coord, digest = v3
            info["vol3"] = idx_coord
            info["members_digest"] = digest
            gap_text = []
            for s in segs:
                if s["kind"] == "gap":
                    info["gaps"].append(s)
                    gap_text.append(s["payload"].decode("utf-8", "replace"))
                else:
                    info["members"].append(s)
            info["recovered"] = recover_types("\n".join(gap_text))
        per_file[path] = info
        for m in info["members"]:
            if m["kind"] == "function":
                for nm in m["name"].split(","):
                    func_universe[nm.strip()].append((path, m["form"]))
            elif m["kind"] == "object" and m["form"] == "global":
                for nm in m["name"].split(","):
                    global_universe.add(nm.strip())
    # tcc.h declared names (for Book 6 "core hooks" section)
    tcch_decls = set()
    if "tcc.h" in per_file:
        for m in per_file["tcc.h"]["members"]:
            if m["kind"] == "function" and m["form"] == "decl":
                tcch_decls.update(n.strip() for n in m["name"].split(","))

    # ---- pass 2: derive views
    new_scrolls = {}
    stats = {"books": {}, "views": 0, "skipped_nonc": [], "file_level": [],
             "recovered_types": 0, "members_total": 0}
    for path, coord in artifacts:
        info = per_file[path]
        b = info["book"]
        if books is not None and b not in books:
            continue
        ext = os.path.splitext(path)[1].lower()
        bs = stats["books"].setdefault(
            str(b), {"artifacts": 0, "views": 0, "functions": 0,
                     "types": 0, "objects": 0, "recovered": 0})
        bs["artifacts"] += 1
        if ext not in C_EXTS:
            stats["skipped_nonc"].append(path)
            continue
        if info["vol3"] is None:
            stats["file_level"].append(path)
        view = render_view(info, per_file, func_universe, global_universe,
                           tcch_decls)
        dcoord = (1, 1, 1, 3, 2, coord[5], coord[6], coord[7], 1)
        existing = scrolls.get(dcoord)
        if existing:
            if not existing.startswith(b"GENERATED"):
                raise AssertionError(
                    f"Design Scroll 1 at {phext_io.fmt(dcoord)} is not a "
                    f"generated view — refusing to overwrite")
        new_scrolls[dcoord] = view
        stats["views"] += 1
        bs["views"] += 1
        nf = sum(1 for m in info["members"] if m["kind"] == "function")
        nt = sum(1 for m in info["members"] if m["kind"] == "type")
        no = sum(1 for m in info["members"] if m["kind"] == "object")
        bs["functions"] += nf
        bs["types"] += nt + len(info["recovered"])
        bs["objects"] += no
        bs["recovered"] += len(info["recovered"])
        stats["recovered_types"] += len(info["recovered"])
        stats["members_total"] += len(info["members"])

    # ---- pipeline view + register (only on a full run)
    if books is None:
        assert (10, 1, 90) not in {(c[5], c[6], c[7])
                                   for _, c in artifacts}, \
            "pipeline section collides with an artifact address"
        new_scrolls[PIPELINE_COORD] = PIPELINE_VIEW.encode()
        new_scrolls[REGISTER_COORD] = render_register(
            stats, base_bytes, per_file).encode()

    merged = dict(scrolls)
    for k, v in new_scrolls.items():
        old = merged.get(k)
        if old and not old.startswith(b"GENERATED") and k != REGISTER_COORD:
            raise AssertionError(f"refusing to overwrite non-generated "
                                 f"scroll {phext_io.fmt(k)}")
        merged[k] = v
    blob = phext_io.implode(merged)
    with open(a.out, "wb") as f:
        f.write(blob)
    back = phext_io.load_phext(a.out)
    # Inherited scrolls must be byte-identical EXCEPT the ones this
    # generator owns and has just replaced (generated Design Scroll
    # 1s, the pipeline view, the register — overwriting those was
    # guarded above: a non-GENERATED scroll at a target coordinate
    # aborts the run). On a fresh base (the shipped run) the owned
    # set starts empty, so the additive guarantee is unqualified.
    bad = [k for k, v in scrolls.items()
           if len(v) > 0 and k not in new_scrolls and back.get(k) != v]
    assert not bad, f"inherited scrolls altered: {bad[:3]}"
    bad_new = [k for k, v in new_scrolls.items() if back.get(k) != v]
    assert not bad_new, f"added scrolls altered/missing: {bad_new[:3]}"
    print(f"output: {a.out}  {len(blob)} bytes  sha256 {sha(blob)}")
    print(f"views placed: {stats['views']}; recovered types: "
          f"{stats['recovered_types']}; file-level C views: "
          f"{len(stats['file_level'])}; non-C skipped: "
          f"{len(stats['skipped_nonc'])}")
    print(json.dumps(stats["books"], indent=1))
    with open(a.stats, "w") as f:
        json.dump(stats, f, indent=1)


# ------------------------------------------------------------------ views
def render_view(info, per_file, func_universe, global_universe, tcch_decls):
    path, coord, b = info["path"], info["coord"], info["book"]
    src_text = info["src"].decode("utf-8", "replace")
    L = []
    L.append("GENERATED — phcc Design view (design §A.1). Machine-owned "
             "Scroll 1; human commentary belongs on Scroll 2+, never "
             "overwritten by the generator.")
    L.append(f"generator: {GENERATOR}")
    L.append(f"artifact: {path}")
    L.append(f"book: {b} ({BOOK_NAMES[b]})")
    L.append(f"source-scroll: {phext_io.fmt(coord)}")
    L.append(f"source-sha256: {info['src_sha']}")
    if info["vol3"] is not None:
        L.append(f"vol3-index: {phext_io.fmt(info['vol3'])}")
        L.append(f"members-sha256: {info['members_digest']}")
    else:
        L.append("vol3-index: none (file stayed file-level in Vol 3; "
                 "view derived from the Vol 2 bridge scroll only)")
        L.append("members-sha256: none")
    L.append("")
    members = info["members"]
    funcs = [m for m in members if m["kind"] == "function"]
    types = [m for m in members if m["kind"] == "type"]
    objs = [m for m in members if m["kind"] == "object"]
    L.append("## summary")
    L.append(f"members from Vol 3: {len(funcs)} functions, {len(types)} "
             f"types, {len(objs)} objects; {len(info['gaps'])} gap "
             f"segments; {len(info['recovered'])} types recovered from "
             f"gap segments (labelled below).")
    if info["vol3"] is None:
        L.append("No Vol 3 member structure exists for this file "
                 "(importer v3 found no file-scope members, or the "
                 "file is a declaration-free header). Structure below "
                 "is limited to includes/dependencies.")
    L.append("")

    # signatures + staticness per function member
    sigs = {}
    for m in funcs + types + objs:
        text = m["payload"].decode("utf-8", "replace")
        m["_text"] = text
    for m in funcs:
        m["_sig"] = signature(m["_text"], m["form"])
        m["_static"] = is_static(m["_sig"])

    # exports
    L.append("## exports (non-static members)")
    n_exp = 0
    for m in funcs:
        if not m["_static"]:
            L.append(f"function\t{m['name']}\t{m['_sig']}")
            n_exp += 1
    for m in types:
        L.append(f"type\t{m['name']}\t({m['form']})")
        n_exp += 1
    for m in objs:
        decl = trunc(collapse(strip_comments(m["_text"]).split(";")[0]))
        if m["form"] == "macro":
            decl = trunc(collapse(m["_text"].split("\n")[0]))
        if not is_static(decl):
            L.append(f"object\t{m['name']}\t{decl}")
            n_exp += 1
    if n_exp == 0:
        L.append("(none)")
    L.append("")

    # core hooks for Book 6 backends
    if b == 6 and tcch_decls:
        hooks = sorted({m["name"] for m in funcs if m["form"] == "def"
                        and m["name"] in tcch_decls})
        if hooks:
            L.append("## core hooks implemented (declared in tcc.h, "
                     "defined here)")
            for h in hooks:
                L.append(f"- {h}")
            L.append("")

    # types with fields
    L.append("## types")
    all_types = list(types)
    for t in info["recovered"]:
        all_types.append(t)
    if not all_types:
        L.append("(no type definitions extracted)")
    for m in all_types:
        recovered = m.get("recovered", False)
        mark = " [recovered from gap segment]" if recovered else ""
        L.append(f"### {m['form']} {m['name']}{mark}")
        if recovered:
            L.append(f"declaration: {m['decl']}")
            fields = m["fields"]
        else:
            fields = type_fields(m["_text"])
            if fields is None:
                L.append(f"declaration: "
                         f"{trunc(collapse(strip_comments(m['_text'])))}")
        if fields:
            L.append("fields:")
            for f in fields:
                L.append(f"- {trunc(f, 200)}")
        L.append("")

    # functions with signatures + calls
    L.append("## functions")
    if not funcs:
        L.append("(no function members extracted)")
    file_globals_ref = set()
    for m in funcs:
        st = ", static" if m["_static"] else ""
        L.append(f"### {m['name']} ({m['form']}{st})")
        L.append(f"signature: {m['_sig']}")
        if m["form"] == "def":
            called = sorted({c for c in CALL_RE.findall(m["_text"])
                             if c in func_universe and c not in KEYWORDS
                             and c != m["name"]})
            if called:
                shown = called[:40]
                extra = f" (+{len(called) - 40} more)" \
                    if len(called) > 40 else ""
                L.append(f"calls: {', '.join(shown)}{extra}")
            refs = {w for w in re.findall(r"\b([A-Za-z_]\w*)\b",
                                          m["_text"])
                    if w in global_universe}
            file_globals_ref |= refs
        L.append("")

    # objects
    L.append("## objects")
    if not objs:
        L.append("(no object members extracted)")
    for m in objs:
        if m["form"] == "macro":
            decl = trunc(collapse(m["_text"].split("\n")[0]), 160)
        else:
            decl = trunc(collapse(strip_comments(m["_text"]).split(";")[0]),
                         160)
        L.append(f"- {m['name']} ({m['form']}): {decl}")
    L.append("")

    # globals referenced
    L.append("## globals referenced by this file's function bodies")
    L.append("(ctags-grade: identifier match against the tree-wide "
             "file-scope object set; reads and writes are NOT "
             "distinguished — extractor limitation, register scroll)")
    if file_globals_ref:
        names = sorted(file_globals_ref)
        shown = names[:60]
        extra = f" (+{len(names) - 60} more)" if len(names) > 60 else ""
        L.append(", ".join(shown) + extra)
    else:
        L.append("(none identified)")
    L.append("")

    # includes / dependencies
    L.append("## includes / dependencies")
    incs = INCLUDE_RE.findall(src_text)
    if not incs:
        L.append("(no #include lines)")
    by_base = defaultdict(list)
    for pth, c in per_file.items():
        by_base[os.path.basename(pth)].append((pth, c))
    for q, name in incs:
        if q == "<":
            L.append(f"- <{name}> (system header)")
        else:
            cands = by_base.get(os.path.basename(name), [])
            if len(cands) == 1:
                pth, c = cands[0]
                L.append(f"- \"{name}\" -> {pth} "
                         f"({phext_io.fmt(c['coord'])})")
            elif len(cands) > 1:
                where = ", ".join(f"{p} ({phext_io.fmt(c['coord'])})"
                                  for p, c in cands)
                L.append(f"- \"{name}\" -> ambiguous: {where}")
            else:
                L.append(f"- \"{name}\" (not placed in this phext)")
    L.append("")

    # outgoing call edges, cross-file
    L.append("## call edges (cross-file, extractor-derived)")
    edges = defaultdict(set)
    for m in funcs:
        if m["form"] != "def":
            continue
        for cname in CALL_RE.findall(m["_text"]):
            if cname in KEYWORDS or cname == m["name"]:
                continue
            for (pth, form) in func_universe.get(cname, []):
                if pth != path and form == "def":
                    edges[cname].add(pth)
    if not edges:
        L.append("(no cross-file call edges identified)")
    for cname in sorted(edges):
        wheres = ", ".join(sorted(edges[cname]))
        L.append(f"- {cname} — defined in: {wheres}")
    L.append("")
    return ("\n".join(L) + "\n").encode()


def render_register(stats, base_bytes, per_file):
    L = []
    L.append("# Design register — Meta (Vol 2, Book 10), Slice 3 "
             "(2026-11-07)")
    L.append(f"generator: {GENERATOR}")
    L.append(f"base phext: phcc-fn.phext (Slice 3 granularity output) "
             f"sha256 {sha(base_bytes)}")
    L.append("")
    L.append("Design Scroll-1 views placed (Collection 3, Volume 2) at "
             "the 5D address of each C artifact (.c/.h). Per-Book "
             "coverage:")
    for bk in sorted(stats["books"], key=int):
        s = stats["books"][bk]
        L.append(f"book {bk} ({BOOK_NAMES[int(bk)]}): {s['views']} views "
                 f"/ {s['artifacts']} artifacts; {s['functions']} "
                 f"functions, {s['types']} types, {s['objects']} objects"
                 f", {s['recovered']} gap-recovered types")
    L.append(f"total views: {stats['views']}")
    L.append(f"file-level C artifacts (view from bridge scroll only): "
             f"{len(stats['file_level'])}")
    for p in stats["file_level"]:
        L.append(f"file-level\t{p}")
    L.append(f"non-C artifacts (no view placed): "
             f"{len(stats['skipped_nonc'])}")
    L.append("")
    L.append("Pipeline interaction view (design §A.2): Design "
             f"{phext_io.fmt(PIPELINE_COORD)} — Book 10 Ch 1 Sec 90, a "
             "project section used by no artifact. Its names/edges "
             "claims are checked by tools/check_pipeline.py against "
             "the extractor-derived call graph.")
    L.append("")
    L.append("Extractor blind spots (design §A.1 trust-ledger entry "
             "for a ctags-grade extractor):")
    L.append("- Members come from importer v3's tree-sitter segment "
             "structure; bytes the granularity pass left in gap "
             "segments are invisible to the member walk except for "
             "the labelled type-recovery scan. Function definitions "
             "inside gap segments (partial-parse files) do NOT "
             "appear as members, in views, or in the call graph.")
    L.append("- Call edges are name-based: an identifier followed by "
             "'(' inside a function-definition payload, intersected "
             "with the tree-wide function set. Macro-expanded calls, "
             "calls through function pointers, and calls to functions "
             "with no member anywhere are invisible. Same-name "
             "functions in different files share an entry in the "
             "name universe; per-file edge lists disambiguate by "
             "defining path where known.")
    L.append("- Globals referenced = identifier match against "
             "file-scope object names; reads vs writes are not "
             "distinguished, and a local variable shadowing a global "
             "name is counted as a reference (false positives "
             "possible).")
    L.append("- Signatures are text up to the first '{' or ';' of "
             "the member payload, comments stripped, whitespace "
             "collapsed, truncated at 240 chars. K&R-style and "
             "heavily macro-generated declarations can render "
             "approximately.")
    L.append("- Static detection is a leading-`static`-token "
             "heuristic. ST_FUNC/ST_INLN are visibility/inline "
             "macros, not linkage, and are not treated as static.")
    L.append("- #include resolution is by basename against the "
             "placed tree; ambiguous basenames are listed as "
             "ambiguous, not guessed.")
    L.append("")
    return "\n".join(L) + "\n"


PIPELINE_VIEW = """GENERATED — phcc pipeline interaction view (design §A.2).
System view, not an artifact view: it lives at the project address
(Book 10, Ch 1, Sec 90 — a section used by no artifact) and carries
no Source-hash binding. Its factual claims are the names/edges block
at the end, machine-checked by tools/check_pipeline.py against the
extractor-derived call graph; the prose around it is orientation
for a new reader.

# The phcc/TinyCC compile pipeline, on one page

    main (tcc.c, Book 1)
      |  tcc_new                create the TCCState
      |  tcc_add_file           queue each input file
      v
    tcc_add_file_internal (libtcc.c, Book 1)
      |  tcc_compile            one translation unit, start to finish
      v
    tcc_compile (libtcc.c, Book 1)
      |-- tcc_preprocess (tccpp.c, Book 2)   preprocess-only mode (-E)
      |-- tccelf_begin_file (tccelf.c, Book 5)  open the object output
      |-- tcc_assemble (tccasm.c, Book 4)    .s inputs bypass codegen
      v
    tccgen_compile (tccgen.c, Book 3)
      |  next (tccpp.c, Book 2)   the token stream, pulled one token
      |                           at a time by the parser
      |  decl (tccgen.c, Book 3)  parse one external declaration;
      |                           code is emitted as it is parsed —
      |                           TinyCC has no AST and no IR pass
      v
    gen_opl (tccgen.c, Book 3)
      |  gfunc_call               the backend hook: emitted by the
      v                           shared code generator, defined per
    gfunc_call (*-gen.c, Book 6)  architecture in every *-gen.c

    main (tcc.c, Book 1)
      |-- tcc_output_file (tccelf.c, Book 5)
      |     elf_output_file       lay out sections, resolve symbols,
      |                           write the ELF object/executable
      |-- tcc_run (tccrun.c, Book 7)
            tcc_relocate          relocate in memory, then control
                                  passes to the program's entry point
                                  through a function pointer — that
                                  final hop is pointer-dispatched and
                                  is therefore NOT one of the checked
                                  edges below.

Reading notes for the new contributor: the pipeline is a pull
pipeline. tccgen_compile does not receive a token array; it calls
next() itself, so the preprocessor (Book 2) and the parser/codegen
(Book 3) are interleaved in time, and the value stack in tccgen.c is
where the two meet. Object output is split oddly on purpose:
tcc_compile opens the file (tccelf_begin_file) before codegen runs,
and tcc_output_file — called from main, not from tcc_compile —
finishes it after all inputs are queued.

## machine-checked claims (check_pipeline.py)
names:
- main @ tcc.c
- tcc_new @ libtcc.c
- tcc_add_file @ libtcc.c
- tcc_add_file_internal @ libtcc.c
- tcc_compile @ libtcc.c
- tcc_preprocess @ tccpp.c
- next @ tccpp.c
- tccgen_compile @ tccgen.c
- decl @ tccgen.c
- gen_opl @ tccgen.c
- gfunc_call @ x86_64-gen.c
- tcc_assemble @ tccasm.c
- tccelf_begin_file @ tccelf.c
- tcc_output_file @ tccelf.c
- elf_output_file @ tccelf.c
- tcc_run @ tccrun.c
- tcc_relocate @ tccrun.c
edges:
- tcc.c: main -> tcc_new
- tcc.c: main -> tcc_add_file
- tcc.c: main -> tcc_output_file
- tcc.c: main -> tcc_run
- libtcc.c: tcc_add_file -> tcc_add_file_internal
- libtcc.c: tcc_add_file_internal -> tcc_compile
- libtcc.c: tcc_compile -> tcc_preprocess
- libtcc.c: tcc_compile -> tccgen_compile
- libtcc.c: tcc_compile -> tccelf_begin_file
- libtcc.c: tcc_compile -> tcc_assemble
- tccpp.c: tcc_preprocess -> next
- tccgen.c: tccgen_compile -> next
- tccgen.c: tccgen_compile -> decl
- tccgen.c: gen_opl -> gfunc_call
- tccelf.c: tcc_output_file -> elf_output_file
- tccrun.c: tcc_run -> tcc_relocate
"""


if __name__ == "__main__":
    main()
