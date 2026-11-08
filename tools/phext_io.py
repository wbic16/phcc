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


# ------------------------------------------------------- statement refs
# EXTENSION (statement tier, 2026-11-07): the statement-level
# expression. A Volume 3 segment payload may be rewritten as a
# statement reference sequence — the member's body expressed as an
# ordered list of references to statement scrolls, each of which
# holds one distinct statement core exactly once (Library 20000,
# content-derived coordinates; see METHODS.md, "analyze —
# statement tier"). The payload grammar is exact, like the dedup
# stub's: a payload is a statement sequence iff it matches in full.
#
#     #phcc-stmt-seq 1\n
#     #phcc-stmt-ref <coordinate> <sha256-of-core> <indent-hex>\n
#     #phcc-stmt-ref EMPTY <indent-hex>\n
#     ...
#
# Each reference names the statement scroll holding the segment's
# core bytes (the segment minus its leading whitespace), the
# SHA-256 of those core bytes, and the segment's leading whitespace
# itself, hex-encoded (whitespace is the one part of a segment that
# is positional, not content). EMPTY stands for the empty core (a
# whitespace-only segment — e.g. a gap tail); it names no scroll.
# Expansion is indent + core, concatenated in order, and must
# reproduce the original segment payload byte-for-byte — unpack
# verifies that against the file index's recorded payload SHA-256,
# exactly as it does for a literal payload.
STMT_SEQ_MAGIC = b"#phcc-stmt-seq 1\n"
STMT_COORD_PAT = rb"\d+\.\d+\.\d+/\d+\.\d+\.\d+/\d+\.\d+\.\d+"
STMT_REF_RE = re.compile(
    rb"#phcc-stmt-ref (" + STMT_COORD_PAT + rb") ([0-9a-f]{64}) "
    rb"([0-9a-f]*)")
STMT_REF_EMPTY_RE = re.compile(rb"#phcc-stmt-ref EMPTY ([0-9a-f]*)")


def stmt_ref(coord, core_sha256, indent):
    """One reference line (bytes, newline-terminated)."""
    return (b"#phcc-stmt-ref " + fmt(coord).encode("ascii") + b" "
            + core_sha256.encode("ascii") + b" "
            + indent.hex().encode("ascii") + b"\n")


def stmt_ref_empty(indent):
    """The reference line for a whitespace-only segment."""
    return b"#phcc-stmt-ref EMPTY " + indent.hex().encode("ascii") \
        + b"\n"


def parse_stmt_seq(data):
    """Parse a statement reference sequence payload. Returns a list
    of (coord_tuple | None, sha256_hex | None, indent_bytes) — the
    EMPTY form yields (None, None, indent) — or None when `data` is
    not exactly a statement sequence. A payload that opens with the
    magic but then breaks the grammar is corruption, not a plain
    payload: callers that expand must treat a magic-prefixed
    non-parse as an error (see phcc_migrate.resolve_stmt_seq)."""
    if data is None or not data.startswith(STMT_SEQ_MAGIC):
        return None
    rest = data[len(STMT_SEQ_MAGIC):]
    if rest == b"":
        return []
    if not rest.endswith(b"\n"):
        return None
    refs = []
    for line in rest[:-1].split(b"\n"):
        m = STMT_REF_RE.fullmatch(line)
        if m:
            try:
                indent = bytes.fromhex(m.group(3).decode("ascii"))
            except ValueError:
                return None
            refs.append((parse_coord(m.group(1).decode("ascii")),
                         m.group(2).decode("ascii"), indent))
            continue
        m = STMT_REF_EMPTY_RE.fullmatch(line)
        if m:
            try:
                indent = bytes.fromhex(m.group(1).decode("ascii"))
            except ValueError:
                return None
            refs.append((None, None, indent))
            continue
        return None
    return refs


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
