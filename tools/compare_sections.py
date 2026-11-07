#!/usr/bin/env python3
"""compare_sections.py — split each gate stdout into named sections
and diff gate v8's sections against the donor gates' own runs on
their own files. Expected differences (union counts, the machine-#3
register coordinate) are reported, not hidden."""
import difflib

L = "/home/hatch/workspace/phcc-final/logs"
FILES = {
    "v8": f"{L}/gate-v8-on-preverdict.txt",
    "slice6": f"{L}/gate-slice6-on-slice6.txt",
    "slice7": f"{L}/gate-slice7-on-slice7.txt",
    "builds": f"{L}/gate-builds-on-builds.txt",
}
MARKERS = [
    ("coverage", "per-Book phase coverage"),
    ("tiers", "tier distribution:"),
    ("design", "design views (Slice 3"),
    ("machine1", "machine conformance (Slice 4"),
    ("machine2", "machine conformance #2"),
    ("machine3", "machine conformance #3"),
    ("machine4", "machine conformance #4"),
    ("assembly", "generated assembly (builds pass"),
]


def sections(path):
    lines = open(path).read().splitlines()
    lines = [l for l in lines if not l.startswith("gate input:")]
    out = {}
    cur, buf = "head", []
    for l in lines:
        hit = next((n for n, m in MARKERS if l.startswith(m)), None)
        if hit:
            out[cur] = buf
            cur, buf = hit, [l]
        else:
            buf.append(l)
    out[cur] = buf
    # strip trailing gate trailer lines from the last section
    for k in out:
        out[k] = [l for l in out[k]
                  if not l.startswith(("verdict scroll:",
                                        "verdict sha256:",
                                        "verdict-out:"))]
        while out[k] and out[k][-1] == "":
            out[k].pop()
    return out


S = {k: sections(p) for k, p in FILES.items()}


def cmp(sec, donor):
    a, b = S[donor].get(sec), S["v8"].get(sec)
    if a is None:
        print(f"{sec} vs {donor}: donor run has no such section")
        return
    if a == b:
        print(f"{sec} vs {donor}: IDENTICAL ({len(a)} lines)")
    else:
        d = list(difflib.unified_diff(a, b, donor, "v8", lineterm="",
                                      n=0))
        body = [x for x in d if x.startswith(("+", "-"))
                and not x.startswith(("+++", "---"))]
        print(f"{sec} vs {donor}: {len(body)} differing line(s)")
        for x in body:
            print(f"    {x[:180]}")


for sec in ("tiers", "design", "machine1", "machine2"):
    for donor in ("slice6", "slice7", "builds"):
        cmp(sec, donor)
for sec, donor in (("machine3", "slice6"), ("machine4", "slice7"),
                   ("assembly", "builds"), ("coverage", "slice6"),
                   ("coverage", "slice7"), ("coverage", "builds")):
    cmp(sec, donor)
