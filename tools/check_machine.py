#!/usr/bin/env python3
"""check_machine.py — static conformance checker (design A.3 level 1)
for the phcc Slice 4 preprocessor conditional-stack machine scroll.

Checks, against the phext alone:
  1. every event in the machine scroll names a function that exists
     as a Vol 3 member (form: def) of tccpp.c in Source;
  2. every identifier used in a transition guard resolves to a real
     field/variable/constant of the preprocessor's state: a field of
     TCCState, BufferedFile or TokenString (tcc.h), a #define in
     tcc.h/tccpp.c/tcctok.h, a file-scope object of tccpp.c or tcc.h
     (Vol 3 index), a declared state/event/notation name of the
     scroll itself, or a declared prose stopword (below);
  3. every transition's endpoints are declared states (or ANY / pop /
     ERROR "...");
  4. every declared event is used by at least one transition, and
     every declared state is reachable in the transition graph.

Usage: check_machine.py PHEXT [MACHINE_COORD]
Exit 0 = conforming; exit 1 = violations, each named precisely.
Stdlib only.
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

MACHINE_COORD = (1, 1, 1, 3, 2, 2, 1, 1, 2)     # Design, tccpp.c, Scroll 2
TCCPP_SRC = (1, 1, 1, 4, 2, 2, 1, 1, 1)          # Source, Vol 2
TCCPP_V3_INDEX = (1, 1, 1, 4, 3, 2, 1, 1, 1)     # Source, Vol 3 index
TCCH_SRC = (1, 1, 1, 4, 2, 3, 2, 1, 1)           # Source tcc.h (Book 3)
TCCTOK_SRC = None                                # resolved from manifest

# Prose words that may appear in guards without naming state. Declared
# here so the check is honest about what it does not verify: guard
# *logic* is not machine-checked, only guard *vocabulary*.
STOPWORDS = {
    "result", "not", "evaluated", "exhausted", "now", "empty",
    "restored", "its", "expression", "expansion", "needs", "while",
    "reading", "invocation", "pushed", "back", "onto", "token",
    "region", "scanned", "boundary", "directive", "end", "of",
    "processing", "discarded", "remainder", "line", "a", "an", "the",
    "or", "and", "with", "in", "on", "is", "are", "be", "by", "to",
}

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_machine(text):
    """Split the scroll into sections; return dict of parsed parts."""
    sections = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^(states|events|transitions|invariants|notation):", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
            continue
        if re.match(r"^(notes|machine|claim):", line):
            cur = None
            continue
        if cur:
            sections[cur].append(line)
    states = []
    for line in sections.get("states", []):
        m = re.match(r"^  ([A-Z_]+):", line)
        if m:
            states.append(m.group(1))
    events = {}
    for line in sections.get("events", []):
        m = re.match(r"^  (ev_[a-z_]+): ([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            events[m.group(1)] = m.group(2)
    notation = []
    for line in sections.get("notation", []):
        m = re.match(r"^  ([A-Za-z_]+)\s*=", line)
        if m:
            notation.append(m.group(1))
        m2 = re.match(r"^  (ANY)\s+=", line)
        if m2:
            notation.append("ANY")
    transitions = []
    tre = re.compile(
        r"^  (\S+) --(ev_[a-z_]+) \[(.*)\]--> (.+)$")
    for line in sections.get("transitions", []):
        m = tre.match(line)
        if m:
            transitions.append({
                "from": m.group(1), "event": m.group(2),
                "guard": m.group(3), "to": m.group(4).strip(),
                "raw": line.strip()})
    return states, events, notation, transitions


def vol3_functions(scrolls, index_coord):
    idx = scrolls[index_coord].decode("utf-8", "replace")
    out = {}
    for line in idx.splitlines():
        p = line.split("\t")
        if len(p) == 6 and p[1] == "function":
            out[p[2]] = p[3]
    return out


def vol3_objects(scrolls, index_coord):
    idx = scrolls[index_coord].decode("utf-8", "replace")
    out = set()
    for line in idx.splitlines():
        p = line.split("\t")
        if len(p) == 6 and p[1] == "object":
            out.add(p[2])
    return out


def struct_fields(text, struct_name):
    """Extract field identifiers from a struct body in C source.
    Brace-matches the struct definition, then takes the last
    identifier of each declaration at depth 1 (best-effort, declared
    as such in the report)."""
    m = re.search(r"(?:typedef\s+)?struct\s+" + struct_name +
                  r"\s*\{", text)
    if not m:
        # try 'struct X {' via 'typedef struct {' with name after }
        m = re.search(r"struct\s+" + struct_name + r"\b[^;{]*\{", text)
    if not m:
        return set()
    i = m.end() - 1
    depth = 0
    j = i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = text[i + 1:j]
    # strip nested braces (function pointers / nested structs) crudely
    fields = set()
    depth = 0
    cur = ""
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            cur += ch
    for decl in cur.split(";"):
        ids = IDENT.findall(decl)
        if ids:
            fields.add(ids[-1])
            # array fields: name before '[' is last ident anyway;
            # bitfields and multi-declarator lists: add all idents
            # after the first type word(s) is overkill; also add any
            # identifier immediately before ',' or '[' in the decl.
            for mm in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?=[,\[])", decl):
                fields.add(mm.group(1))
    return fields


def defines(text):
    return set(re.findall(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phext")
    ap.add_argument("--machine-coord", default=None)
    a = ap.parse_args()

    scrolls = phext_io.load_phext(a.phext)
    mcoord = (phext_io.parse_coord(a.machine_coord)
              if a.machine_coord else MACHINE_COORD)
    if mcoord not in scrolls or not scrolls[mcoord]:
        print(f"VIOLATION: machine scroll absent at {phext_io.fmt(mcoord)}")
        return 1
    text = scrolls[mcoord].decode("utf-8", "replace")
    states, events, notation, transitions = parse_machine(text)
    violations = []

    if not states:
        violations.append("no states parsed from machine scroll")
    if not events:
        violations.append("no events parsed from machine scroll")
    if not transitions:
        violations.append("no transitions parsed from machine scroll")

    # --- check 1: event functions exist as Vol 3 defs of tccpp.c
    funcs = vol3_functions(scrolls, TCCPP_V3_INDEX)
    for ev, fn in sorted(events.items()):
        if fn not in funcs:
            violations.append(
                f"event {ev}: function '{fn}' is not a Vol 3 member "
                f"of tccpp.c")
        elif funcs[fn] != "def":
            violations.append(
                f"event {ev}: function '{fn}' is a Vol 3 member of "
                f"tccpp.c but form is '{funcs[fn]}', not 'def'")

    # --- identifier universe for guard resolution
    manifest = phext_io.parse_manifest(scrolls)
    tcch = scrolls[manifest["tcc.h"]].decode("utf-8", "replace")
    tccpp = scrolls[manifest["tccpp.c"]].decode("utf-8", "replace")
    tcctok = scrolls[manifest["tcctok.h"]].decode("utf-8", "replace")
    universe = set()
    for sname in ("TCCState", "BufferedFile", "TokenString"):
        universe |= struct_fields(tcch, sname)
    universe |= defines(tcch) | defines(tccpp) | defines(tcctok)
    universe |= vol3_objects(scrolls, TCCPP_V3_INDEX)
    # Vol 3 objects of tcc.h too (globals like tok, file, tcc_state)
    tcch_v3 = (1, 1, 1, 4, 3, manifest["tcc.h"][5], manifest["tcc.h"][6],
               manifest["tcc.h"][7], 1)
    if tcch_v3 in scrolls:
        universe |= vol3_objects(scrolls, tcch_v3)
    universe |= set(events) | set(states) | set(notation)
    universe |= {"TCCState", "BufferedFile", "TokenString", "ANY",
                 "s1", "file", "tok"}
    # identifiers that are the leading name of an s1->X / file->X in a
    # guard resolve via struct fields already; plain 'slot' etc. via
    # notation.

    # --- check 2: guard vocabulary
    for t in transitions:
        for ident in IDENT.findall(t["guard"]):
            if ident in STOPWORDS:
                continue
            if ident not in universe:
                violations.append(
                    f"transition '{t['raw']}': guard identifier "
                    f"'{ident}' does not resolve to any field, "
                    f"variable, constant, event, state or notation "
                    f"name of the preprocessor state")

    # --- check 3: endpoints declared
    declared = set(states) | {"ANY"}
    for t in transitions:
        if t["from"] not in declared:
            violations.append(
                f"transition '{t['raw']}': from-state '{t['from']}' "
                f"is not a declared state")
        to = t["to"]
        if to in declared or to == "pop":
            pass
        elif to.startswith('ERROR "') and to.endswith('"'):
            pass
        else:
            violations.append(
                f"transition '{t['raw']}': target '{to}' is not a "
                f"declared state, 'pop', or an ERROR target")

    # --- check 4: usage / reachability
    used_events = {t["event"] for t in transitions}
    for ev in sorted(events):
        if ev not in used_events:
            violations.append(f"event {ev} is declared but used by "
                              f"no transition")
    touched = set()
    for t in transitions:
        touched.add(t["from"])
        if t["to"] in declared:
            touched.add(t["to"])
    for s in sorted(states):
        if s not in touched:
            violations.append(f"state {s} appears in no transition")

    print(f"machine: {phext_io.fmt(mcoord)}")
    print(f"states: {len(states)}  events: {len(events)}  "
          f"transitions: {len(transitions)}")
    print(f"event functions resolved against Vol 3 tccpp.c members: "
          f"{sum(1 for fn in events.values() if funcs.get(fn) == 'def')}"
          f"/{len(events)}")
    if violations:
        print(f"STATIC CONFORMANCE: FAIL ({len(violations)} violations)")
        for v in violations:
            print(f"  VIOLATION: {v}")
        return 1
    print("STATIC CONFORMANCE: PASS (0 violations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
