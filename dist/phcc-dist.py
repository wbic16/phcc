#!/usr/bin/env python3
"""phcc-dist - distributed compile driver for phcc.

Splits a multi-TU build into hash-pinned work units and distributes
them across phccd workers. The model rhymes with wpm: nodes are
untrusted carriers, a unit's identity is its SHA-256, and every
returned object is verified against the hash the worker reports and
(in --verify-local mode) against a local compile of the same unit.

There is deliberately NO local fallback: a unit that cannot be
distributed and verified fails the build, by name. A failed
distribution names its block; it never silently becomes a local
compile.

Unit identity:
    unit_id = SHA256("phcc-dist-v1" || compiler_id || flags || 0x00 || src)
    compiler_id = SHA256 of the phccd executable (reported in HELLO;
                  the driver refuses nodes whose compiler differs).

Usage:
    phcc-dist.py --phcc ./tcc --phcc-root . --worker-bin ./phccd \
        --nodes 100.69.163.95:4711,100.69.30.79:4711 \
        --outdir /tmp/objs [--verify-local] [-I dir] [-D X] \
        [--flags "-fPIC"] file1.c file2.c ...
"""

import argparse
import hashlib
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

DOMAIN = b"phcc-dist-v1"


def sha256(b):
    return hashlib.sha256(b).digest()


def recv_all(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise IOError("connection closed")
        buf += chunk
    return buf


def recv_frame(sock, magic):
    hdr = recv_all(sock, 12)
    if hdr[:4] != magic:
        raise IOError(f"bad frame magic: {hdr[:4]!r}")
    (plen,) = struct.unpack(">Q", hdr[4:12])
    return recv_all(sock, plen)


class NodeError(Exception):
    pass


def run_unit(node, unit_id, flags, src, timeout=120):
    """Send one unit to one node; return (obj_bytes, obj_hash, cache_hit)."""
    host, port = node.rsplit(":", 1)
    with socket.create_connection((host, int(port)), timeout=timeout) as s:
        hello = recv_frame(s, b"PHCH")
        node_compiler = hello[:32]
        if node_compiler != run_unit.expected_compiler:
            raise NodeError(
                f"{node}: compiler_id mismatch "
                f"({node_compiler.hex()[:16]}... != expected "
                f"{run_unit.expected_compiler.hex()[:16]}...)")
        payload = unit_id + struct.pack(">H", len(flags)) + flags \
            + struct.pack(">Q", len(src)) + src
        s.sendall(b"PHCU" + struct.pack(">Q", len(payload)) + payload)
        resp = recv_frame(s, b"PHCO")
    status, cache_hit = resp[0], resp[1]
    obj_hash = resp[2:34]
    (obj_len,) = struct.unpack(">Q", resp[34:42])
    if status != 0:
        (mlen,) = struct.unpack(">H", resp[42:44])
        msg = resp[44:44 + mlen].decode("utf-8", "replace")
        raise NodeError(f"{node}: status {status}: {msg.strip()}")
    obj = resp[42:42 + obj_len]
    if len(obj) != obj_len:
        raise NodeError(f"{node}: truncated object")
    if sha256(obj) != obj_hash:
        raise NodeError(f"{node}: object hash does not match reported hash")
    return obj, obj_hash, bool(cache_hit)


def preprocess(phcc, root, src_path, includes, defines, tmpdir):
    out = os.path.join(tmpdir, os.path.basename(src_path) + ".i")
    cmd = [phcc, "-B" + root, "-E", src_path, "-o", out]
    for i in includes:
        cmd += ["-I", i]
    for d in defines:
        cmd += ["-D", d]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise NodeError(f"preprocess failed for {src_path}: {r.stderr.strip()}")
    with open(out, "rb") as f:
        return f.read()


def local_compile(phcc, root, src_bytes, flags, tmpdir, unit_id):
    # The unit is compiled under its canonical name, <unit_id>.i —
    # the same name the worker uses — because the object records its
    # source name. Byte-identity is only well-defined when both sides
    # compile the unit under its identity.
    name = unit_id.hex()
    ipath = os.path.join(tmpdir, name + ".i")
    opath = os.path.join(tmpdir, name + ".o")
    with open(ipath, "wb") as f:
        f.write(src_bytes)
    cmd = [os.path.abspath(phcc), "-B" + os.path.abspath(root),
           "-c", name + ".i", "-o", name + ".o"]
    if flags:
        cmd += flags.decode().split()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir)
    if r.returncode != 0:
        raise NodeError(f"local compile failed for {name}: {r.stderr.strip()}")
    with open(opath, "rb") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phcc", required=True, help="path to hub phcc (tcc) binary")
    ap.add_argument("--phcc-root", default=".", help="dir passed via -B")
    ap.add_argument("--worker-bin", required=True,
                    help="path to the phccd binary deployed on the nodes; "
                         "its SHA-256 is the expected compiler_id")
    ap.add_argument("--nodes", required=True,
                    help="comma-separated host:port list")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--flags", default="",
                    help="codegen flags carried in the unit (e.g. -fPIC)")
    ap.add_argument("--verify-local", action="store_true",
                    help="locally compile every unit from the same "
                         "preprocessed bytes and compare hashes "
                         "(a check only; outputs remain node-produced)")
    ap.add_argument("-I", dest="includes", action="append", default=[])
    ap.add_argument("-D", dest="defines", action="append", default=[])
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()

    with open(args.worker_bin, "rb") as f:
        compiler_id = sha256(f.read())
    run_unit.expected_compiler = compiler_id
    flags = args.flags.encode()
    nodes = args.nodes.split(",")
    os.makedirs(args.outdir, exist_ok=True)

    print(f"compiler_id (phccd build): {compiler_id.hex()}")
    print(f"nodes: {', '.join(nodes)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build the units.
        units = []  # (outname, unit_id, src_bytes)
        for src_path in args.sources:
            src = preprocess(args.phcc, args.phcc_root, src_path,
                             args.includes, args.defines, tmpdir)
            unit_id = sha256(DOMAIN + compiler_id + flags + b"\x00" + src)
            outname = os.path.splitext(os.path.basename(src_path))[0] + ".o"
            units.append((outname, unit_id, src, src_path))
        print(f"units: {len(units)}")

        # Dispatch: one in-flight unit per node, pulled from a shared queue.
        results = {}
        failures = []
        lock = threading.Lock()
        queue = list(units)

        def worker(node):
            while True:
                with lock:
                    if not queue:
                        return
                    outname, unit_id, src, src_path = queue.pop(0)
                t0 = time.time()
                try:
                    obj, obj_hash, hit = run_unit(node, unit_id, flags, src)
                    ms = (time.time() - t0) * 1000
                    with open(os.path.join(args.outdir, outname), "wb") as f:
                        f.write(obj)
                    with lock:
                        results[outname] = (unit_id, obj_hash, node, ms, hit)
                except Exception as e:  # named below; never substituted
                    with lock:
                        failures.append((outname, unit_id, str(e)))

        threads = [threading.Thread(target=worker, args=(n,)) for n in nodes]
        t_start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.time() - t_start

        per_node = {}
        for outname in sorted(results):
            unit_id, obj_hash, node, ms, hit = results[outname]
            per_node[node] = per_node.get(node, 0) + 1
            print(f"  {outname:20s} unit {unit_id.hex()[:12]}  "
                  f"obj {obj_hash.hex()[:16]}  {node}  {ms:7.1f} ms"
                  f"{'  (cache)' if hit else ''}")
        print(f"distributed wall-clock: {wall:.2f} s "
              f"({len(results)}/{len(units)} units, per-node {per_node})")

        if failures:
            print("\nFAILED UNITS (no local fallback taken):", file=sys.stderr)
            for outname, unit_id, err in failures:
                print(f"  {outname} unit {unit_id.hex()[:12]}: {err}",
                      file=sys.stderr)
            return 1

        if args.verify_local:
            print("\nlocal verification (same preprocessed bytes):")
            bad = 0
            for outname, unit_id, src, src_path in units:
                obj = local_compile(args.phcc, args.phcc_root, src, flags,
                                    tmpdir, unit_id)
                lh = sha256(obj)
                rh = results[outname][1]
                ok = lh == rh
                bad += 0 if ok else 1
                print(f"  {outname:20s} local {lh.hex()[:16]}  "
                      f"remote {rh.hex()[:16]}  {'MATCH' if ok else 'MISMATCH'}")
            if bad:
                print(f"{bad} unit(s) differ from local compile",
                      file=sys.stderr)
                return 2
            print(f"all {len(units)} distributed objects byte-identical "
                  f"to local compiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
