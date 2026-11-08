#!/usr/bin/env python3
"""phcc_migrate.py — the canonical bidirectional phcc migration engine.

User-facing interface (Will's ruling, 2026-11-07):

    phcc unpack --phext X.phext --out DIR [--from vol2|vol3]
    phcc pack   --tree DIR --out Y.phext [--base Z.phext]

This module is the engine; the `phcc` executable next to it is a thin
dispatcher that maps unpack->export, pack->import. The subcommands are
also usable directly:

    phcc_migrate.py export ...   (== phcc unpack)
    phcc_migrate.py import ...   (== phcc pack)

What is reused vs adapted (nothing reinvented silently):

  - phext byte format (walk_bytes / implode / fmt): phext_io.py,
    copied unchanged from the Slice 0/1 tools lineage.
  - unpack --from vol2: ADAPTED from Slice 0 tools/export_phcc.py
    (manifest-driven, verify-before-write), extended to also write a
    manifest file into the exported tree.
  - unpack --from vol3: ADAPTED from importer v4 tools/reassemble.py
    (index-authoritative segment reassembly; file-level files fall
    back to the Volume 2 bridge scroll), same verification rules.
  - unpack (both routes) expands dedup stubs written by
    `phcc analyze --apply` (phext_io dedup refs): auto-detected,
    target verified against the stub's SHA-256, then the usual
    manifest/index verification runs on the expanded bytes — see
    METHODS.md, "analyze".
  - pack stage A (tree -> Volume 1 + Volume 2 + placement manifest):
    ADAPTED from Slice 0 tools/import_phcc.py (placement table
    `place()` copied verbatim, plus extensions: tools/** -> Book 10
    Chapter 9; placement completion 2026-11-07 — README.md -> Book 10
    Chapter 1 (the PATCHES.md precedent), docs/** -> the Docs phase
    (Collection 9) via place_full(), phcc.phext.xz excluded by name
    (the generated seal of the phext), and phext/** excluded by name
    (carried by the Sec-14 placement addendum at Book 10 Chapter 10;
    pack routing would renumber phext.c/phext.h). phcc.phext is
    excluded by name for the same reason monolith.phext was — a
    phext cannot byte-exactly contain itself). Differences from the
    original: the tree need
    not be a git checkout (plain directory walk, modes from the
    filesystem), and Volume 1 may be inherited from --base instead
    of read from a monolith.phext in the tree.
  - pack stage B (Volume 3 member segmentation): REUSED, not
    adapted — the original importer v3 (import_fn.py) and importer
    v4 (import_v4.py) are run as subprocesses against the stage-A
    phext, exactly as the slice passes ran them. They require a
    Python with tree-sitter + tree-sitter-c importable (the
    granularity venv); see --ts-python.

Invariants and non-invariants are documented in METHODS.md.
Stdlib only (this engine itself).
"""
import argparse, hashlib, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phext_io import (walk_bytes, implode, fmt, sha256, parse_coord,
                      parse_dedup_ref)

LEVEL_BYTES = [0x01, 0x1F, 0x1E, 0x1D, 0x1C, 0x1A, 0x19, 0x18, 0x17]
DELIM_SET = set(LEVEL_BYTES)
MANIFEST_COORD = (1, 1, 1, 1, 2, 10, 1, 1, 1)
NOTES_COORD = (1, 1, 1, 1, 2, 10, 1, 2, 1)
MANIFEST_NAME = "phcc-manifest.tsv"


# ------------------------------------------------------------ shared
def load_scrolls(path):
    return dict(walk_bytes(open(path, "rb").read()))


def manifest_entries(scrolls):
    if MANIFEST_COORD not in scrolls:
        raise SystemExit("FATAL: placement manifest scroll "
                         "(1.1.1/1.2.10/1.1.1) not found in phext")
    entries = []
    for line in scrolls[MANIFEST_COORD].decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        path, coord_s, sha, size, mode = line.split("\t")
        entries.append({"path": path, "coord": parse_coord(coord_s),
                        "sha": sha, "size": int(size), "mode": mode})
    return entries


def write_file(out, path, data, mode):
    dest = os.path.join(out, path)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    os.chmod(dest, 0o755 if mode == "100755" else 0o644)


# ------------------------------------------------------------ unpack
def resolve_stub(scrolls, data, segment, stats):
    """Expand a dedup stub (phext_io dedup refs, written by
    `phcc analyze --apply`) to the bytes it stands for. Returns None
    when `data` is not a stub. segment=True: stub and target are
    Volume 3 segment payloads — the target scroll's post-header
    bytes are the payload, and the stub's SHA-256 names those bytes
    (the value the file index records). segment=False: stub and
    payload are whole scrolls (Volume 2 file scrolls). Raises
    ValueError on any inconsistency — a stub whose target is
    missing, is itself a stub, or does not hash to the stub's
    SHA-256 is corruption, and unpack fails that file loudly rather
    than fall back to anything. Detection is auto (a payload is a
    stub iff it matches the stub format in full) and expansion is
    always verified before the caller's manifest/index checks run
    on the expanded bytes, so a deduplicated phext unpacks under
    exactly the same verification rules as a plain one."""
    ref = parse_dedup_ref(data)
    if ref is None:
        return None
    coord, want = ref
    target = scrolls.get(coord)
    if target is None:
        raise ValueError(f"dedup target {fmt(coord)} not present in phext")
    if segment:
        if b"\n" not in target:
            raise ValueError(f"dedup target {fmt(coord)} is headerless")
        payload = target.split(b"\n", 1)[1]
    else:
        payload = target
    if parse_dedup_ref(payload) is not None:
        raise ValueError(f"dedup target {fmt(coord)} is itself a stub "
                         "(chains are never written and never followed)")
    if sha256(payload) != want:
        raise ValueError(f"dedup target {fmt(coord)} payload sha256 "
                         f"{sha256(payload)[:16]}… != stub's {want[:16]}…")
    if stats is not None:
        stats["dedup_refs"] = stats.get("dedup_refs", 0) + 1
    return payload


def unpack_vol2(scrolls, entries, stats=None):
    """Yield (path, data, mode, ok, why)."""
    for e in entries:
        data = scrolls.get(e["coord"])
        if data is None:
            yield e["path"], None, e["mode"], False, "scroll missing from phext"
            continue
        route = "vol2"
        try:
            resolved = resolve_stub(scrolls, data, segment=False,
                                    stats=stats)
        except ValueError as ex:
            yield e["path"], None, e["mode"], False, f"dedup stub: {ex}"
            continue
        if resolved is not None:
            data, route = resolved, "vol2+dedup-ref"
        if sha256(data) != e["sha"] or len(data) != e["size"]:
            yield e["path"], None, e["mode"], False, \
                f"SHA-256/size mismatch vs manifest ({sha256(data)[:16]}… != {e['sha'][:16]}…)"
        else:
            yield e["path"], data, e["mode"], True, route


def unpack_vol3(scrolls, entries, stats=None):
    """Reassemble from Volume 3 segment scrolls where a file index
    exists (same identification rule as reassemble.py: magic header +
    path + file hash must all match, so structural empty scrolls can
    never masquerade as an index); bridge from Volume 2 otherwise.
    The bridge route expands whole-scroll dedup stubs and the
    segment route expands per-segment stubs, both via resolve_stub,
    before any hash check runs."""
    for e in entries:
        v2 = e["coord"]
        idx = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        raw_idx = scrolls.get(idx, b"")
        structured = raw_idx.startswith(b"# phcc file index") and \
            f"# path: {e['path']}\n".encode() in raw_idx and \
            f"# sha256: {e['sha']} ".encode() in raw_idx
        if not structured:
            data = scrolls.get(v2)
            if data is None:
                yield e["path"], None, e["mode"], False, "bridge scroll missing"
                continue
            route = "vol3-bridge"
            try:
                resolved = resolve_stub(scrolls, data, segment=False,
                                        stats=stats)
            except ValueError as ex:
                yield e["path"], None, e["mode"], False, \
                    f"bridge dedup stub: {ex}"
                continue
            if resolved is not None:
                data, route = resolved, "vol3-bridge+dedup-ref"
            if sha256(data) != e["sha"] or len(data) != e["size"]:
                yield e["path"], None, e["mode"], False, "bridge scroll hash mismatch"
            else:
                yield e["path"], data, e["mode"], True, route
            continue
        table, why = [], None
        for line in raw_idx.decode("utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            scr, kind, name, form, span, psha = line.split("\t")
            table.append((int(scr), span, psha))
        parts, expect = [], 0
        for scr, span, psha in table:
            s, en = (int(x) for x in span.split("-"))
            if s != expect:
                why = f"span discontinuity at scroll {scr}: {s} != {expect}"
                break
            expect = en
            seg = scrolls.get((1, 1, 1, 4, 3, v2[5], v2[6], v2[7], scr))
            if seg is None or b"\n" not in seg:
                why = f"segment scroll {scr} missing or headerless"
                break
            payload = seg.split(b"\n", 1)[1]
            try:
                resolved = resolve_stub(scrolls, payload, segment=True,
                                        stats=stats)
            except ValueError as ex:
                why = f"segment scroll {scr} dedup stub: {ex}"
                break
            if resolved is not None:
                payload = resolved
            if sha256(payload) != psha or len(payload) != en - s:
                why = f"segment scroll {scr} payload hash/length mismatch"
                break
            parts.append(payload)
        if why is not None:
            yield e["path"], None, e["mode"], False, why
            continue
        data = b"".join(parts)
        if sha256(data) != e["sha"] or len(data) != e["size"]:
            yield e["path"], None, e["mode"], False, "reassembled bytes != manifest sha256"
        else:
            yield e["path"], data, e["mode"], True, "vol3-segments"


def cmd_export(a):
    if os.path.isdir(a.out) and os.listdir(a.out) and not a.force:
        print(f"REFUSING: {a.out} exists and is not empty (pass --force)",
              file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    scrolls = load_scrolls(a.phext)
    entries = manifest_entries(scrolls)
    print(f"manifest: {len(entries)} files; source: --from {a.source}")
    stats = {}
    gen = unpack_vol2(scrolls, entries, stats) if a.source == "vol2" \
        else unpack_vol3(scrolls, entries, stats)
    ok, failed, routes = 0, [], {}
    man_lines = ["# phcc-manifest — written by phcc unpack "
                 f"(phcc_migrate export --from {a.source})",
                 "# source phext sha256: " + sha256(open(a.phext, 'rb').read()),
                 "# columns: path <TAB> sha256 <TAB> size <TAB> git-mode <TAB> route"]
    for path, data, mode, good, why in gen:
        if not good:
            failed.append((path, why))
            continue
        write_file(a.out, path, data, mode)
        routes[why] = routes.get(why, 0) + 1
        man_lines.append(f"{path}\t{sha256(data)}\t{len(data)}\t{mode}\t{why}")
        ok += 1
    with open(os.path.join(a.out, MANIFEST_NAME), "w") as f:
        f.write("\n".join(man_lines) + "\n")
    print(f"verified + written: {ok}/{len(entries)}  routes: {routes}")
    if stats.get("dedup_refs"):
        print(f"dedup stubs expanded: {stats['dedup_refs']} "
              f"(each verified against its stub SHA-256)")
    print(f"manifest written: {os.path.join(a.out, MANIFEST_NAME)}")
    if failed:
        print("UNPACK FAILURES:", file=sys.stderr)
        for p, why in failed:
            print(f"  {p}: {why}", file=sys.stderr)
        return 1
    print("unpack OK — every file SHA-256-verified against the in-phext manifest")
    return 0


# ------------------------------------------------------------ pack, stage A
# Placement table copied verbatim from Slice 0 tools/import_phcc.py
# (design §1 Books), with ONE extension marked below.
ARCH = ["x86_64", "i386", "arm", "arm64", "riscv64", "c67"]

def place(path):
    """Return (book, chapter) for a repo-relative path, or None."""
    base = os.path.basename(path)
    if path == "tcc.c": return (1, 1)
    if path in ("libtcc.c", "libtcc.h"): return (1, 2)
    if path == "tccpp.c": return (2, 1)
    if path == "tcctok.h" or ("/" not in path and base.endswith("-tok.h")): return (2, 2)
    if path == "tccgen.c": return (3, 1)
    if path == "tcc.h": return (3, 2)
    if path == "tccasm.c": return (4, 1)
    if "/" not in path and (base.endswith("-asm.c") or base.endswith("-asm.h")): return (4, 2)
    if path in ("tccelf.c", "elf.h"): return (5, 1)
    if path in ("tccpe.c", "tcccoff.c", "tccmacho.c", "coff.h"): return (5, 2)
    if "/" not in path and base.endswith("-link.c"): return (5, 3)
    if "/" not in path and base.endswith("-gen.c"):
        arch = base[: -len("-gen.c")]
        if arch in ARCH: return (6, ARCH.index(arch) + 1)
        if arch == "il": return (6, 7)
    if path == "il-opcodes.h": return (6, 7)
    if path.startswith("lib/"):
        if base in ("libtcc1.c", "runmain.c", "dsohandle.c"): return (7, 1)
        if base in ("bcheck.c", "bt-dll.c", "bt-exe.c", "bt-log.c"): return (7, 2)
        if base in ("builtin.c", "stdatomic.c", "va_list.c", "atomic.S", "alloca.S", "alloca-bt.S"): return (7, 3)
        if base in ("armeabi.c", "armflush.c", "lib-arm64.c", "pic86.S"): return (7, 4)
        if base == "tcov.c": return (7, 5)
        if base == "Makefile": return (7, 6)
        return None
    if path == "tccrun.c": return (7, 5)
    if path in ("tccdbg.c", "dwarf.h", "stab.h", "stab.def"): return (8, 1)
    if path == "tcctools.c": return (8, 2)
    if path.startswith("include/"): return (9, 1)
    if path == "tcclib.h": return (9, 2)
    if path.startswith("win32/include/"): return (9, 3)
    if path.startswith("win32/lib/"): return (9, 4)
    if path.startswith("win32/"): return (9, 5)
    if path in ("Makefile", "configure", "conftest.c", ".gitignore",
                "slurp.sh", "PATCHES.md", "README.md",
                "texi2pod.pl"): return (10, 1)
    if path.startswith("tests/"):
        if "/" not in path[len("tests/"):]: return (10, 2)
        if path.startswith("tests/tests2/"): return (10, 3)
        if path.startswith("tests/pp/"): return (10, 4)
        return (10, 5)
    if path in ("README", "Changelog", "COPYING", "RELICENSING", "TODO",
                "USES", "VERSION", "CodingStyle", "tcc-doc.texi"): return (10, 6)
    if path.startswith("examples/"): return (10, 7)
    if path.startswith(".github/"): return (10, 8)
    # EXTENSION (phcc_migrate, not Slice 0): the migration/tooling set
    # that now ships in the repo gets Book 10 Chapter 9.
    if path.startswith("tools/"): return (10, 9)
    return None

def place_full(path):
    """Return (collection, volume, book, chapter) for a path, or None.

    Everything place() covers lives in the Source phase (Collection
    4), Volume 2 — place_full() just widens its (book, chapter) with
    that prefix. The one further extension (placement completion,
    2026-11-07): the project's documentation set, docs/**, goes to
    the Docs phase (Collection 9) of the 6D UML model — Volume 2
    (the working volume every phase's current content uses), Book 1
    (project documentation), Chapter 1 (guides), Section = file,
    path-sorted: the same file-sectioning idiom as Source, at the
    smallest scale that fits. Tree documentation belongs in the
    phase the model reserves for it, not in Source."""
    if path.startswith("docs/"):
        return (9, 2, 1, 1)
    bc = place(path)
    if bc is None:
        return None
    return (4, 2, bc[0], bc[1])

def phext_dir_exclusion(path):
    """Why a phext/** path is excluded from pack placement (the
    reason is recorded in the manifest, per file).

    The phext/ C parity library already has its phext home: Source
    Book 10 Chapter 10, placed by the builds pass's Sec-14 placement
    addendum (Meta 1.1.1/1.2.10/1.14.1), whose stated rule is
    "phext/** -> Book 10, Chapter 10". place() must NOT also route
    the directory: pack assigns Sections by path-sort within a
    chapter, so routing all eight phext/** files would renumber
    phext.c/phext.h from the addendum's Sections 1-2 to 3-4 and
    split each file across two addresses at the next merge. The
    directory is therefore carried by the addendum as one component
    and excluded here, by name."""
    if path in ("phext/phext.c", "phext/phext.h"):
        return ("carried at Source Book 10 Ch 10 Secs 1-2 by the "
                "Sec-14 placement addendum (Meta 1.1.1/1.2.10/1.14.1); "
                "pack routing would renumber it (path-sort among all "
                "phext/** files puts it at Sec 3-4) and split the "
                "file across two addresses")
    if path == "phext/tests/regression-1-helios.phext":
        return ("a phext file: its bytes ARE phext delimiter bytes "
                "(0x01/0x17/0x1E present), so it cannot be a scroll "
                "byte-exactly — the same exclusion as phcc.phext")
    return ("rides with the phext/ library's Sec-14 addendum "
            "placement (Source Book 10 Ch 10): the directory is "
            "carried as one component, not split across two manifests")

BOOK_NAMES = {1: "Driver & public API", 2: "Preprocessor & tokenizer",
              3: "Parser & codegen core", 4: "Assembler",
              5: "Object formats & linker", 6: "Target backends",
              7: "Runtime & execution", 8: "Debug info & tools",
              9: "Shipped headers", 10: "Build & project"}

LAYOUT_NOTES = """# phcc.phext — layout notes (phcc pack, phcc_migrate stage A + importers v3/v4)

One file, whole project. Outer dimensions 1.1.1 throughout.

- Collection 1 (Meta), Volume 1: the 2024 flat slurp — 319 scrolls at
  1.1.1/1.1.1/1.1.N, copied verbatim from the tree's monolith.phext or
  inherited from the --base phext. Historical; never rewritten.
- Collection 1 (Meta), Volume 2, Book 10: Section 1 = placement
  manifest for Volume 2 Source (path, coordinate, SHA-256, size, git
  mode); Section 2 = this notes scroll.
- Collection 4 (Source), Volume 2: the phcc tree. Book = module,
  Chapter = component, Section = file (path-sorted within chapter),
  Scroll 1 = file bytes, byte-exact. (Placement: Slice 0 §1 Books,
  plus tools/** at Book 10 Chapter 9 and README.md at Book 10
  Chapter 1.)
- Collection 9 (Docs), Volume 2, Book 1, Chapter 1: the project's
  docs/*.md guides, Section = file (path-sorted within chapter),
  Scroll 1 = file bytes, byte-exact — tree documentation is placed
  in the Docs phase of the 6D UML model, not in Source.
- Collection 4 (Source), Volume 3: member-level segmentation of
  Volume 2 (importer v3 segmentation, importer v4 classification
  refinement) — index scroll + segment scrolls per structured file;
  file-level files ride the Volume 2 bridge. Meta Volume 3 Book 10
  holds the rebind manifest, layout notes, degradation register.
- Excluded from placement: monolith.phext and phcc.phext (a phext
  cannot byte-exactly contain itself — its bytes ARE the delimiters),
  phcc.phext.xz (the generated xz seal OF phcc.phext: a seal is
  produced from the phext, never packed into it), phcc-manifest.tsv
  (unpack's own output), .git (not content), and phext/** — the C
  parity library already lives at Book 10 Chapter 10 under the
  Sec-14 placement addendum, and pack routing would renumber
  phext.c/phext.h and split them across two addresses (one member,
  phext/tests/regression-1-helios.phext, could not be a scroll
  anyway: its bytes are phext delimiters). Exclusions are recorded
  in the manifest, per file, with reasons.
"""

# files never placed: name -> reason recorded in the manifest
EXCLUDED = {
    "monolith.phext": "preserved as Volume 1; a phext cannot byte-exactly contain itself as a scroll",
    "phcc.phext": "a phext cannot byte-exactly contain itself as a scroll",
    "phcc.phext.xz": "the generated seal of phcc.phext (xz of the whole phext, produced by `phcc seal`); a generated artifact is never packed into the phext it seals — unseal regenerates the phext, pack consumes the tree",
    MANIFEST_NAME: "unpack's verification manifest; regenerated on every unpack",
}


def enumerate_tree(tree):
    """[(mode, path)] for every packable file under tree, path-sorted.
    Uses git ls-files when tree is a git work tree (exact git modes),
    else a plain walk (mode from the executable bit)."""
    if os.path.isdir(os.path.join(tree, ".git")):
        try:
            raw = subprocess.run(["git", "-C", tree, "ls-files", "-s", "-z"],
                                 capture_output=True, check=True).stdout
            out = []
            for rec in raw.decode("utf-8").split("\0"):
                if rec.strip():
                    meta, path = rec.split("\t", 1)
                    out.append((meta.split()[0], path))
            out.sort(key=lambda e: e[1])
            return out, "git ls-files"
        except Exception:
            pass  # fall through to the walk
    out = []
    for root, dirs, files in os.walk(tree):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, tree)
            mode = "100755" if os.stat(full).st_mode & 0o111 else "100644"
            out.append((mode, rel))
    out.sort(key=lambda e: e[1])
    return out, "directory walk"


def stage_a(tree, base_phext):
    """Build the Volume 1 + Volume 2 scroll set. Returns dict."""
    scrolls = {}
    # --- Volume 1: monolith in tree wins; else inherit from --base
    mono_path = os.path.join(tree, "monolith.phext")
    if os.path.isfile(mono_path):
        v1 = walk_bytes(open(mono_path, "rb").read())
        for coord, content in v1:
            assert coord[3] == 1 and coord[4] == 1, coord
            scrolls[coord] = content
        print(f"volume 1: {len(v1)} scrolls verbatim from tree's monolith.phext")
    elif base_phext:
        base = load_scrolls(base_phext)
        v1 = {c: b for c, b in base.items() if c[3] == 1 and c[4] == 1 and b}
        scrolls.update(v1)
        print(f"volume 1: {len(v1)} scrolls inherited from --base {base_phext}")
    else:
        raise SystemExit("FATAL: no Volume 1 source — the tree has no "
                         "monolith.phext and no --base phext was given")
    # --- placement
    entries, how = enumerate_tree(tree)
    print(f"tree enumeration: {len(entries)} files ({how})")
    by_chapter, unplaced, excluded = {}, [], []
    for mode, path in entries:
        if path in EXCLUDED:
            excluded.append((path, EXCLUDED[path]))
            continue
        if path.startswith("phext/"):
            excluded.append((path, phext_dir_exclusion(path)))
            continue
        pf = place_full(path)
        if pf is None:
            unplaced.append(path)
        else:
            by_chapter.setdefault(pf, []).append((path, mode))
    if unplaced:
        print("UNPLACED FILES — pack aborted:", *unplaced, sep="\n  ",
              file=sys.stderr)
        raise SystemExit(1)
    manifest_lines = [
        "# phcc placement manifest — phcc pack (phcc_migrate stage A)",
        "# placement: Slice 0 importer v2 §1 Books (+ tools/** -> Book 10 Ch 9,"
        " README.md -> Book 10 Ch 1, docs/** -> Docs Collection 9 Vol 2 Book 1 Ch 1)",
        "# columns: path <TAB> coordinate <TAB> sha256 <TAB> size <TAB> git-mode",
    ]
    total = 0
    for prefix, files in sorted(by_chapter.items()):
        for i, (path, mode) in enumerate(files, start=1):
            data = open(os.path.join(tree, path), "rb").read()
            bad = DELIM_SET & set(data)
            if bad:
                print(f"DELIMITER BYTES in {path}: "
                      f"{sorted(hex(b) for b in bad)} — aborting", file=sys.stderr)
                raise SystemExit(1)
            coord = (1, 1, 1) + prefix + (i, 1)
            scrolls[coord] = data
            total += len(data)
            manifest_lines.append(
                f"{path}\t{fmt(coord)}\t{sha256(data)}\t{len(data)}\t{mode}")
    for path, why in excluded:
        manifest_lines.append(f"# EXCLUDED\t{path}\t{why}")
    scrolls[MANIFEST_COORD] = ("\n".join(manifest_lines) + "\n").encode()
    scrolls[NOTES_COORD] = LAYOUT_NOTES.encode()
    print(f"volume 2: {sum(len(v) for v in by_chapter.values())} files placed, "
          f"{total} content bytes; excluded: {[p for p, _ in excluded]}")
    return scrolls


# ------------------------------------------------------------ pack, stage B
def find_tool(name):
    home = os.path.expanduser("~")
    for d in (HERE,
              os.path.join(home, "workspace/phcc-consolidated/tools"),
              os.path.join(home, "workspace/phcc-importer-v4/tools"),
              os.path.join(home, "workspace/phcc-slice3-granularity/tools")):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def find_ts_python(explicit):
    home = os.path.expanduser("~")
    cands = [explicit, os.environ.get("PHCC_TS_PYTHON"),
             os.path.join(home, "workspace/phcc-slice3-granularity/work/venv/bin/python"),
             os.path.join(HERE, "venv/bin/python"),
             sys.executable]
    for c in cands:
        if not c or not os.path.exists(c):
            continue
        r = subprocess.run([c, "-c", "import tree_sitter, tree_sitter_c"],
                           capture_output=True)
        if r.returncode == 0:
            return c
    raise SystemExit("FATAL: no Python with tree-sitter + tree-sitter-c found "
                     "for pack stage B (importers v3/v4). Pass --ts-python "
                     "or set PHCC_TS_PYTHON.")


def cmd_import(a):
    scrolls = stage_a(a.tree, a.base)
    blob = implode(scrolls)
    if a.no_vol3:
        with open(a.out, "wb") as f:
            f.write(blob)
        print(f"pack OK (Volume 2 only, --no-vol3): {a.out}  {len(blob)} bytes  "
              f"sha256 {sha256(blob)}")
        return 0
    fn_py, v4_py = find_tool("import_fn.py"), find_tool("import_v4.py")
    if not fn_py or not v4_py:
        print("FATAL: import_fn.py / import_v4.py (importers v3/v4) not found "
              "next to phcc_migrate.py or in the known slice tool dirs",
              file=sys.stderr)
        return 1
    py = find_ts_python(a.ts_python)
    print(f"stage B: importers v3+v4 via {py}")
    with tempfile.TemporaryDirectory(prefix="phcc-pack-") as td:
        base_p = os.path.join(td, "stage-a.phext")
        fn_p = os.path.join(td, "stage-b.phext")
        with open(base_p, "wb") as f:
            f.write(blob)
        for tool, src, dst in ((fn_py, base_p, fn_p), (v4_py, fn_p, a.out)):
            cmd = [py, tool, "--base", src, "--out", dst,
                   "--stats", os.path.join(td, "stats.json")]
            if tool == v4_py:  # only importer v4 takes --diff
                cmd += ["--diff", os.path.join(td, "diff.json")]
            print("+", " ".join(cmd[1:3]), f"--base {os.path.basename(src)} "
                  f"--out {os.path.basename(dst)}")
            r = subprocess.run(cmd, capture_output=True, text=True)
            sys.stdout.write(r.stdout)
            if r.returncode != 0:
                sys.stderr.write(r.stderr)
                print(f"FATAL: {os.path.basename(tool)} failed", file=sys.stderr)
                return 1
    out_blob = open(a.out, "rb").read()
    print(f"pack OK: {a.out}  {len(out_blob)} bytes  sha256 {sha256(out_blob)}")
    return 0


# ------------------------------------------------------------ cli
def cli(argv):
    ap = argparse.ArgumentParser(prog="phcc_migrate",
                                 description="phcc phext <-> directory tree migration")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="phext -> directory tree (phcc unpack)")
    e.add_argument("--phext", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--from", dest="source", choices=("vol2", "vol3"),
                   default="vol2")
    e.add_argument("--force", action="store_true",
                   help="write into a non-empty directory")
    e.set_defaults(fn=cmd_export)

    i = sub.add_parser("import", help="directory tree -> phext (phcc pack)")
    i.add_argument("--tree", required=True)
    i.add_argument("--out", required=True)
    i.add_argument("--base", default=None,
                   help="phext to inherit Volume 1 (the 2024 slurp) from "
                        "when the tree has no monolith.phext")
    i.add_argument("--no-vol3", action="store_true",
                   help="stop after stage A (Volume 1+2 only, no member "
                        "segmentation; no tree-sitter needed)")
    i.add_argument("--ts-python", default=None,
                   help="Python with tree-sitter for stage B")
    i.set_defaults(fn=cmd_import)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
