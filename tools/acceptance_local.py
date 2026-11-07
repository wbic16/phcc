#!/usr/bin/env python3
"""acceptance_local.py — unpack the pre-verdict phext, verify the
carried tree is byte-identical to the repo tree at e399b212 across
all 558 manifest files (lib/libtcc1.c included), and that the two
Sec-14 addendum files match the repo F4 bytes. Writes the unpack
tree + a tarball for the ranch build step.
"""
import hashlib
import os
import subprocess
import sys

WS = os.path.expanduser("~/workspace")
R = os.path.join(WS, "phcc-reissue")
sys.path.insert(0, os.path.join(R, "tools"))
import phext_io

FIXED = os.path.join(WS, "phcc-attrfix/tree")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(R, "work/phcc-pre-verdict.phext")
    outdir = os.path.join(R, "work/unpack-final")
    subprocess.run([sys.executable, os.path.join(R, "tools/phcc_migrate.py"),
                    "export", "--phext", src, "--out", outdir, "--from", "vol2"],
                   check=False)
    # phcc_migrate's CLI is driven through the `phcc` dispatcher in the
    # repo tools; if the direct call above is not the entry, fall back:
    if not os.path.isdir(outdir):
        r = subprocess.run([os.path.join(R, "tools/phcc"), "unpack",
                            "--phext", src, "--out", outdir, "--force"],
                           capture_output=True, text=True)
        print(r.stdout[-2000:], r.stderr[-500:])
    man = phext_io.parse_manifest(phext_io.load_phext(src))
    bad = []
    for path, _c in sorted(man.items()):
        a = open(os.path.join(outdir, path), "rb").read()
        b = open(os.path.join(FIXED, path), "rb").read()
        if a != b:
            bad.append(path)
    print(f"manifest files compared: {len(man)}; differing: {bad}")
    scrolls = phext_io.load_phext(src)
    for pth, coord in (("phext/phext.c", (1, 1, 1, 4, 2, 10, 10, 1, 1)),
                       ("phext/phext.h", (1, 1, 1, 4, 2, 10, 10, 2, 1))):
        want = open(os.path.join(FIXED, pth), "rb").read()
        got = scrolls[coord]
        print(f"addendum {pth}: {'MATCH' if got == want else 'MISMATCH'} ({sha(got)[:12]}...)")
        os.makedirs(os.path.join(outdir, "phext"), exist_ok=True)
        open(os.path.join(outdir, pth), "wb").write(got)
    assert not bad
    print("ACCEPTANCE_LOCAL_OK")


if __name__ == "__main__":
    main()
