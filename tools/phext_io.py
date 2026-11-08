#!/usr/bin/env python3
"""phext_io.py — byte-exact phext read/write helpers for phcc Slice 1.

Copied verbatim in behaviour from Slice 0's tools/import_phcc.py
(walk_bytes / implode / fmt) so the Slice 1 phext stays byte-format
consistent with the Slice 0 phext. Stdlib only.

Coordinate tuple order: (library, shelf, series, collection, volume,
book, chapter, section, scroll).
"""
import hashlib, re

LEVEL_BYTES = [0x01, 0x1F, 0x1E, 0x1D, 0x1C, 0x1A, 0x19, 0x18, 0x17]  # library..scroll
DELIM_SET = set(LEVEL_BYTES)
DELIM_TO_LEVEL = {b: i for i, b in enumerate(LEVEL_BYTES)}


def fmt(coord):
    return f"{coord[0]}.{coord[1]}.{coord[2]}/{coord[3]}.{coord[4]}.{coord[5]}/{coord[6]}.{coord[7]}.{coord[8]}"


def parse_coord(s):
    a, b, c = s.split("/")
    parts = []
    for grp in (a, b, c):
        parts += [int(x) for x in grp.split(".")]
    return tuple(parts)


def walk_bytes(data):
    """Dead-reckoning byte walk — same state machine as parse_phext.py,
    but yields (coord_tuple, bytes) so scrolls stay byte-exact."""
    coord = [1] * 9
    buf = bytearray()
    out = []
    for b in data:
        lvl = DELIM_TO_LEVEL.get(b)
        if lvl is None:
            buf.append(b)
        else:
            out.append((tuple(coord), bytes(buf)))
            buf = bytearray()
            coord[lvl] += 1
            for j in range(lvl + 1, 9):
                coord[j] = 1
    out.append((tuple(coord), bytes(buf)))
    if out and out[-1][1] == b"":
        out.pop()
    return out


def implode(scrolls):
    """scrolls: dict coord_tuple -> bytes. Same emitter as Slice 0."""
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


def load_phext(path):
    with open(path, "rb") as f:
        return dict(walk_bytes(f.read()))


# ------------------------------------------------------------ dedup refs
# EXTENSION (phcc_analyze, 2026-11-07): the de-duplication reference
# stub written by `phcc analyze --apply` and expanded by `phcc
# unpack`. A stub is a complete payload (a Volume 3 segment's bytes
# after its #phcc-member header line) or a complete scroll (a
# Volume 2 file scroll) consisting of exactly one line:
#
#     #phcc-dedup-ref <coordinate> <sha256>\n
#
# naming the canonical scroll that holds the bytes and the SHA-256
# of the bytes the stub stands for (for a segment target, the SHA-256
# of the target segment's payload, i.e. its post-header bytes — the
# same value the file index records). The format is deliberately a
# single anchored line: a payload is a stub iff it matches in full,
# so detection is exact, never heuristic. See tools/METHODS.md,
# "analyze — duplication census + automatic de-duplication".
DEDUP_REF_RE = re.compile(
    rb"\A#phcc-dedup-ref "
    rb"(\d+\.\d+\.\d+/\d+\.\d+\.\d+/\d+\.\d+\.\d+) "
    rb"([0-9a-f]{64})\n\Z")


def dedup_ref(coord, payload_sha256):
    """The stub bytes standing for the payload at `coord`."""
    return (b"#phcc-dedup-ref " + fmt(coord).encode("ascii") + b" "
            + payload_sha256.encode("ascii") + b"\n")


def parse_dedup_ref(data):
    """(coord_tuple, sha256_hex) if `data` is exactly a dedup stub,
    else None."""
    if data is None:
        return None
    m = DEDUP_REF_RE.match(data)
    if not m:
        return None
    return parse_coord(m.group(1).decode("ascii")), m.group(2).decode("ascii")


def parse_manifest(scrolls):
    """Return {path: coord_tuple} from the Slice 0 placement manifest
    scroll (Meta, Volume 2, Book 10, Ch 1, Sec 1)."""
    coord = (1, 1, 1, 1, 2, 10, 1, 1, 1)
    text = scrolls[coord].decode("utf-8")
    out = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[0]] = parse_coord(parts[1])
    return out
