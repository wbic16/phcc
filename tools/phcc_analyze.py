#!/usr/bin/env python3
"""phcc_analyze.py — duplication census + automatic de-duplication.

User-facing interface (Will's ruling, 2026-11-07 — "add an analysis
mode for automatic de-duplication"):

    phcc analyze --phext X.phext [--out REPORT]
    phcc analyze --phext X.phext --apply --out Y.phext [--report R]
    phcc analyze --phext X.phext --statements [--out REPORT]
    phcc analyze --phext X.phext --build-stmt --out Y.phext [--report R]
    phcc analyze --phext Y.phext --verify-stmt [--out REPORT]

The statement tier (--statements / --build-stmt / --verify-stmt)
re-expresses the corpus at statement grain: segment payloads are
split into statement-grain segments, each distinct statement core
is held once in a statement library at a content-derived
coordinate, and member scrolls become ordered reference
sequences. See the statement-tier section below and METHODS.md.

Census (default) is read-only and has two tiers:

  EXACT — cluster by payload SHA-256. Two granularities: Volume 3
  segment payloads (the importer's per-member hashes, reused from
  the file indexes and verified against recomputation — a mismatch
  is reported, never silently trusted), and whole scrolls for every
  scroll that is not a Volume 3 segment/index. Bytes duplicated in
  a cluster of n copies of size s is (n-1)*s.

  NEAR (report-only) — for Source members (segment kinds function /
  type / object), a normalized hash: C comments stripped by a
  string/char-aware scanner, whitespace collapsed. A near cluster
  claims exactly "identical after normalization" — nothing fuzzier
  is asserted, and nothing in this tier is ever applied.

Apply (--apply) writes a NEW phext in which, per exact cluster, the
lowest-coordinate member stays canonical and every other member's
body is replaced by a dedup stub (phext_io dedup refs:
`#phcc-dedup-ref <coordinate> <sha256>`), the member header and
address kept intact. Two classes only, because those are the two
`phcc unpack` can expand: Volume 3 segment payloads and Volume 2
whole-file scrolls named by the placement manifest. Everything else
duplicated is census-only — no expansion path exists for it, and an
unexpandable rewrite would be lossy. Library-10000 build-region
scrolls and binary-format scrolls are excluded everywhere (they are
artifacts, already canonical base64); zero-byte payloads are never
stubbed (a stub is bigger than the payload).

SAFETY LAW: a rewrite is never silent about bindings. Apply lists
every receipt whose binding a rewrite invalidates as
DEMOTED-TO-STALE — proof receipts (Proofs collection), gate
verdicts, and Design views of touched files — because demotion to
STALE on a source edit is the tier system's designed response, and
hiding it is the one unforgivable outcome. Bindings are found by
scanning every scroll for the SHA-256 of a stubbed payload or a
touched file, plus the Design path rule and the standing fact that
the current gate verdict binds the Volume 3 members digest.

Stdlib only.
"""
import argparse, collections, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phext_io
from phext_io import (walk_bytes, implode, fmt, sha256, parse_coord,
                      parse_dedup_ref, dedup_ref)

BINARY_HEADER = b"phext-binary:1:base64"
REGION_LIBRARY = 10000
MEMBER_KINDS = ("function", "type", "object")
HEX64_RE = re.compile(rb"[0-9a-f]{64}")
HEADER_SHA_RE = re.compile(rb"sha256=([0-9a-f]{64})")


def load_scrolls(path):
    return dict(walk_bytes(open(path, "rb").read()))


def is_binary_scroll(content):
    return content == BINARY_HEADER or \
        content.startswith(BINARY_HEADER + b"\n")


# ------------------------------------------------------------ segments
def collect_segments(scrolls, entries):
    """Segment records for every manifest file with a Volume 3 index,
    identified by exactly unpack_vol3's rule (index magic + path +
    file hash), so analyze and unpack always mean the same segments.
    Each record: file entry, coord, kind/name/form/span, index_sha,
    header bytes (without the newline), header_sha, payload,
    recomputed sha, and a verify status."""
    segs, problems = [], []
    for e in entries:
        v2 = e["coord"]
        idx = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        raw_idx = scrolls.get(idx, b"")
        structured = raw_idx.startswith(b"# phcc file index") and \
            f"# path: {e['path']}\n".encode() in raw_idx and \
            f"# sha256: {e['sha']} ".encode() in raw_idx
        if not structured:
            continue
        for line in raw_idx.decode("utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            scr, kind, name, form, span, psha = line.split("\t")
            coord = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], int(scr))
            rec = {"path": e["path"], "file_coord": v2, "idx": idx,
                   "coord": coord, "kind": kind, "name": name,
                   "form": form, "span": span, "index_sha": psha,
                   "header": None, "header_sha": None, "payload": None,
                   "sha": None, "status": "ok"}
            seg = scrolls.get(coord)
            if seg is None or b"\n" not in seg:
                rec["status"] = "missing"
                problems.append(rec)
                segs.append(rec)
                continue
            rec["header"], rec["payload"] = seg.split(b"\n", 1)
            m = HEADER_SHA_RE.search(rec["header"])
            rec["header_sha"] = m.group(1).decode() if m else None
            rec["sha"] = sha256(rec["payload"])
            ref = parse_dedup_ref(rec["payload"])
            if ref is not None and ref[1] == psha \
                    and rec["header_sha"] == psha:
                # A dedup stub standing for exactly the payload the
                # index binds: verified by reference (unpack does
                # the deep verification against the target scroll).
                rec["ref"] = ref
            elif rec["sha"] != psha:
                rec["status"] = "index-mismatch"
                problems.append(rec)
            elif rec["header_sha"] != psha:
                rec["status"] = "header-mismatch"
                problems.append(rec)
            segs.append(rec)
    return segs, problems


# ------------------------------------------------------------ census
def normalize_code(data):
    """C-comment-stripped, whitespace-collapsed form of a member
    payload. The scanner is string/char aware (comment markers
    inside literals are content); each comment span becomes one
    space so token separation survives; then all whitespace runs
    collapse to one space. Two payloads with the same normalized
    hash are identical after normalization — that is the whole
    claim of the NEAR tier."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == 0x2F and i + 1 < n and data[i + 1] == 0x2F:      # //
            j = data.find(b"\n", i)
            i = n if j < 0 else j
            out.append(0x20)
        elif b == 0x2F and i + 1 < n and data[i + 1] == 0x2A:    # /*
            j = data.find(b"*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(0x20)
        elif b in (0x22, 0x27):                                   # " / '
            q = b
            out.append(b)
            i += 1
            while i < n:
                out.append(data[i])
                if data[i] == 0x5C and i + 1 < n:
                    out.append(data[i + 1])
                    i += 2
                    continue
                if data[i] == q:
                    i += 1
                    break
                i += 1
        else:
            out.append(b)
            i += 1
    return re.sub(rb"\s+", b" ", bytes(out)).strip()


def census(scrolls, entries, segs):
    """All census groupings. Returns a dict of tallies + clusters."""
    cz = {}
    seg_coords = {s["coord"] for s in segs}
    idx_coords = {s["idx"] for s in segs}
    coord_path = {e["coord"]: e["path"] for e in entries}

    # --- member tier (Volume 3 segment payloads)
    ref_coords = {s["coord"] for s in segs
                  if s["payload"] is not None
                  and parse_dedup_ref(s["payload"])}
    cz["refs_segments"] = [s for s in segs if s["coord"] in ref_coords]
    live = [s for s in segs if s["payload"] is not None
            and s["coord"] not in ref_coords]
    by_hash = collections.defaultdict(list)
    cz["empty_segments"] = 0
    for s in live:
        if len(s["payload"]) == 0:
            cz["empty_segments"] += 1
        else:
            by_hash[s["sha"]].append(s)
    cz["member_clusters"] = {h: ms for h, ms in by_hash.items()
                             if len(ms) > 1}
    # --- near tier (Source members, normalized)
    nby = collections.defaultdict(list)
    for s in live:
        if s["kind"] in MEMBER_KINDS and len(s["payload"]) > 0:
            nby[sha256(normalize_code(s["payload"]))].append(s)
    cz["near_clusters"] = {}
    for h, ms in nby.items():
        if len(ms) > 1 and len({s["sha"] for s in ms}) > 1:
            cz["near_clusters"][h] = ms
    # --- whole-scroll tier (everything that is not a segment/index)
    sby = collections.defaultdict(list)
    cz.update({"empty_scrolls": 0, "region_scrolls": 0,
               "region_bytes": 0, "binary_scrolls": 0,
               "binary_bytes": 0, "binary_dup_groups": 0,
               "refs_scrolls": []})
    binary_hashes = collections.Counter()
    for c, content in scrolls.items():
        if c in seg_coords or c in idx_coords:
            continue
        if c[0] == REGION_LIBRARY:
            cz["region_scrolls"] += 1
            cz["region_bytes"] += len(content)
            continue
        if len(content) == 0:
            cz["empty_scrolls"] += 1
            continue
        if is_binary_scroll(content):
            cz["binary_scrolls"] += 1
            cz["binary_bytes"] += len(content)
            binary_hashes[sha256(content)] += 1
            continue
        if parse_dedup_ref(content):
            cz["refs_scrolls"].append(c)
            continue
        sby[sha256(content)].append(c)
    cz["binary_dup_groups"] = sum(1 for v in binary_hashes.values()
                                  if v > 1)
    cz["scroll_clusters"] = {h: cs for h, cs in sby.items()
                              if len(cs) > 1}
    cz["coord_path"] = coord_path
    # A whole-scroll cluster is actionable (apply rewrites it) iff
    # every member is a manifest file scroll; anything else —
    # Volume 1 history, Tests placements, registers — has no
    # expansion path and stays census-only.
    cz["scroll_clusters_actionable"] = sum(
        1 for cs in cz["scroll_clusters"].values()
        if all(c in coord_path for c in cs))
    return cz


def cluster_stats(clusters, size_of):
    n = sum(len(v) for v in clusters.values())
    dup = sum((len(v) - 1) * size_of(h, v) for h, v in clusters.items())
    return n, dup


def first_line(content, limit=72):
    line = content.split(b"\n", 1)[0].decode("utf-8", "replace")
    return line[:limit]


def render_report(phext_path, raw, scrolls, entries, segs, problems,
                  cz, apply_info=None):
    L = []
    add = L.append
    add("# phcc analyze — duplication census")
    add("")
    add(f"- phext: {phext_path}")
    add(f"- phext bytes: {len(raw)}  sha256: {sha256(raw)}")
    add(f"- scrolls: {len(scrolls)} "
        f"(nonempty {sum(1 for v in scrolls.values() if v)})")
    add(f"- manifest files: {len(entries)}")
    nfiles = len({s['path'] for s in segs})
    add(f"- segments indexed: {len(segs)} across {nfiles} structured "
        f"files (identification rule: unpack_vol3's)")
    bad = collections.Counter(s["status"] for s in problems)
    add(f"- index hash verification: "
        f"{len(segs) - len(problems)}/{len(segs)} segment payloads "
        f"verify against their index + header SHA-256 (directly, "
        f"or by dedup reference to a payload that does)"
        + (f"; PROBLEMS: {dict(bad)}" if problems else ""))
    add("")
    add("## Totals")
    mn, mdup = cluster_stats(cz["member_clusters"],
                             lambda h, ms: len(ms[0]["payload"]))
    sn, sdup = cluster_stats(cz["scroll_clusters"],
                             lambda h, cs: len(scrolls[cs[0]]))
    add(f"- exact member clusters: {len(cz['member_clusters'])} "
        f"(members {mn}, bytes duplicated {mdup})")
    add(f"- exact whole-scroll clusters (non-segment): "
        f"{len(cz['scroll_clusters'])} (scrolls {sn}, "
        f"bytes duplicated {sdup}; manifest-file clusters "
        f"{cz['scroll_clusters_actionable']}, census-only "
        f"{len(cz['scroll_clusters']) - cz['scroll_clusters_actionable']})")
    add(f"- near clusters (report-only): {len(cz['near_clusters'])}")
    add(f"- dedup references already present: "
        f"{len(cz['refs_segments'])} segment, "
        f"{len(cz['refs_scrolls'])} whole-scroll")
    add(f"- excluded from de-duplication: Library-10000 region "
        f"({cz['region_scrolls']} scrolls, {cz['region_bytes']} B), "
        f"binary-format scrolls ({cz['binary_scrolls']}, "
        f"{cz['binary_bytes']} B, {cz['binary_dup_groups']} duplicate "
        f"groups among them), empty segments ({cz['empty_segments']}), "
        f"empty scrolls ({cz['empty_scrolls']})")
    add("")
    add("## EXACT — member payload clusters (largest first)")
    add("")
    ranked = sorted(cz["member_clusters"].items(),
                    key=lambda kv: -(len(kv[1]) - 1)
                    * len(kv[1][0]["payload"]))
    if not ranked:
        add("(none)")
    for h, ms in ranked[:25]:
        size = len(ms[0]["payload"])
        canon = min(s["coord"] for s in ms)
        add(f"### sha256 {h[:16]}… — {len(ms)} copies × {size} B "
            f"({(len(ms) - 1) * size} B duplicated)")
        for s in sorted(ms, key=lambda s: s["coord"])[:8]:
            mark = " (canonical)" if s["coord"] == canon else ""
            add(f"- {s['path']} :: {s['name']} [{s['kind']}/{s['form']}] "
                f"@ {fmt(s['coord'])}{mark}")
        if len(ms) > 8:
            add(f"- … and {len(ms) - 8} more")
        add("")
    add("## EXACT — whole-scroll clusters (non-segment scrolls)")
    add("")
    sranked = sorted(cz["scroll_clusters"].items(),
                     key=lambda kv: -(len(kv[1]) - 1)
                     * len(scrolls[kv[1][0]]))
    if not sranked:
        add("(none)")
    for h, cs in sranked[:25]:
        size = len(scrolls[cs[0]])
        tag = " — manifest-file cluster (apply rewrites)" if all(
            c in cz["coord_path"] for c in cs) else \
            " — census-only (no expansion path)"
        add(f"### sha256 {h[:16]}… — {len(cs)} copies × {size} B "
            f"({(len(cs) - 1) * size} B duplicated){tag}")
        for c in sorted(cs)[:8]:
            who = cz["coord_path"].get(c)
            label = f"file {who}" if who else \
                f"“{first_line(scrolls[c])}”"
            add(f"- {fmt(c)} — {label}")
        if len(cs) > 8:
            add(f"- … and {len(cs) - 8} more")
        add("")
    add("## NEAR — normalized member clusters (report-only)")
    add("")
    add("Basis: C comments stripped (string/char aware), whitespace "
        "collapsed; a cluster claims identical-after-normalization "
        "and nothing more. Never applied.")
    add("")
    nranked = sorted(cz["near_clusters"].items(),
                     key=lambda kv: -sum(len(s["payload"])
                                         for s in kv[1]))
    if not nranked:
        add("(none)")
    for h, ms in nranked[:20]:
        total = sum(len(s["payload"]) for s in ms)
        add(f"### normalized {h[:16]}… — {len(ms)} members, "
            f"{len({s['sha'] for s in ms})} distinct exact payloads, "
            f"{total} B total")
        for s in sorted(ms, key=lambda s: s["coord"])[:8]:
            add(f"- {s['path']} :: {s['name']} [{s['kind']}] "
                f"@ {fmt(s['coord'])} ({len(s['payload'])} B)")
        if len(ms) > 8:
            add(f"- … and {len(ms) - 8} more")
        add("")
    if problems:
        add("## Index verification problems")
        add("")
        for s in problems[:50]:
            add(f"- {s['path']} @ {fmt(s['coord'])}: {s['status']} "
                f"(index {s['index_sha'][:16]}…, "
                f"recomputed {(s['sha'] or '—')[:16]}…)")
        add("")
    if apply_info:
        L += render_apply(apply_info)
    return "\n".join(L) + "\n"


def render_apply(ai):
    L = []
    add = L.append
    add("## APPLY — automatic de-duplication")
    add("")
    add(f"- output phext: {ai['out']} ({ai['out_bytes']} B; "
        f"{ai['delta']:+d} B vs input)")
    add(f"- stubs written: {ai['seg_stubs']} segment, "
        f"{ai['file_stubs']} whole-file")
    add(f"- payload bytes replaced by stubs: {ai['replaced']} "
        f"(stub bytes written: {ai['stub_bytes']})")
    saving = [(p, s) for p, s in ai["stub_sizes"] if p > s]
    costing = [(p, s) for p, s in ai["stub_sizes"] if p <= s]
    add(f"- stub economics: {len(saving)} stubs replace more bytes "
        f"than they cost (net {sum(p - s for p, s in saving):+d} B); "
        f"{len(costing)} stubs replace payloads no larger than the "
        f"stub line itself (net {sum(p - s for p, s in costing):+d} "
        f"B). A break-even-only apply would have written just the "
        f"{len(saving)} saving stubs; full stubbing is the default "
        f"because the stub is the provenance record, not a "
        f"compression codec — the census is where the byte story "
        f"is told.")
    add(f"- files touched: {len(ai['touched'])}")
    add("")
    add("### DEMOTED-TO-STALE — bindings this rewrite invalidates")
    add("")
    if not ai["demoted"]:
        add("(none — no receipt, verdict, or view binding names a "
            "rewritten payload or a touched file)")
    for coord, kind, why in ai["demoted"]:
        add(f"- {fmt(coord)} — {kind}: {why}")
    add("")
    add("Demotion is the tier system's designed response to a source "
        "edit: the binding scrolls above are listed, never edited, "
        "and read STALE until their own pass re-issues them.")
    if ai["mentions"]:
        add("")
        add(f"### Also mentions a changed hash (no binding asserted): "
            f"{len(ai['mentions'])} scrolls")
        for c in ai["mentions"][:10]:
            add(f"- {fmt(c)}")
        if len(ai["mentions"]) > 10:
            add(f"- … and {len(ai['mentions']) - 10} more")
    add("")
    return L


# ------------------------------------------------------------ apply
def apply_dedup(scrolls, entries, segs, cz):
    """Rewrite exact duplicates as dedup stubs. Returns
    (new_scrolls, info). Only two classes are rewritten — Volume 3
    segment payloads (header line kept byte-exact) and Volume 2
    whole-file scrolls named by the placement manifest — because
    those are the two `phcc unpack` expands. Canonical = the
    lowest coordinate of the cluster; it is never stubbed, so
    stubs never chain."""
    new = dict(scrolls)
    seg_stubs = file_stubs = replaced = stub_bytes = 0
    stub_sizes = []          # (payload bytes, stub bytes) per stub
    touched = set()          # manifest paths with >= 1 stub
    changed = set()          # hashes whose raw bytes were rewritten
    rewritten = set()        # coords rewritten (skipped by the scan)

    for h, ms in cz["member_clusters"].items():
        ordered = sorted(ms, key=lambda s: s["coord"])
        canon = ordered[0]
        stub = dedup_ref(canon["coord"], h)
        for s in ordered[1:]:
            if is_binary_scroll(s["payload"]):
                continue  # paranoia: a segment is C text; never stub
                # a binary-format payload (see exclusions in METHODS)
            new[s["coord"]] = s["header"] + b"\n" + stub
            seg_stubs += 1
            replaced += len(s["payload"])
            stub_bytes += len(stub)
            stub_sizes.append((len(s["payload"]), len(stub)))
            touched.add(s["path"])
            changed.add(h)
            rewritten.add(s["coord"])

    by_file = collections.defaultdict(list)
    for e in entries:
        if e["size"] > 0 and not parse_dedup_ref(scrolls[e["coord"]]):
            by_file[e["sha"]].append(e)
    for sha, es in by_file.items():
        if len(es) < 2:
            continue
        ordered = sorted(es, key=lambda e: e["coord"])
        canon = ordered[0]
        if is_binary_scroll(scrolls[canon["coord"]]):
            continue
        stub = dedup_ref(canon["coord"], sha)
        for e in ordered[1:]:
            if is_binary_scroll(scrolls[e["coord"]]):
                continue
            new[e["coord"]] = stub
            file_stubs += 1
            replaced += e["size"]
            stub_bytes += len(stub)
            stub_sizes.append((e["size"], len(stub)))
            touched.add(e["path"])
            changed.add(sha)
            rewritten.add(e["coord"])

    for e in entries:
        if e["path"] in touched:
            changed.add(e["sha"])

    demoted, mentions = demote_scan(scrolls, changed, touched,
                                    rewritten, seg_stubs)
    info = {"seg_stubs": seg_stubs, "file_stubs": file_stubs,
            "replaced": replaced, "stub_bytes": stub_bytes,
            "stub_sizes": stub_sizes,
            "touched": sorted(touched), "demoted": demoted,
            "mentions": mentions, "rewritten": rewritten}
    return new, info


def demote_scan(scrolls, changed, touched, rewritten, seg_stubs):
    """Find every binding a rewrite invalidates. A scroll (other
    than a rewritten one) whose text names a changed hash is a
    binding hit; classification decides DEMOTED vs mention:
    gate verdicts and Proofs-collection receipts are receipts by
    construction; Design-collection scrolls are derived views bound
    to their file (hash hit, or the Design path rule: the view
    names a touched file's path). The current gate verdict is
    always demoted by any segment rewrite — it binds the Volume 3
    members digest of the whole phext (Slice 3 binding), whether or
    not an individual changed hash appears in its text."""
    demoted, mentions = [], []
    verdicts = []
    touched_b = [p.encode() for p in touched]
    for c in sorted(scrolls):
        content = scrolls[c]
        if c in rewritten or not content:
            continue
        is_verdict = content.startswith(b"# phcc gate verdict")
        if is_verdict:
            verdicts.append(c)
        hits = changed & {m.decode() for m in HEX64_RE.findall(content)}
        if is_verdict and hits:
            demoted.append((c, "gate verdict",
                            f"names {len(hits)} changed hash(es); its "
                            f"digests were computed over the "
                            f"pre-dedup phext"))
        elif c[3] == 10 and hits:
            demoted.append((c, "proof receipt",
                            "binds changed hash(es): "
                            + ", ".join(sorted(h[:16] for h in hits))
                            + "…"))
        elif c[3] == 3 and hits:
            demoted.append((c, "design view",
                            "binds changed hash(es): "
                            + ", ".join(sorted(h[:16] for h in hits))
                            + "…"))
        elif c[3] == 3 and any(p in content for p in touched_b):
            demoted.append((c, "design view",
                            "derived view of a touched file (path "
                            "rule); its members digest no longer "
                            "matches the file's segments"))
        elif hits:
            mentions.append(c)
    if seg_stubs and verdicts:
        latest = verdicts[-1]
        if all(c != latest for c, _, _ in demoted):
            demoted.append((latest, "gate verdict",
                            "binds the Volume 3 members digest of "
                            "the pre-dedup phext; any segment rewrite "
                            "demotes it"))
            demoted.sort(key=lambda d: d[0])
    return demoted, mentions


# ------------------------------------------------------ statement tier
# Statement-level de-duplication as a phext-native expression
# (Will's directive, 2026-11-07: "phcc needs to flex on older
# compilation toolchains by expressing statement-level
# de-duplication", refined by his ruling "we have as many scrolls
# as we need — files and filenames don't concern us").
#
# The member-stub apply above answers duplication at member grain
# inside a file-shaped phext; its economics were a byte loss and
# that framing is retired for this tier. Here the corpus is
# re-expressed at statement grain: every Volume 3 segment payload
# is split into statement-grain segments (the splitter below), each
# distinct statement core is held exactly once in a dedicated
# statement library (Library 20000) at a content-derived
# coordinate, and each member scroll is rewritten as an ordered
# sequence of statement references (phext_io statement refs) —
# composition by reference. Files survive only as the unpack
# export view. The success metrics are structural, not bytes:
# instances vs distinct (the de-duplication ratio), reference
# integrity (every reference resolves, hash-verified), and a
# lossless round-trip through `phcc unpack`.
from phext_io import (parse_stmt_seq, stmt_ref, stmt_ref_empty,
                      STMT_SEQ_MAGIC)

STMT_LIBRARY = 20000
STMT_REGISTER_COORD = (1, 1, 1, 1, 2, 10, 1, 23, 1)
_STMT_WS = frozenset(b" \t\r\n\x0b\x0c")
_BLOCK_LENS = (3, 4, 5, 6, 8, 10, 12, 16, 20)


def split_segments(data):
    """Split a C payload into statement-grain segments.

    Returns a list of (indent, core, terminator): indent is the
    segment's leading whitespace (positional, not content), core
    is the remaining bytes, and terminator names what ended the
    segment — "semi" (`;` at paren depth 0), "open" (`{`), "close"
    (`}`), "close-semi" (`}` + optional whitespace + `;`, the
    struct/array-declaration ending taken as one unit), "pp" (a
    preprocessor line), "split" (a chunk ended by an intervening
    preprocessor line, not by its own delimiter), "tail" (the
    remainder after the last delimiter). Joining indent + core
    over the list reproduces `data` byte-for-byte, always — the
    partition is total, so the statement expression built on it is
    lossless for any payload, C or not.

    The scanner is atom-aware: string/char literals and comments
    are consumed whole (structural characters inside them are
    content), semicolons inside parentheses never cut (the
    for-header rule), and a preprocessor line is detected only at
    a line start and consumed to its logical end (backslash
    continuations respected). Paren depth is clamped at 0 so
    fragment payloads (gap segments) still segment. Known limits,
    by design: initializer lists are single segments (they are
    single declarations; commas never cut), a label binds to the
    statement it prefixes (colons never cut), a do-while tail
    `while (x);` segments as its own "semi" segment, and
    trigraphs are not honoured."""
    if not data:
        return []
    n = len(data)
    cuts = []                       # (end_index, terminator)
    cur = [0]                       # start of the open segment

    def cut(end, term):
        cuts.append((end, term))
        cur[0] = end

    i, paren = 0, 0
    at_line_start, line_begin = True, 0
    while i < n:
        b = data[i]
        if b == 0x0A:                                   # newline
            i += 1
            at_line_start, line_begin = True, i
            continue
        if b in (0x20, 0x09, 0x0D, 0x0B, 0x0C):         # other ws
            i += 1
            continue
        if b == 0x2F and i + 1 < n and data[i + 1] == 0x2F:
            j = data.find(b"\n", i)                     # // comment
            i = n if j < 0 else j
            at_line_start = False
            continue
        if b == 0x2F and i + 1 < n and data[i + 1] == 0x2A:
            j = data.find(b"*/", i + 2)                 # /* comment
            end = n if j < 0 else j + 2
            seg = data[i:end]
            k = seg.rfind(b"\n")
            if k >= 0:
                at_line_start = all(c in _STMT_WS
                                    for c in seg[k + 1:])
                line_begin = i + k + 1
            else:
                at_line_start = False
            i = end
            continue
        if b in (0x22, 0x27):                           # " / ' literal
            q = b
            i += 1
            while i < n:
                if data[i] == 0x5C:
                    i += 2
                    continue
                if data[i] == q:
                    i += 1
                    break
                i += 1
            at_line_start = False
            continue
        if b == 0x23 and at_line_start:                 # # directive
            # An interrupted chunk is cut at its line's start, and
            # the newline that ends the interrupted line belongs
            # to the directive segment's leading whitespace (the
            # same place the newline after a `;` lands), so cores
            # never carry a stray trailing newline from the split.
            pre = line_begin - 1 if line_begin > 0 \
                and data[line_begin - 1] == 0x0A else line_begin
            if cur[0] < pre and any(
                    c not in _STMT_WS for c in data[cur[0]:pre]):
                cut(pre, "split")
            j = i
            while True:
                k = data.find(b"\n", j)
                if k < 0:
                    j = n
                    break
                m, bs = k - 1, 0
                while m >= i and data[m] == 0x5C:
                    bs += 1
                    m -= 1
                if bs % 2 == 1:                         # continued
                    j = k + 1
                    continue
                j = k
                break
            i = j
            cut(i, "pp")
            at_line_start = False
            continue
        if b == 0x28:
            paren += 1
        elif b == 0x29:
            paren = max(0, paren - 1)
        elif b == 0x7B:                                 # {
            i += 1
            cut(i, "open")
            at_line_start = False
            continue
        elif b == 0x7D:                                 # }
            i += 1
            j = i
            while j < n and data[j] in _STMT_WS:
                j += 1
            if j < n and data[j] == 0x3B:
                cut(j + 1, "close-semi")
                i = j + 1
            else:
                cut(i, "close")
            at_line_start = False
            continue
        elif b == 0x3B and paren == 0:                  # ;
            i += 1
            cut(i, "semi")
            at_line_start = False
            continue
        at_line_start = False
        i += 1
    if not cuts or cuts[-1][0] < n:
        cuts.append((n, "tail"))
    out, start = [], 0
    for end, term in cuts:
        raw = data[start:end]
        k = 0
        while k < len(raw) and raw[k] in _STMT_WS:
            k += 1
        out.append((raw[:k], raw[k:], term))
        start = end
    return out


_BACKEND_PREFIXES = ("x86_64", "i386", "arm64", "arm", "riscv64",
                     "c67", "il")


def stmt_group(path):
    """Coarse grouping for per-backend ratios."""
    base = path.rsplit("/", 1)[-1]
    for a in _BACKEND_PREFIXES:
        if base.startswith(a + "-"):
            return f"backend:{a}"
    if path.startswith("win32/include/"):
        return "headers:win32"
    if path.startswith("include/"):
        return "headers"
    if path.startswith("win32/"):
        return "win32"
    if path.startswith("lib/"):
        return "runtime-lib"
    if path.startswith("tests/"):
        return "tests"
    if "/" not in path and (base.endswith(".c")
                            or base.endswith(".h")):
        return "core"
    return "other"


def statement_census(segs):
    """Segment every segment payload and tally the statement
    census. Also verifies, on the whole corpus, the splitter's
    partition invariant (indent + core rejoins to the payload).
    Returns a dict: totals, per-class / per-file / per-group
    tallies, top statements, repeated blocks, size distribution,
    the distinct-core table (sha -> core bytes), and per-segment
    reference lists for the builder."""
    cores = {}                       # sha -> core bytes
    per_segment = []                 # [(indent, sha|None)] per seg
    total = empty_core = 0
    classes = collections.Counter()
    sizes = collections.Counter()
    per_file = collections.defaultdict(
        lambda: {"inst": 0, "shas": set()})
    per_group = collections.defaultdict(
        lambda: {"inst": 0, "shas": set()})
    top = collections.Counter()      # sha -> instances
    example = {}                     # sha -> (path, member name)
    blocks = {}                      # (L, id-tuple) -> [count, loc]
    block_cores = {}                 # (L, id-tuple) -> [core bytes]
    ids = {}                         # sha -> small int id
    partition_failures = 0

    def bucket(ln):
        for cap in (8, 16, 32, 64, 128, 256, 512, 1024):
            if ln <= cap:
                return f"≤{cap}"
        return ">1024"

    for rec in segs:
        payload = rec["payload"]
        if payload is None:
            per_segment.append(None)
            continue
        parts = split_segments(payload)
        if b"".join(ind + core for ind, core, _ in parts) != payload:
            partition_failures += 1
        pf = per_file[rec["path"]]
        pg = per_group[stmt_group(rec["path"])]
        refs, seq = [], []
        for ind, core, term in parts:
            total += 1
            classes[term] += 1
            sizes[bucket(len(core))] += 1
            pf["inst"] += 1
            pg["inst"] += 1
            if not core:
                empty_core += 1
                refs.append((ind, None))
                seq.append(-1)
                continue
            h = sha256(core)
            if h not in cores:
                cores[h] = core
                ids[h] = len(ids)
            elif cores[h] != core:
                raise SystemExit("SHA-256 collision between "
                                 "distinct statement cores")
            top[h] += 1
            pf["shas"].add(h)
            pg["shas"].add(h)
            if h not in example:
                example[h] = (rec["path"], rec["name"])
            refs.append((ind, h))
            seq.append(ids[h])
        per_segment.append(refs)
        for L in _BLOCK_LENS:
            if len(seq) < L:
                continue
            for s0 in range(len(seq) - L + 1):
                if -1 in seq[s0:s0 + L]:
                    continue        # blocks span real statements
                key = (L, tuple(seq[s0:s0 + L]))
                if key in blocks:
                    blocks[key][0] += 1
                else:
                    blocks[key] = [1, (rec["path"], rec["name"], s0)]
                    # capture the block's cores at first sight
                    block_cores[key] = [
                        parts[s0 + t][1] for t in range(L)]
    # NEAR tier: distinct normalized forms among the distinct
    # exact cores (normalizing per distinct core, not per
    # instance — same set, far less work).
    near_distinct = len({sha256(normalize_code(c))
                         for c in cores.values()})
    return {"total": total, "empty_core": empty_core,
            "distinct": len(cores), "near_distinct": near_distinct,
            "classes": classes, "sizes": sizes,
            "per_file": {p: {"inst": v["inst"],
                             "distinct": len(v["shas"])}
                         for p, v in per_file.items()},
            "per_group": {p: {"inst": v["inst"],
                              "distinct": len(v["shas"])}
                          for p, v in per_group.items()},
            "top": top, "example": example, "blocks": blocks,
            "block_cores": block_cores, "cores": cores,
            "per_segment": per_segment,
            "partition_failures": partition_failures}


def _block_rank(item):
    (L, _t), (count, _loc) = item
    return -(count * (L - 1))


def render_stmt_report(phext_path, raw, segs, sc, build_info=None):
    L = []
    add = L.append
    tot, dis = sc["total"], sc["distinct"]
    add("# phcc analyze — statement tier census")
    add("")
    add(f"- phext: {phext_path}")
    add(f"- phext bytes: {len(raw)}  sha256: {sha256(raw)}")
    add(f"- segment payloads segmented: "
        f"{sum(1 for r in sc['per_segment'] if r is not None)} "
        f"of {len(segs)} indexed segments")
    add(f"- splitter partition invariant (indent + core rejoins "
        f"to the payload, byte-for-byte, every payload): "
        f"{'HOLDS' if sc['partition_failures'] == 0 else 'FAILED'}"
        f" ({sc['partition_failures']} failures)")
    add("")
    add("## Headline — instances vs distinct")
    add("")
    add(f"- statement instances: {tot}")
    add(f"- distinct statements (exact core bytes): {dis}")
    add(f"- **de-duplication ratio (exact): "
        f"{tot / max(dis, 1):.2f}×** — each distinct statement is "
        f"written once and referenced "
        f"{tot / max(dis, 1):.2f} times on average")
    add(f"- distinct statements (NEAR normalization — comments "
        f"stripped, whitespace collapsed): {sc['near_distinct']} "
        f"(ratio {tot / max(sc['near_distinct'], 1):.2f}×; the "
        f"expression deduplicates at the exact tier — the NEAR "
        f"figure is the headroom a formatting-insensitive "
        f"expression would add)")
    add(f"- whitespace-only segments (empty core, EMPTY "
        f"reference): {sc['empty_core']}")
    add("")
    add("## Instances by segment class")
    add("")
    for term in ("semi", "open", "close", "close-semi", "pp",
                 "split", "tail"):
        if sc["classes"].get(term):
            add(f"- {term}: {sc['classes'][term]}")
    add("")
    add("## Statement core sizes")
    add("")
    for cap in ("≤8", "≤16", "≤32", "≤64", "≤128", "≤256", "≤512",
                "≤1024", ">1024"):
        if sc["sizes"].get(cap):
            add(f"- {cap} B: {sc['sizes'][cap]}")
    add("")
    add("## Per-group ratio (instances / distinct-in-group)")
    add("")
    for g, v in sorted(sc["per_group"].items(),
                       key=lambda kv: -kv[1]["inst"]):
        add(f"- {g}: {v['inst']} / {v['distinct']} = "
            f"{v['inst'] / max(v['distinct'], 1):.2f}×")
    add("")
    add("## Per-file ratio (top 25 by instances)")
    add("")
    for p, v in sorted(sc["per_file"].items(),
                       key=lambda kv: -kv[1]["inst"])[:25]:
        add(f"- {p}: {v['inst']} / {v['distinct']} = "
            f"{v['inst'] / max(v['distinct'], 1):.2f}×")
    add("")
    add("## Most-repeated statements")
    add("")
    for h, cnt in sc["top"].most_common(30):
        core = sc["cores"][h]
        preview = core[:100].decode("utf-8", "replace") \
            .replace("\n", "\\n")
        path, name = sc["example"][h]
        add(f"- ×{cnt} — `{preview}` ({len(core)} B; first at "
            f"{path} :: {name})")
    add("")
    add("## Most-repeated statement blocks (≥3 consecutive, exact)")
    add("")
    add("Ranked by references a factoring would save: "
        "occurrences × (length − 1).")
    add("")
    ranked = sorted(sc["blocks"].items(), key=_block_rank)
    shown = 0
    for (Ln, _t), (count, loc) in ranked:
        if count < 2:
            break
        text = b" ".join(sc["block_cores"][(Ln, _t)])
        preview = text[:220].decode("utf-8", "replace") \
            .replace("\n", "\\n")
        add(f"- len {Ln} × {count} occurrences "
            f"(saves {count * (Ln - 1)} refs) — {preview} "
            f"(first at {loc[0]} :: {loc[1]} +{loc[2]})")
        shown += 1
        if shown >= 25:
            break
    if not shown:
        add("(no block of ≥3 statements repeats)")
    if build_info:
        L += render_stmt_build(build_info)
    return "\n".join(L) + "\n"


def render_stmt_build(bi):
    L = []
    add = L.append
    add("")
    add("## BUILD — the statement-level expression")
    add("")
    add(f"- output phext: {bi['out']} ({bi['out_bytes']} B; "
        f"{bi['delta']:+d} B vs input — bytes are not the metric "
        f"here; see the ratio above)")
    add(f"- statement library: Library {STMT_LIBRARY}, "
        f"{bi['statements']} statement scrolls (one per distinct "
        f"statement)")
    add(f"- member scrolls rewritten as reference sequences: "
        f"{bi['rewritten']} ({bi['refs']} references, "
        f"{bi['empty_refs']} of them EMPTY/whitespace-only)")
    add(f"- coordinate derivation: SHA-256 of the statement core; "
        f"the eight sub-library components are digest bytes 0–7 "
        f"mod 5 + 1 (content-derived — the address is a function "
        f"of the statement, recomputed, never assigned); "
        f"collisions probed deterministically in digest order "
        f"({bi['probes']} probes needed)")
    add(f"- register scroll: {fmt(STMT_REGISTER_COORD)} "
        f"(Meta, placement-manifest book, Section 23)")
    add(f"- verification: `phcc analyze --verify-stmt --phext "
        f"{bi['out']}` and `phcc unpack --from vol3` (see "
        f"METHODS.md, statement tier)")
    add("")
    return L


def assign_stmt_coords(cores):
    """Content-derived coordinates for the statement library.
    Distinct cores are processed in digest (SHA-256 hex) order;
    the derived coordinate is Library 20000 with the eight
    remaining components taken from digest bytes 0–7 (mod 5, +1).
    A collision (a different core deriving an occupied
    coordinate) probes forward as a base-5 counter over the
    eight components — deterministic, so the mapping is a pure
    function of the corpus's digest set: found, not assigned.

    The component base is a walk-cost decision, measured, not
    assumed: a sparse content-derived layout materializes one
    empty scroll per unit climbed along the sorted coordinate
    walk (the Library-10000 build region's documented artifact,
    at scale). The first build used mod 99 (99^8 cells) and
    materialized 15,341,147 empty scrolls — 15.3 MB of delimiter
    bytes around 66,272 statements, and a ~90 s verification
    walk. Mod 5 (5^8 = 390,625 cells for a 66k corpus) keeps
    every address a pure function of the statement's own
    SHA-256 at roughly 1/12 the materialization. Dense rank
    addressing would erase it entirely but makes addresses
    corpus-relative; this programme's ledger culture prizes
    addresses that survive corpus changes."""
    occupied, assign, probes = {}, {}, 0
    for h in sorted(cores):
        d = bytes.fromhex(h)
        base = [d[k] % 5 + 1 for k in range(8)]
        while True:
            coord = (STMT_LIBRARY,) + tuple(base)
            if coord not in occupied:
                break
            probes += 1
            p = 7
            while True:
                base[p] += 1
                if base[p] <= 5:
                    break
                base[p] = 1
                p -= 1
                if p < 0:
                    raise SystemExit("statement coordinate space "
                                     "exhausted (cannot happen: "
                                     "5^8 = 390,625 >> corpus)")
        occupied[coord] = h
        assign[h] = coord
    return assign, probes


def build_stmt(scrolls, segs, sc, src_sha):
    """Rewrite every segment payload as a statement reference
    sequence and add the statement library + register scroll.
    Returns (new_scrolls, info)."""
    assign, probes = assign_stmt_coords(sc["cores"])
    new = dict(scrolls)
    refs = empty_refs = rewritten = 0
    for rec, seglist in zip(segs, sc["per_segment"]):
        if seglist is None:
            continue
        lines = [STMT_SEQ_MAGIC]
        for ind, h in seglist:
            if h is None:
                lines.append(stmt_ref_empty(ind))
                empty_refs += 1
            else:
                lines.append(stmt_ref(assign[h], h, ind))
            refs += 1
        new[rec["coord"]] = rec["header"] + b"\n" + b"".join(lines)
        rewritten += 1
    for h, coord in assign.items():
        new[coord] = sc["cores"][h]
    tot, dis = sc["total"], sc["distinct"]
    new[STMT_REGISTER_COORD] = (
        "# phcc statement expression — register\n"
        "# The statement-level layout of the canonical phcc "
        "corpus: every Volume 3 segment payload is expressed as\n"
        "# an ordered sequence of statement references "
        "(phext_io statement refs), and each distinct statement\n"
        "# core is held exactly once in the statement library.\n"
        f"# source phext sha256: {src_sha}\n"
        f"# statement library: {STMT_LIBRARY}\n"
        f"# statement scrolls: {dis}\n"
        f"# statement instances referenced: {tot}\n"
        f"# de-duplication ratio: {tot / max(dis, 1):.4f}\n"
        "# coordinate derivation: library 20000; the eight "
        "remaining components are SHA-256(core)\n"
        "#   digest bytes 0-7 mod 5 + 1, collisions probed "
        "forward in digest order as a base-5 counter.\n"
        "# expansion: phcc unpack --from vol3 (each reference "
        "target verified against its recorded SHA-256,\n"
        "#   then the file index's payload SHA-256 verifies the "
        "reassembled segment — the plain rules).\n"
        "# verification: phcc analyze --verify-stmt on this "
        "phext.\n").encode("utf-8")
    info = {"refs": refs, "empty_refs": empty_refs,
            "rewritten": rewritten, "statements": dis,
            "probes": probes, "assign": assign}
    return new, info


def verify_stmt(scrolls, entries):
    """Verify a statement-level phext against its own records:
    (a) every statement reference resolves and its target hashes
    to the SHA-256 the reference records (via phcc_migrate's
    expander, the same code unpack runs), and the reassembled
    payload hashes to the file index's recorded payload SHA-256;
    (c) the statement library holds each distinct statement
    exactly once — the set of library content hashes equals the
    set of hashes the references name, with no duplicates and no
    orphans. Returns (ok, lines of report)."""
    import phcc_migrate
    segs, _problems = collect_segments(scrolls, entries)
    refs = expanded = bad = 0
    failures = []
    ref_shas = set()
    for rec in segs:
        payload = rec["payload"]
        if payload is None:
            bad += 1
            failures.append(f"{rec['path']} :: {rec['name']}: "
                            "segment missing")
            continue
        parsed = parse_stmt_seq(payload)
        if parsed is None:
            bad += 1
            failures.append(f"{rec['path']} :: {rec['name']}: "
                            "payload is not a statement sequence")
            continue
        for coord, want, _ind in parsed:
            if want is not None:
                ref_shas.add(want)
        stats = {}
        try:
            out = phcc_migrate.resolve_stmt_seq(scrolls, payload,
                                                stats)
        except ValueError as ex:
            bad += 1
            failures.append(f"{rec['path']} :: {rec['name']}: {ex}")
            continue
        refs += stats.get("stmt_refs", 0)
        if sha256(out) != rec["index_sha"]:
            bad += 1
            failures.append(f"{rec['path']} :: {rec['name']}: "
                            "expanded payload sha != index sha")
            continue
        expanded += 1
    # The statement library's content scrolls are its non-empty
    # scrolls: statement cores are never empty (whitespace-only
    # segments are EMPTY references and hold no scroll), while the
    # phext walk materializes an empty scroll at every intermediate
    # coordinate of a sparse region — the same representation
    # artifact the Library-10000 build region documents. Empty
    # scrolls in the region are counted and reported, never
    # mistaken for statements.
    region = {c: b for c, b in scrolls.items()
              if c[0] == STMT_LIBRARY}
    lib = {c: b for c, b in region.items() if b}
    lib_hashes = [sha256(b) for b in lib.values()]
    lib_set = set(lib_hashes)
    c_ok = len(lib_hashes) == len(lib_set) \
        and lib_set == ref_shas
    lines = [
        f"- segments verified: {expanded}/{len(segs)} expand to "
        f"payloads matching their file-index SHA-256",
        f"- statement references resolved + hash-verified: {refs}",
        f"- reference failures: {bad}",
        f"- statement library: {len(lib)} statement scrolls "
        f"(+ {len(region) - len(lib)} materialized empty scrolls "
        f"in the region), {len(lib_set)} distinct contents, "
        f"{len(ref_shas)} distinct statements referenced — "
        f"each distinct statement held exactly once: "
        f"{'YES' if c_ok else 'NO'}",
    ]
    for f in failures[:20]:
        lines.append(f"- FAIL: {f}")
    ok = bad == 0 and expanded == len(segs) and c_ok
    return ok, lines


# ------------------------------------------------------------ cli
def run(a):
    raw = open(a.phext, "rb").read()
    scrolls = dict(walk_bytes(raw))
    try:
        import phcc_migrate
        entries = phcc_migrate.manifest_entries(scrolls)
    except SystemExit:
        entries = []
        print("note: no placement manifest — member/file tiers "
              "unavailable, whole-scroll census only", file=sys.stderr)
    if a.verify_stmt:
        if not entries:
            print("REFUSING: --verify-stmt needs the placement "
                  "manifest", file=sys.stderr)
            return 2
        ok, lines = verify_stmt(scrolls, entries)
        report = ("# phcc analyze — statement expression "
                  "verification\n\n"
                  f"- phext: {a.phext}\n"
                  f"- phext bytes: {len(raw)}  sha256: "
                  f"{sha256(raw)}\n\n" + "\n".join(lines) + "\n")
        if a.out:
            with open(a.out, "w") as f:
                f.write(report)
            print(f"verification written: {a.out}")
        else:
            print(report)
        print("verify-stmt:", "OK" if ok else "FAILED")
        return 0 if ok else 1
    segs, problems = collect_segments(scrolls, entries)
    if a.statements or a.build_stmt:
        if not entries:
            print("REFUSING: statement tier needs the placement "
                  "manifest", file=sys.stderr)
            return 2
        if a.build_stmt and problems:
            print(f"REFUSING to build: {len(problems)} segment "
                  f"hash-verification problem(s) — the statement "
                  f"expression is never built on untrusted hashes",
                  file=sys.stderr)
            return 1
        sc = statement_census(segs)
        build_info = None
        if a.build_stmt:
            if not a.out:
                print("REFUSING: --build-stmt requires --out "
                      "Y.phext", file=sys.stderr)
                return 2
            if os.path.exists(a.out) and not a.force:
                print(f"REFUSING: {a.out} exists (pass --force)",
                      file=sys.stderr)
                return 2
            new, build_info = build_stmt(scrolls, segs, sc,
                                         sha256(raw))
            blob = implode(new)
            with open(a.out, "wb") as f:
                f.write(blob)
            build_info.update({"out": a.out,
                               "out_bytes": len(blob),
                               "delta": len(blob) - len(raw)})
            print(f"analyze --build-stmt: {build_info['refs']} "
                  f"references to {build_info['statements']} "
                  f"statement scrolls -> {a.out} ({len(blob)} B)")
        report = render_stmt_report(a.phext, raw, segs, sc,
                                    build_info)
        report_path = a.report or (None if a.build_stmt else a.out)
        if report_path:
            with open(report_path, "w") as f:
                f.write(report)
            print(f"report written: {report_path}")
        else:
            print(report)
        return 0
    cz = census(scrolls, entries, segs)

    apply_info = None
    if a.apply:
        if not a.out:
            print("REFUSING: --apply requires --out Y.phext",
                  file=sys.stderr)
            return 2
        if os.path.exists(a.out) and not a.force:
            print(f"REFUSING: {a.out} exists (pass --force)",
                  file=sys.stderr)
            return 2
        if problems:
            print(f"REFUSING to apply: {len(problems)} segment "
                  f"hash-verification problem(s) — apply never "
                  f"rewrites on untrusted hashes (see census)",
                  file=sys.stderr)
            return 1
        new, apply_info = apply_dedup(scrolls, entries, segs, cz)
        blob = implode(new)
        with open(a.out, "wb") as f:
            f.write(blob)
        apply_info.update({"out": a.out, "out_bytes": len(blob),
                           "delta": len(blob) - len(raw)})
        print(f"analyze --apply: {apply_info['seg_stubs']} segment + "
              f"{apply_info['file_stubs']} file stubs -> {a.out} "
              f"({len(blob)} B, {apply_info['delta']:+d} B)")

    report = render_report(a.phext, raw, scrolls, entries, segs,
                           problems, cz, apply_info)
    report_path = a.report or (None if a.apply else a.out)
    if report_path:
        with open(report_path, "w") as f:
            f.write(report)
        print(f"report written: {report_path}")
    else:
        print(report)
    return 0


def cli(argv):
    ap = argparse.ArgumentParser(
        prog="phcc analyze",
        description="duplication census + automatic de-duplication")
    ap.add_argument("--phext", required=True)
    ap.add_argument("--out", default=None,
                    help="census: report file (default stdout); "
                         "apply: the NEW phext to write (required)")
    ap.add_argument("--apply", action="store_true",
                    help="write a deduplicated phext to --out")
    ap.add_argument("--report", default=None,
                    help="also write the report to this file "
                         "(apply mode; census uses --out)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite --out if it exists")
    ap.add_argument("--statements", action="store_true",
                    help="statement tier census: segment every "
                         "member payload at statement grain and "
                         "report instances vs distinct statements")
    ap.add_argument("--build-stmt", action="store_true",
                    help="write the statement-level expression of "
                         "the phext to --out (statement library + "
                         "member scrolls as reference sequences)")
    ap.add_argument("--verify-stmt", action="store_true",
                    help="verify a statement-level phext: every "
                         "reference resolves + hash-matches, every "
                         "expanded payload matches its index "
                         "SHA-256, and the statement library holds "
                         "each distinct statement exactly once")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
