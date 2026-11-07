#!/usr/bin/env python3
"""phext_io.py — byte-exact phext read/write helpers for phcc Slice 1.

Copied verbatim in behaviour from Slice 0's tools/import_phcc.py
(walk_bytes / implode / fmt) so the Slice 1 phext stays byte-format
consistent with the Slice 0 phext. Stdlib only.

Coordinate tuple order: (library, shelf, series, collection, volume,
book, chapter, section, scroll).
"""
import hashlib

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
