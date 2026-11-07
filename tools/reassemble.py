#!/usr/bin/env python3
"""reassemble.py — exit-test tool for importer v3: rebuild every file
from its Volume-3 segment scrolls (never consulting the Volume-2
scroll for structured files) and byte-compare against the Slice 0
manifest SHA-256. File-level files (no Volume-3 index) are taken from
their Volume-2 bridge scroll and verified the same way.

Writes the reassembled tree (git modes restored) for the ranch build.

Usage: reassemble.py [--phext FILE] [--out DIR]
Exits 0 only if all 558 files byte-match the manifest.
Stdlib only.
"""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from phext_io import walk_bytes, fmt, sha256, parse_coord


def main():
    ap = argparse.ArgumentParser()
    home = os.path.expanduser("~")
    w = os.path.join(home, "workspace/phcc-slice3-granularity")
    ap.add_argument("--phext", default=os.path.join(w, "phcc-fn.phext"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    scrolls = dict(walk_bytes(open(a.phext, "rb").read()))
    man = (1, 1, 1, 1, 2, 10, 1, 1, 1)
    entries = []
    for line in scrolls[man].decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        path, coord_s, sha, size, mode = line.split("\t")
        entries.append((path, parse_coord(coord_s), sha, int(size), mode))
    print(f"manifest: {len(entries)} files")

    ok_seg, ok_bridge, failed = 0, 0, []
    for path, v2, sha, size, mode in entries:
        idx = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        # An index scroll must identify itself: the phext byte walk
        # also yields structural EMPTY scrolls at intermediate
        # coordinates (consecutive delimiters), which can sit on a
        # file-level file's would-be index coordinate. Magic + path
        # + hash check, or it is not an index.
        idx_bytes = scrolls.get(idx, b"")
        structured = idx_bytes.startswith(b"# phcc file index") and \
            f"# path: {path}\n".encode() in idx_bytes and \
            f"# sha256: {sha} ".encode() in idx_bytes
        if structured:
            table = []
            for line in scrolls[idx].decode("utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                scr, kind, name, form, span, psha = line.split("\t")
                table.append((int(scr), kind, span, psha))
            parts, expect_start = [], 0
            for scr, kind, span, psha in table:
                s, e = (int(x) for x in span.split("-"))
                if s != expect_start:
                    failed.append((path, f"span discontinuity at scroll {scr}: {s} != {expect_start}"))
                    break
                expect_start = e
                raw = scrolls[(1, 1, 1, 4, 3, v2[5], v2[6], v2[7], scr)]
                payload = raw.split(b"\n", 1)[1]
                if sha256(payload) != psha or len(payload) != e - s:
                    failed.append((path, f"segment scroll {scr} payload hash/length mismatch"))
                    break
                parts.append(payload)
            else:
                data = b"".join(parts)
                if sha256(data) == sha and len(data) == size:
                    ok_seg += 1
                else:
                    failed.append((path, "reassembled bytes != manifest sha256"))
                    continue
        else:
            data = scrolls[v2]
            if sha256(data) == sha and len(data) == size:
                ok_bridge += 1
            else:
                failed.append((path, "bridge scroll != manifest sha256"))
                continue
        dest = os.path.join(a.out, path)
        os.makedirs(os.path.dirname(dest) or a.out, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        os.chmod(dest, 0o755 if mode == "100755" else 0o644)

    print(f"reassembled from member segments: {ok_seg}")
    print(f"verified via bridge (file-level):  {ok_bridge}")
    print(f"total verified: {ok_seg + ok_bridge}/{len(entries)}")
    if failed:
        print("FAILURES:", file=sys.stderr)
        for p, why in failed:
            print(f"  {p}: {why}", file=sys.stderr)
        sys.exit(1)
    print("REASSEMBLY OK — every file byte-identical to the Slice 0 manifest")


if __name__ == "__main__":
    main()
