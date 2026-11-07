#!/usr/bin/env python3
"""make_stale_mutants.py — two copies of the merged phext, each with
exactly one byte flipped in one Source scroll:
  mutant-m3.phext: tccelf.c Source (machine #3's bound source)
  mutant-asm.phext: lib/libtcc1.c Source (the assembly listings'
  bound source)"""
import sys

sys.path.insert(0, "/home/hatch/workspace/phcc-final/tools")
import phext_io

W = "/home/hatch/workspace/phcc-final/work"
src = phext_io.load_phext("/home/hatch/workspace/phcc-final/phcc.phext")


def flip(scrolls, coord):
    data = bytearray(scrolls[coord])
    i = 100
    data[i] = ord("Z") if data[i] != ord("Z") else ord("Y")
    scrolls[coord] = bytes(data)


m = dict(src)
flip(m, (1, 1, 1, 4, 2, 5, 1, 2, 1))  # tccelf.c
with open(f"{W}/mutant-m3.phext", "wb") as f:
    f.write(phext_io.implode(m))

m = dict(src)
flip(m, (1, 1, 1, 4, 2, 7, 1, 2, 1))  # lib/libtcc1.c
with open(f"{W}/mutant-asm.phext", "wb") as f:
    f.write(phext_io.implode(m))
print("mutants written")
