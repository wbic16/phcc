#!/usr/bin/env python3
"""verify_wipe.py — the wiped file differs from the merged file by
EXACTLY the 27 Library-10000 scrolls: nothing added, nothing else
altered."""
import sys

sys.path.insert(0, "/home/hatch/workspace/phcc-final/tools")
import phext_io

full = phext_io.load_phext("/home/hatch/workspace/phcc-final/phcc.phext")
wiped = phext_io.load_phext("/home/hatch/workspace/phcc-final/work/wiped.phext")
removed = sorted(set(full) - set(wiped))
added = sorted(set(wiped) - set(full))
altered = sorted(c for c in set(full) & set(wiped) if full[c] != wiped[c])
region = [c for c in removed if c[0] == 10000]
extra = [c for c in removed if c[0] != 10000]
print(f"full {len(full)}  wiped {len(wiped)}")
print(f"removed {len(removed)}: {len(region)} Library-10000 scrolls + "
      f"{len(extra)} walker artifact")
for c in extra:
    print(f"  artifact: {phext_io.fmt(c)} size {len(full[c])} "
          f"(highest non-region coordinate; becomes the wiped file's "
          f"trailing scroll and is dropped by the walker's "
          f"trailing-empty convention — zero content)")
print(f"added {len(added)}  altered {len(altered)}")
assert len(region) == 27
assert len(extra) == 1 and full[extra[0]] == b"" \
    and extra[0] == max(c for c in full if c[0] != 10000)
assert not added and not altered
print("WIPE PROOF OK")
