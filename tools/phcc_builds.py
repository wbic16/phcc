#!/usr/bin/env python3
"""phcc_builds.py — build-artifact region + phext seal tooling for phcc.

Commands (routed by the `phcc` dispatcher):

    phcc build-region list --phext X.phext
    phcc build-region wipe --phext X.phext --out Y.phext [--force]
    phcc seal   --phext X.phext [--out X.phext.xz] [--force]
    phcc unseal --sealed X.phext.xz [--out X.phext] [--force]

Build region (Will's ruling, 2026-11-07): binary build artifacts live
inside the phext in a wipeable region rooted at Library 10000
(10000.1.1/1.1.1/1.1.1 = the region manifest scroll). Binary scrolls
mirror their origin artifact's Source address under Library 10000:

    (10000, 1, 1, 4, V, B, Ch, Sec, slot)

    slot 1 = x86_64 object (.o)      slot 3 = x86_64 archive (.a)
    slot 2 = arm64  object (.o)      slot 4 = arm64  archive (.a)

Each binary scroll is in the CANONICAL libphext binary format
(libphext-rs 0.5, PR #9): a header line exactly
`phext-binary:1:base64`, a newline, then the raw binary as RFC 4648
base64 (standard alphabet, padding required, NO line wrapping); an
empty payload is the header line alone. Canonical scrolls carry NO
provenance: artifact, origin, kind, target, raw size, raw SHA-256,
and compiler provenance live in the region root manifest's entry
lines. Decoding = decode the base64 and verify size + SHA-256
against the manifest entry. (The pre-alignment project-local format
— a `# phcc-binary 1` header with inline provenance and 76-column
wrapped base64 — is still decodable by `parse_binary_scroll` as a
legacy fallback, so unconverted phexts remain readable.)

Seal (Will's ruling, 2026-11-07, integrating the 2026-11-04 seal
doctrine): the WORKING phext is always plain text. The xz seal
(`xz -9`, CRC64) is the persistence/publish form only: produce it from
the finished plain phext, store/publish the seal, unseal to work.
unseal(seal(x)) is byte-identical to x by construction (xz is a
lossless codec); the unseal command verifies nothing itself — callers
compare SHA-256, and the round-trip is proven in the slice report.
"""
import argparse, base64, hashlib, lzma, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

REGION_LIBRARY = 10000
REGION_ROOT = (10000, 1, 1, 1, 1, 1, 1, 1, 1)
MAGIC = "# phcc-binary 1"
CANONICAL_HEADER = b"phext-binary:1:base64"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def is_region(coord):
    return coord[0] == REGION_LIBRARY


def is_canonical_binary_scroll(content):
    return content.startswith(CANONICAL_HEADER + b"\n")


def encode_canonical_binary_scroll(raw):
    return CANONICAL_HEADER + b"\n" + base64.b64encode(raw)


def decode_canonical_binary_scroll(content):
    """Raw bytes of a canonical binary scroll, or raise ValueError."""
    if not is_canonical_binary_scroll(content):
        raise ValueError("no canonical binary header line")
    return base64.b64decode(content[len(CANONICAL_HEADER) + 1:],
                            validate=True)


def parse_binary_scroll(content):
    """(header dict, raw bytes) or raise ValueError.

    Canonical scrolls have no in-scroll header; the returned dict
    carries only what the bytes themselves prove (raw-size,
    raw-sha256) — provenance comes from the region manifest. Legacy
    '# phcc-binary 1' scrolls return their full header, verified
    against the decoded bytes as before.
    """
    if is_canonical_binary_scroll(content):
        raw = decode_canonical_binary_scroll(content)
        return {"format": "phext-binary:1:base64",
                "raw-size": str(len(raw)), "raw-sha256": sha256(raw)}, raw
    text = content.decode("ascii")
    head, sep, body = text.partition("\n\n")
    if not sep:
        raise ValueError("no header/body separator")
    lines = head.split("\n")
    if lines[0] != MAGIC:
        raise ValueError("bad magic line")
    hdr = {}
    for line in lines[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            hdr[k.strip()] = v.strip()
    raw = base64.b64decode("".join(body.split()), validate=True)
    if sha256(raw) != hdr.get("raw-sha256"):
        raise ValueError("raw-sha256 mismatch")
    if len(raw) != int(hdr.get("raw-size", -1)):
        raise ValueError("raw-size mismatch")
    return hdr, raw


def parse_region_manifest(content):
    """{coord-string: entry dict} from the region root manifest."""
    entries = {}
    if content is None:
        return entries
    keys = ("artifact", "kind", "target", "raw-size", "raw-sha256",
            "origin", "format", "compiler", "compiler-commit",
            "compile-command", "build-host", "built-at")
    for line in content.decode("utf-8", "replace").splitlines():
        if line.startswith("entry\t"):
            parts = line.split("\t")
            if len(parts) >= 7:
                entry = dict(zip(keys, parts[2:]))
                entry["raw-size"] = int(entry["raw-size"])
                entries[parts[1]] = entry
    return entries


def cmd_region_list(a):
    scrolls = phext_io.load_phext(a.phext)
    region = sorted(c for c in scrolls if is_region(c))
    if not region:
        print("build region: empty (no Library-10000 scrolls)")
        return 0
    total = sum(len(scrolls[c]) for c in region)
    print(f"build region: {len(region)} scrolls, {total} bytes of phext")
    manifest = parse_region_manifest(scrolls.get(REGION_ROOT))
    empties = 0
    for c in region:
        content = scrolls[c]
        if len(content) == 0:
            empties += 1
            continue
        if c == REGION_ROOT:
            kind = "region manifest"
            detail = f"{len(content)} bytes"
        else:
            try:
                hdr, raw = parse_binary_scroll(content)
                entry = manifest.get(phext_io.fmt(c), {})
                merged = {**entry,
                          **{k: v for k, v in hdr.items()
                             if k in ("artifact", "kind", "target")}}
                if entry:
                    if (len(raw) != entry["raw-size"]
                            or sha256(raw) != entry["raw-sha256"]):
                        raise ValueError("manifest raw-size/sha256 mismatch")
                kind = f"{merged.get('kind')} {merged.get('target')}"
                detail = (f"artifact {merged.get('artifact')} "
                          f"raw {len(raw)} B "
                          f"sha256 {sha256(raw)[:16]}…")
            except ValueError as e:
                kind, detail = "binary (UNPARSEABLE)", str(e)
        print(f"  {phext_io.fmt(c)}\t{kind}\t{detail}")
    if empties:
        print(f"  (+ {empties} empty scrolls: coordinate-climb "
              f"materialization inside Library 10000, no content)")
    return 0


def cmd_region_wipe(a):
    if os.path.exists(a.out) and not a.force:
        print(f"REFUSING: {a.out} exists (pass --force)", file=sys.stderr)
        return 1
    scrolls = phext_io.load_phext(a.phext)
    kept = {c: s for c, s in scrolls.items() if not is_region(c)}
    removed = len(scrolls) - len(kept)
    with open(a.out, "wb") as f:
        f.write(phext_io.implode(kept))
    print(f"wiped {removed} region scrolls; {len(kept)} scrolls remain "
          f"-> {a.out}")
    return 0


def cmd_seal(a):
    out = a.out or (a.phext + ".xz")
    if os.path.exists(out) and not a.force:
        print(f"REFUSING: {out} exists (pass --force)", file=sys.stderr)
        return 1
    with open(a.phext, "rb") as f:
        data = f.read()
    sealed = lzma.compress(data, format=lzma.FORMAT_XZ,
                           check=lzma.CHECK_CRC64, preset=9 | lzma.PRESET_EXTREME)
    with open(out, "wb") as f:
        f.write(sealed)
    print(f"sealed {a.phext} ({len(data)} B, sha256 {sha256(data)})")
    print(f"  -> {out} ({len(sealed)} B, {100.0 * len(sealed) / len(data):.1f}% "
          f"of plain)")
    return 0


def cmd_unseal(a):
    out = a.out or (a.sealed[:-3] if a.sealed.endswith(".xz") else a.sealed + ".plain")
    if os.path.exists(out) and not a.force:
        print(f"REFUSING: {out} exists (pass --force)", file=sys.stderr)
        return 1
    with open(a.sealed, "rb") as f:
        sealed = f.read()
    data = lzma.decompress(sealed, format=lzma.FORMAT_XZ)
    with open(out, "wb") as f:
        f.write(data)
    print(f"unsealed {a.sealed} -> {out} ({len(data)} B, sha256 {sha256(data)})")
    return 0


def cli(argv):
    ap = argparse.ArgumentParser(prog="phcc (builds)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build-region")
    psub = p.add_subparsers(dest="sub", required=True)
    q = psub.add_parser("list")
    q.add_argument("--phext", required=True)
    q.set_defaults(fn=cmd_region_list)
    q = psub.add_parser("wipe")
    q.add_argument("--phext", required=True)
    q.add_argument("--out", required=True)
    q.add_argument("--force", action="store_true")
    q.set_defaults(fn=cmd_region_wipe)

    p = sub.add_parser("seal")
    p.add_argument("--phext", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_seal)

    p = sub.add_parser("unseal")
    p.add_argument("--sealed", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_unseal)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
