#!/usr/bin/env python3
"""upstream_carry.py — pristine upstream TinyCC -> upstream.phext.

phcc carries its own (forked) TinyCC tree in phcc.phext. This tool
carries the PRISTINE upstream tree — the exact commit phcc's base
pin names (PATCHES.md, U-series) — into a companion phext,
upstream.phext, so the fork's divergence is always measurable
against a sealed, byte-exact copy of what it diverged from.

Carry model (the phst precedent, wbic16/phst): the SEAL ships in
the repo (upstream.phext.xz at the repository root, beside
phcc.phext.xz); the plain upstream.phext is generated on demand by
this script and checkable against UPSTREAM.md's recorded hashes.
File grain only — member grain is phcc.phext's own importer job,
not this carry's.

Layout of the produced phext (outer Library.Shelf.Series = 1.1.1):
  Collection 1 (Meta), Vol 1, Book 1, Ch 1, Sec 1, Scroll 1
      = identity scroll: upstream repo + pinned commit.
  Collection 1 (Meta), Vol 2, Book 10, Ch 1:
      Sec 1 = placement manifest (path -> coordinate, SHA-256,
              size, git mode, encoding)
      Sec 2 = layout notes
      Sec 3 = exclusions register (gitlinks with pinned SHAs;
              anything not placed, with reason)
  Collection 4 (Source), Vol 2 — the file-grain carry:
      Book    = top-level area: 1 lib/, 2 include/, 3 tests/,
                4 tests2/, 5 win32/, 6 examples/, 7 doc/,
                8 everything else (repository-root files — the
                compiler core — and any other top-level directory,
                which becomes the chapter component name)
      Chapter = second-level component within the book (sorted;
                files directly in an area root form component "")
      Section = file, sequential within chapter, path-sorted
      Scroll 1 = the file's bytes (verbatim, or a canonical
                phext-binary base64 scroll — see encode_scroll)
  Collection 10 (Proofs), Vol 99, Book 99, Ch 99, Sec 99, Scroll 99
      = endmark scroll (structural; guarantees the last placed
        scroll is never the trailing byte).

Phext byte format + walk/implode are the phcc/phst importer
lineage's (import_phcc.py / phext_io.py), copied so this phext is
byte-format identical in kind to phcc.phext and phst.phext.

A scroll holds the file's bytes verbatim when they are valid UTF-8
with no phext delimiter byte and do not begin with the binary
header; otherwise it holds the canonical libphext 0.5.0 binary form
(scroll = header line 'phext-binary:1:base64' + LF + RFC 4648
base64, padding required, no wrapping), and the manifest's
encoding column says which. The manifest's SHA-256 is always over
the ORIGINAL file bytes.

Import scope = `git ls-files` of a pristine checkout at the pin
(the build refuses a dirty tree or a HEAD other than --pin).
Gitlink content belongs to other repos and is registered, not
imported. Symlinks are placed: scroll content = target bytes,
git mode 120000 in the manifest, restored as symlinks on unpack.

Stdlib only. Usage:
  upstream_carry.py build  --repo DIR --pin SHA --out FILE.phext
                           --stats FILE.json
  upstream_carry.py unpack --phext FILE.phext --out DIR
"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------- phext io
LEVEL_BYTES = [0x01, 0x1F, 0x1E, 0x1D, 0x1C, 0x1A, 0x19, 0x18, 0x17]  # library..scroll
DELIM_TO_LEVEL = {b: i for i, b in enumerate(LEVEL_BYTES)}
_DELIM_RE = re.compile(rb"[\x01\x17-\x1f]")

BINARY_HEADER = b"phext-binary:1:base64"


def fmt(coord):
    return f"{coord[0]}.{coord[1]}.{coord[2]}/{coord[3]}.{coord[4]}.{coord[5]}/{coord[6]}.{coord[7]}.{coord[8]}"


def parse_coord(s):
    a, b, c = s.split("/")
    parts = []
    for grp in (a, b, c):
        parts += [int(x) for x in grp.split(".")]
    return tuple(parts)


def walk_bytes(data):
    """Dead-reckoning byte walk — yields (coord_tuple, bytes) so
    scrolls stay byte-exact. The lineage walk (phcc/phst)."""
    coord = [1] * 9
    out = []
    pos = 0
    for m in _DELIM_RE.finditer(data):
        out.append((tuple(coord), data[pos:m.start()]))
        lvl = DELIM_TO_LEVEL[m.group()[0]]
        coord[lvl] += 1
        for j in range(lvl + 1, 9):
            coord[j] = 1
        pos = m.end()
    out.append((tuple(coord), data[pos:]))
    if out and out[-1][1] == b"":
        out.pop()
    return out


def implode(scrolls):
    """scrolls: dict coord_tuple -> bytes. The lineage emitter."""
    out = bytearray()
    state = [1] * 9
    for target in sorted(scrolls):
        for lvl in range(9):
            while state[lvl] < target[lvl]:
                out.append(LEVEL_BYTES[lvl])
                state[lvl] += 1
                for j in range(lvl + 1, 9):
                    state[j] = 1
        assert tuple(state) == target, (state, target)
        out += scrolls[target]
    return bytes(out)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encode_scroll(data):
    """Return (scroll_bytes, encoding) for one file's bytes.

    'raw': valid UTF-8, no phext delimiter byte, does not begin
    with the binary header line — placed verbatim. Otherwise
    'binary': the canonical libphext binary format. Standing
    ingestion rule: non-UTF-8 data observed in an incoming scroll
    is encoded base64 verbatim.
    """
    if not data.startswith(BINARY_HEADER) and _DELIM_RE.search(data) is None:
        try:
            data.decode("utf-8")
            return data, "raw"
        except UnicodeDecodeError:
            pass
    return BINARY_HEADER + b"\n" + base64.b64encode(data), "binary"


def decode_scroll(scroll, encoding):
    if encoding == "binary":
        assert scroll.startswith(BINARY_HEADER + b"\n"), "binary scroll missing header"
        return base64.b64decode(scroll[len(BINARY_HEADER) + 1:])
    return scroll


# ------------------------------------------------------------- layout
BOOKS = {"lib": 1, "include": 2, "tests": 3, "tests2": 4,
         "win32": 5, "examples": 6, "doc": 7}
BOOK_OTHER = 8
ENDMARK = (1, 1, 1, 10, 99, 99, 99, 99, 99)
MANIFEST_COORD = (1, 1, 1, 1, 2, 10, 1, 1, 1)
NOTES_COORD = (1, 1, 1, 1, 2, 10, 1, 2, 1)
EXCL_COORD = (1, 1, 1, 1, 2, 10, 1, 3, 1)
IDENT_COORD = (1, 1, 1, 1, 1, 1, 1, 1, 1)

LAYOUT_NOTES = """# upstream.phext — layout notes (file grain)

Carry of the pristine upstream TinyCC tree at phcc's base pin
(see the identity scroll for the commit, UPSTREAM.md in wbic16/phcc
for the full provenance record and the regeneration command).

Source (Collection 4), Volume 2 carries the entire upstream tree at
file grain. Book = top-level area: 1 lib/, 2 include/, 3 tests/,
4 tests2/, 5 win32/, 6 examples/, 7 doc/, 8 everything else
(repository-root files — the compiler core — plus any other
top-level directory, whose name becomes the chapter component).
Chapter = second-level component within the book, assigned in
sorted order; files directly under an area root are the first
component (""). Section = one file, sequential within its chapter,
path-sorted. Scroll 1 = the file itself.

A scroll holds the file's bytes verbatim when they are valid UTF-8
with no phext delimiter byte; otherwise it holds the canonical
binary form (header line 'phext-binary:1:base64' + base64), and the
manifest's encoding column says which. The manifest (Meta Vol 2,
Book 10, Ch 1, Sec 1) is authoritative: path, coordinate, SHA-256 of
the ORIGINAL bytes, size, git mode, encoding.

Exclusions (Meta Vol 2, Book 10, Ch 1, Sec 3): gitlinks, if the
pinned tree has any, are registered with the SHA the superproject
pins; their content lives in other repositories.
"""


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, check=True).stdout


def placement(entries):
    """entries: list of paths (files only). Returns {path: coord}."""
    groups = {}
    for path in entries:
        parts = path.split("/")
        area = parts[0] if len(parts) > 1 else "(root)"
        book = BOOKS.get(area, BOOK_OTHER)
        if book == BOOK_OTHER:
            comp = parts[0] if len(parts) > 1 else ""
        else:
            comp = parts[1] if len(parts) > 2 else ""
        groups.setdefault((book, comp), []).append(path)
    books = {}
    for (book, comp) in groups:
        books.setdefault(book, set()).add(comp)
    chapter_of = {}
    for book, comps in books.items():
        for i, comp in enumerate(sorted(comps)):
            chapter_of[(book, comp)] = i + 1
    coords = {}
    for (book, comp), paths in groups.items():
        ch = chapter_of[(book, comp)]
        for i, path in enumerate(sorted(paths)):
            coords[path] = (1, 1, 1, 4, 2, book, ch, i + 1, 1)
    return coords


# -------------------------------------------------------------- build
def cmd_build(a):
    head = git(a.repo, "rev-parse", "HEAD").decode().strip()
    if head != a.pin:
        sys.exit(f"refusing: repo HEAD {head} != --pin {a.pin}")
    dirty = git(a.repo, "status", "--porcelain").decode().strip()
    if dirty:
        sys.exit(f"refusing: repo is not a pristine checkout:\n{dirty[:500]}")
    subject = git(a.repo, "log", "-1", "--format=%s").decode().strip()

    raw = git(a.repo, "ls-files", "-s", "-z")
    files, gitlinks = [], []
    modes = {}
    for rec in raw.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, sha = meta.decode().split()[:2]
        path = path.decode("utf-8", "surrogateescape")
        if mode == "160000":
            gitlinks.append((path, sha))
        else:
            files.append(path)
            modes[path] = mode
    files.sort()
    coords = placement(files)

    scrolls = {}
    man_lines = ["# upstream TinyCC placement manifest — file grain",
                 f"# upstream: TinyCC/tinycc @ {head}",
                 "# columns: path <TAB> coordinate <TAB> sha256 <TAB> size <TAB> mode <TAB> encoding"]
    stats = {"upstream_commit": head, "upstream_subject": subject,
             "files": 0, "bytes": 0, "raw_scrolls": 0,
             "binary_scrolls": 0, "binary_files": [], "symlinks": 0,
             "empty_files": 0, "gitlinks": len(gitlinks),
             "per_book": {}}
    for path in files:
        full = os.path.join(a.repo, path)
        mode = modes[path]
        if mode == "120000":
            data = os.readlink(full).encode()
            stats["symlinks"] += 1
        else:
            with open(full, "rb") as f:
                data = f.read()
        coord = coords[path]
        scroll, enc = encode_scroll(data)
        assert coord not in scrolls, f"coordinate collision: {path}"
        scrolls[coord] = scroll
        man_lines.append(f"{path}\t{fmt(coord)}\t{sha256(data)}\t{len(data)}\t{mode}\t{enc}")
        stats["files"] += 1
        stats["bytes"] += len(data)
        if enc == "raw":
            stats["raw_scrolls"] += 1
        else:
            stats["binary_scrolls"] += 1
            stats["binary_files"].append(path)
        if len(data) == 0:
            stats["empty_files"] += 1
        bk = stats["per_book"].setdefault(str(coord[5]), {"files": 0, "bytes": 0})
        bk["files"] += 1
        bk["bytes"] += len(data)

    excl_lines = ["# upstream carry exclusions register",
                  "# gitlinks: submodule pins recorded, content NOT imported (belongs to other repos)",
                  "# columns: path <TAB> pinned-sha <TAB> kind"]
    if gitlinks:
        for path, sha in sorted(gitlinks):
            excl_lines.append(f"{path}\t{sha}\tgitlink")
    else:
        excl_lines.append("# (none — the pinned tree has no gitlinks)")

    ident = ("# upstream.phext — pristine upstream TinyCC, sealed carry\n"
             f"# upstream: https://github.com/TinyCC/tinycc.git @ {head}\n"
             f"# commit subject: {subject}\n"
             "# carry model: the seal (upstream.phext.xz) ships in wbic16/phcc;\n"
             "# this plain phext is generated on demand. Provenance + regeneration:\n"
             "# UPSTREAM.md at the wbic16/phcc repository root.\n"
             f"# {stats['files']} files, {stats['bytes']} bytes, "
             f"{stats['raw_scrolls']} raw + {stats['binary_scrolls']} binary scrolls.\n")
    scrolls[IDENT_COORD] = ident.encode()
    scrolls[MANIFEST_COORD] = ("\n".join(man_lines) + "\n").encode()
    scrolls[NOTES_COORD] = LAYOUT_NOTES.encode()
    scrolls[EXCL_COORD] = ("\n".join(excl_lines) + "\n").encode()
    scrolls[ENDMARK] = "# upstream.phext endmark (structural; see layout notes)\n".encode()

    blob = implode(scrolls)
    with open(a.out, "wb") as f:
        f.write(blob)
    stats["phext_bytes"] = len(blob)
    stats["phext_sha256"] = sha256(blob)
    stats["scrolls_total"] = len(scrolls)

    back = dict(walk_bytes(blob))
    bad = [k for k, v in scrolls.items() if back.get(k) != v]
    assert not bad, f"scrolls altered/missing after walk: {bad[:3]}"
    stats["verify"] = "all scrolls byte-identical after walk of written phext"
    print(f"carried {stats['files']} files, {stats['bytes']} bytes "
          f"({stats['raw_scrolls']} raw + {stats['binary_scrolls']} binary scrolls, "
          f"{stats['symlinks']} symlinks, {stats['empty_files']} empty, "
          f"{stats['gitlinks']} gitlinks registered)")
    print(f"phext: {a.out}  {len(blob)} bytes  sha256 {stats['phext_sha256']}")
    with open(a.stats, "w") as f:
        json.dump(stats, f, indent=1)


# ------------------------------------------------------------- unpack
def cmd_unpack(a):
    with open(a.phext, "rb") as f:
        scrolls = dict(walk_bytes(f.read()))
    man = scrolls[MANIFEST_COORD].decode()
    entries = []
    for line in man.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        path, coord, sha, size, mode, enc = line.split("\t")
        entries.append((path, parse_coord(coord), sha, int(size), mode, enc))
    os.makedirs(a.out, exist_ok=True)
    ok = 0
    for path, coord, sha, size, mode, enc in entries:
        data = decode_scroll(scrolls[coord], enc)
        assert len(data) == size, f"{path}: size {len(data)} != manifest {size}"
        assert sha256(data) == sha, f"{path}: sha256 mismatch"
        dest = os.path.join(a.out, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if mode == "120000":
            if os.path.lexists(dest):
                os.unlink(dest)
            os.symlink(data.decode(), dest)
        else:
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o755 if mode == "100755" else 0o644)
        ok += 1
    print(f"unpack: {ok}/{len(entries)} files written, every file SHA-256-verified, 0 failures")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repo", required=True)
    b.add_argument("--pin", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--stats", required=True)
    b.set_defaults(fn=cmd_build)
    u = sub.add_parser("unpack")
    u.add_argument("--phext", required=True)
    u.add_argument("--out", required=True)
    u.set_defaults(fn=cmd_unpack)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
