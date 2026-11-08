#!/usr/bin/env python3
"""phcc_analyze.py — duplication census + automatic de-duplication.

User-facing interface (Will's ruling, 2026-11-07 — "add an analysis
mode for automatic de-duplication"):

    phcc analyze --phext X.phext [--out REPORT]
    phcc analyze --phext X.phext --apply --out Y.phext [--report R]

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
    segs, problems = collect_segments(scrolls, entries)
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
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
