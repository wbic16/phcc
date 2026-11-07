#!/usr/bin/env python3
"""diff_donors.py — scroll-level diff of each donor phext against the
canonical base, plus pairwise collision enumeration among donors'
added/changed sets. Read-only; prints a full accounting and writes
JSON detail to logs/donor-diffs.json."""
import json
import sys

sys.path.insert(0, "/home/hatch/workspace/phcc-slice7/tools")
import phext_io

BASE = "/home/hatch/workspace/phcc-merged/phcc.phext"
DONORS = {
    "slice6": "/home/hatch/workspace/phcc-slice6/phcc.phext",
    "slice7": "/home/hatch/workspace/phcc-slice7/phcc.phext",
    "builds": "/home/hatch/workspace/phcc-builds-aligned/phcc.phext",
}


def is_meta(c):
    return c[0] == 1 and c[3] == 1


def main():
    base = phext_io.load_phext(BASE)
    print(f"base: {len(base)} scrolls")
    detail = {"base_count": len(base), "donors": {}}
    footprints = {}  # name -> {coord_str: (kind, sha)}
    for name, path in DONORS.items():
        d = phext_io.load_phext(path)
        added = sorted(set(d) - set(base))
        missing = sorted(set(base) - set(d))
        changed = sorted(c for c in set(d) & set(base) if d[c] != base[c])
        identical = len(set(d) & set(base)) - len(changed)
        print(f"\n== {name}: {len(d)} scrolls; added {len(added)}, "
              f"changed {len(changed)}, missing {len(missing)}, "
              f"identical {identical}")
        fp = {}
        for c in added:
            fp[c] = ("added", phext_io.sha256(d[c]))
        for c in changed:
            fp[c] = ("changed", phext_io.sha256(d[c]))
        footprints[name] = fp
        detail["donors"][name] = {
            "count": len(d),
            "added": [[phext_io.fmt(c), len(d[c]), phext_io.sha256(d[c])[:12]]
                      for c in added],
            "changed": [[phext_io.fmt(c), len(base[c]), len(d[c]),
                         phext_io.sha256(base[c])[:12],
                         phext_io.sha256(d[c])[:12]] for c in changed],
            "missing": [phext_io.fmt(c) for c in missing],
            "identical": identical,
        }
        for c in missing:
            print(f"   MISSING vs base: {phext_io.fmt(c)}")
        for c in changed:
            print(f"   CHANGED vs base: {phext_io.fmt(c)} "
                  f"({len(base[c])} -> {len(d[c])} B)")

    names = list(footprints)
    print("\n== pairwise collisions (same coord touched by 2+ donors) ==")
    collisions = []
    allcoords = set()
    for n in names:
        allcoords |= set(footprints[n])
    for c in sorted(allcoords):
        holders = [n for n in names if c in footprints[n]]
        if len(holders) > 1:
            kinds = {n: footprints[n][c] for n in holders}
            same = len({v[1] for v in kinds.values()}) == 1
            collisions.append((c, kinds, same))
            print(f"   {phext_io.fmt(c)} meta={is_meta(c)}: "
                  + ", ".join(f"{n}={kinds[n][0]} sha={kinds[n][1][:12]}"
                              for n in holders)
                  + ("  [SAME BYTES]" if same else "  [CONFLICT]"))
    detail["collisions"] = [
        {"coord": phext_io.fmt(c), "meta": is_meta(c),
         "holders": {n: [k[0], k[1]] for n, k in kinds.items()},
         "same_bytes": same} for c, kinds, same in collisions]
    with open("/home/hatch/workspace/phcc-final/logs/donor-diffs.json",
              "w") as f:
        json.dump(detail, f, indent=1)
    print(f"\ncollisions total: {len(collisions)} "
          f"(conflicts: {sum(1 for _, _, s in collisions if not s)})")


if __name__ == "__main__":
    main()
