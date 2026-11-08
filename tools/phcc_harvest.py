#!/usr/bin/env python3
"""phcc_harvest.py — extract the linker's-eye symbol truth from a built tree.

Usage: phcc_harvest.py TREE OUT.json

OUT.json is the --harvest input to `phcc prune` (see
tools/METHODS.md, prune section).

Walks TREE for object files and archives, runs nm on each, maps every
object to its source file by basename (collisions reported), and
records defined-global / defined-local / undefined symbols per object,
plus archive membership. This is the ground truth the pruner roots
and validates against: what the build actually compiled and what the
link actually needed.
"""
import json, os, re, subprocess, sys, collections

HEAD_RE = re.compile(r"^(?:[^:\[\]]+)(?:\[([^\]]+)\])?:$")

def nm_symbols(path):
    """Return {object_name: (defined_global, defined_local, undefined)}.

    GNU nm -A --format=posix shapes:
      plain object:  "tcc.o: name T value size"
      archive:       "libtcc.a[libtcc.o]: name T value size"
      undefined:     "libtcc.a[libtcc.o]: name U"
    """
    r = subprocess.run(["nm", "-A", "--format=posix", path],
                       capture_output=True, text=True)
    per_obj = collections.defaultdict(lambda: ([], [], []))
    if r.returncode != 0:
        return per_obj
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        m = HEAD_RE.match(parts[0])
        if not m:
            continue
        obj = m.group(1) or os.path.basename(path)
        name = parts[1]
        typ = parts[2]
        g, l, u = per_obj[obj]
        if typ == "U":
            u.append(name)
        elif typ.isupper():
            g.append(name)
        else:
            l.append(name)
    return per_obj

def main():
    tree, out_path = sys.argv[1], sys.argv[2]
    sources = collections.defaultdict(list)
    for root, dirs, files in os.walk(tree):
        if ".git" in root:
            continue
        for f in files:
            if f.endswith((".c", ".S", ".s")):
                rel = os.path.relpath(os.path.join(root, f), tree)
                sources[f].append(rel)
    objects, archives, collisions = {}, {}, []
    for root, dirs, files in os.walk(tree):
        if ".git" in root:
            continue
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, tree)
            if f.endswith(".o"):
                per = nm_symbols(full)
                for obj, (g, l, u) in per.items():
                    base = obj.rsplit(".", 1)[0]
                    # automake per-target objects are named
                    # <target>-<source>.o (libcoreutils_a-xgetcwd.o,
                    # coreutils_ls-ls.o): candidate stems are the
                    # full stem plus every suffix after a '-'
                    stems = [base]
                    while "-" in stems[-1]:
                        stems.append(stems[-1].split("-", 1)[1])
                    cand = []
                    for st in stems:
                        for ext in (".c", ".S", ".s"):
                            cand += sources.get(st + ext, [])
                    cand = list(dict.fromkeys(cand))
                    src = None
                    if len(cand) == 1:
                        src = cand[0]
                    elif len(cand) > 1:
                        # prefer the candidate in the object's directory
                        od = os.path.dirname(rel)
                        pref = [c for c in cand if os.path.dirname(c) == od]
                        src = pref[0] if pref else cand[0]
                        collisions.append({"object": rel, "candidates": cand,
                                           "chose": src})
                    objects[rel] = {"source": src, "defined_global": g,
                                    "defined_local": l, "undefined": u}
            elif f.endswith((".a", ".so")) or (f.endswith(".so.1")):
                per = nm_symbols(full)
                members = {}
                for obj, (g, l, u) in per.items():
                    members[obj] = {"defined_global": g, "defined_local": l,
                                    "undefined": u}
                archives[rel] = members
    # the configured build's dependency graph, from make's own
    # database: the files reachable as prerequisites from the
    # default goal are build-referenced for THIS configuration —
    # generation inputs (gnulib's lib/*.in.h templates) live here.
    # Mere presence in the database is NOT the criterion: automake
    # emits rules for objects the configuration never links, and
    # those sources are exactly what pruning exists to drop.
    # Empty when the tree has no configured Makefile.
    build_prereqs = set()
    mk = os.path.join(tree, "Makefile")
    if os.path.isfile(mk):
        try:
            r = subprocess.run(["make", "-qp", "-C", tree],
                               capture_output=True, text=True, timeout=300)
            edges = {}
            for line in r.stdout.splitlines():
                if ":" not in line or line.startswith(
                        ("\t", "#", " ", ".")):
                    continue
                t, _, rest = line.partition(":")
                t = t.strip()
                if "=" in t or not t or "::" in line:
                    continue
                ps = [p for p in rest.split()
                      if "$" not in p and "%" not in p
                      and not p.startswith("-")]
                if ps:
                    edges.setdefault(t, []).extend(ps)
            seen, stack = set(), ["all"]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for p in edges.get(cur, []):
                    q = p[2:] if p.startswith("./") else p
                    build_prereqs.add(q)
                    if p in edges and p not in seen:
                        stack.append(p)
                    if q in edges and q not in seen:
                        stack.append(q)
        except Exception:
            build_prereqs = set()
    # automake depfiles (.deps/*.Po) are per-object evidence from
    # THIS build: every header the compiler actually opened. The
    # make database's own rules hide object lists behind variable
    # references, so depfile prerequisites are unioned in directly
    # (wrapped lines joined; only plain relative paths kept).
    import glob as _glob
    for po in _glob.glob(os.path.join(tree, "**", ".deps", "*.P*"),
                         recursive=True):
        try:
            text = open(po, errors="replace").read().replace("\\\n", " ")
        except OSError:
            continue
        for line in text.splitlines():
            if ":" not in line:
                continue
            _, _, rest = line.partition(":")
            for p in rest.split():
                if "$" not in p and "%" not in p and \
                        not p.startswith("/") and p != "\\":
                    build_prereqs.add(p[2:] if p.startswith("./") else p)
    result = {"tree": tree, "objects": objects, "archives": archives,
              "collisions": collisions,
              "build_prereqs": sorted(build_prereqs),
              "n_objects": len(objects), "n_archives": len(archives)}
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
    print(f"harvest: {len(objects)} objects, {len(archives)} archives/libs, "
          f"{len(collisions)} basename collisions -> {out_path}")

if __name__ == "__main__":
    main()
