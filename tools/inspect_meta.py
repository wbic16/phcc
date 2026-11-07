#!/usr/bin/env python3
"""inspect_meta.py — dump the contested Meta scrolls and find every
textual cross-reference to Meta Secs 14-17 in all four files."""
import sys

sys.path.insert(0, "/home/hatch/workspace/phcc-slice7/tools")
import phext_io

FILES = {
    "base": "/home/hatch/workspace/phcc-merged/phcc.phext",
    "slice6": "/home/hatch/workspace/phcc-slice6/phcc.phext",
    "slice7": "/home/hatch/workspace/phcc-slice7/phcc.phext",
    "builds": "/home/hatch/workspace/phcc-builds-aligned/phcc.phext",
}


def meta(sec):
    return (1, 1, 1, 1, 2, 10, 1, sec, 1)


scrolls = {n: phext_io.load_phext(p) for n, p in FILES.items()}

print("### builds Sec14 ADDENDUM (keeps coordinate)")
print(scrolls["builds"][meta(14)].decode("utf-8"))
print("### slice6 Sec15 MACHINE-3 REGISTER — first 30 lines")
print("\n".join(
    scrolls["slice6"][meta(15)].decode("utf-8").splitlines()[:30]))
print("\n### builds Sec15 BUILD REGISTER — first 30 lines")
print("\n".join(
    scrolls["builds"][meta(15)].decode("utf-8").splitlines()[:30]))
print("\n### slice7 Sec16 MACHINE-4 REGISTER — first 20 lines")
print("\n".join(
    scrolls["slice7"][meta(16)].decode("utf-8").splitlines()[:20]))

print("\n### cross-references to Meta Sec 14/15/16/17 coordinates")
needles = ["1.2.10/1.14.1", "1.2.10/1.15.1", "1.2.10/1.16.1",
           "1.2.10/1.17.1", "Sec 14", "Sec 15", "Sec 16", "Sec 17"]
for name, sc in scrolls.items():
    for coord, data in sc.items():
        if coord[3] == 1 and coord[5] == 10:
            continue  # skip Meta scrolls themselves for now
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for nd in needles:
            if nd in text:
                print(f"  {name} {phext_io.fmt(coord)}: mentions {nd!r}")
                break

print("\n### self-references INSIDE the contested Meta scrolls")
for name, sec in [("slice6", 15), ("builds", 15), ("slice7", 16),
                  ("builds", 14)]:
    text = scrolls[name][meta(sec)].decode("utf-8")
    for nd in needles:
        if nd in text:
            print(f"  {name} Sec{sec}: mentions {nd!r}")

print("\n### region manifest (Library 10000 root) — builds")
mani = scrolls["builds"].get((10000, 1, 1, 1, 1, 1, 1, 1, 1), b"")
text = mani.decode("utf-8")
print("\n".join(text.splitlines()[:15]))
for nd in needles + ["register"]:
    if nd in text:
        print(f"  manifest mentions {nd!r}")
