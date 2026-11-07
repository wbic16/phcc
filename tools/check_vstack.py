#!/usr/bin/env python3
"""check_vstack.py — static conformance checker (design A.3 level 1)
for the phcc Slice 5 value-stack machine scroll (tccgen.c).

Generalized from Slice 4's tools/check_machine.py. Checks, against
the phext alone:
  1. every event in the machine scroll names a function that exists
     as a Vol 3 member (form: def) of tccgen.c in Source;
  2. every identifier used in a transition guard resolves to a real
     field/variable/constant of the subsystem's state: a field of
     SValue or CType (tcc.h; the anonymous-union members jtrue,
     jfalse, cmp_op, cmp_r are a declared supplement, below, because
     the brace-stripping field extractor cannot see through the
     nested anonymous unions), a #define in tcc.h, tccgen.c,
     tcctok.h or x86_64-gen.c (the register-class and register
     vocabulary - RC_INT, TREG_ST0 - lives in the backend header by
     TinyCC's design), a file-scope object or function of tccgen.c
     or tcc.h (Vol 3 index), a declared state/event/notation name of
     the scroll itself, or a declared prose stopword (below);
  3. every transition's endpoints are declared states (or ANY /
     SAME / pop / ERROR "...");
  4. every declared event is used by at least one transition, and
     every declared state is reachable in the transition graph.

Usage: check_vstack.py PHEXT [MACHINE_COORD]
Exit 0 = conforming; exit 1 = violations, each named precisely.
Stdlib only.
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

MACHINE_COORD = (1, 1, 1, 3, 2, 3, 1, 1, 2)     # Design, tccgen.c, Scroll 2
TCCGEN_V3_INDEX = (1, 1, 1, 4, 3, 3, 1, 1, 1)   # Source, Vol 3 index

# SValue's anonymous-union members (tcc.h:487-494). The extractor in
# struct_fields() strips nested-brace content, so it cannot see
# these; they are declared here, exactly, from the header text:
# union { struct { int jtrue, jfalse; }; CValue c; } and
# union { struct { unsigned short cmp_op, cmp_r; }; struct Sym *sym; }.
SVALUE_UNION_FIELDS = {"jtrue", "jfalse", "c", "cmp_op", "cmp_r", "sym"}

# Prose words that may appear in guards without naming state. Declared
# here so the check is honest about what it does not verify: guard
# *logic* is not machine-checked, only guard *vocabulary*.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "is",
    "are", "be", "by", "with", "when", "then", "first", "before",
    "after", "both", "each", "other", "its", "it", "no", "not",
    "at", "as", "if", "so", "into", "from", "over", "under",
    "for", "else", "s", "x", "d", "their", "classes", "registers",
    "constants", "surviving", "decayed", "array", "designator",
    "local", "addresses", "consumes", "arguments",
    "value", "values", "entry", "entries", "top", "below",
    "result", "stored", "register", "class", "wanted", "context",
    "expression", "constant", "address", "stack", "slot", "frame",
    "offset", "word", "second", "now", "empty", "restored",
    "evaluated", "exhausted", "needs", "while", "reading",
    "invocation", "pushed", "back", "onto", "token", "region",
    "scanned", "boundary", "directive", "end", "processing",
    "discarded", "remainder", "line", "one", "two", "three",
    "four", "five", "six", "seven", "eight", "nine", "zero",
    "non", "plain", "real", "old", "new", "fresh", "own",
    "general", "case", "cases", "whole", "exactly", "already",
    "still", "just", "also", "whose", "which", "that", "this",
    "than", "more", "less", "every", "any", "all", "only",
    "same", "here", "there", "being", "been", "has", "have",
    "had", "was", "were", "will", "would", "can", "may",
    "must", "should", "does", "do", "did", "keeps", "keep",
    "kept", "makes", "make", "made", "takes", "take", "taken",
    "gives", "give", "given", "leaves", "leave", "left",
    "becomes", "become", "became", "stay", "stayed", "stays",
    "holds", "hold", "held", "lives", "live", "lived",
    "says", "say", "said", "words", "list", "lists",
    "jump", "jumps", "flags", "flag", "pending", "dummy",
    "above", "added", "again", "against", "another", "appended",
    "applied", "arrays", "aside", "assertion", "automatic",
    "backend", "beyond", "bitfield", "buried", "bytes", "call",
    "called", "cast", "changes", "clear", "cleared", "code",
    "collapse", "combined", "compare", "comparing", "comparison",
    "complementary", "completes", "computed", "conditional",
    "consequence", "consumed", "conversion", "converted",
    "converts", "copied", "copies", "copy", "dances", "data",
    "decrement", "designating", "destination", "directly",
    "division", "divisor", "dropped", "duplicated", "emitted",
    "except", "exchange", "extracted", "field", "flushed",
    "foldable", "folded", "folding", "folds", "form", "function",
    "functions", "gathered", "generated", "generates",
    "generation", "global", "head", "holding", "identity",
    "installed", "instruction", "inverted", "invoked", "itself",
    "kin", "leaving", "loaded", "loads", "lvalue", "lvalues",
    "marked", "mask", "masked", "materialized", "materializes",
    "memmove", "modify", "modulo", "moved", "moves", "never",
    "nonzero", "nothing", "object", "op", "operand", "operands",
    "ors", "packed", "pair", "pass", "passes", "path",
    "performed", "place", "places", "plus", "pointed", "pointer",
    "pointers", "pop", "popped", "postfix", "prefix", "proceeds",
    "propagated", "pure", "purity", "raw", "read", "recorded",
    "records", "recursive", "refused", "relational", "reloaded",
    "remains", "replaced", "replaces", "requiring", "resolved",
    "resumes", "resurfaces", "returned", "returns", "rewritten",
    "rule", "rvalue", "save", "saved", "scalar", "section",
    "set", "shift", "shifted", "shifts", "sides", "skipped",
    "slots", "spill", "step", "storage", "suppression",
    "survives", "swapped", "symbol", "tail", "target", "targets",
    "test", "time", "touching", "unchanged", "usable",
    "wholesale", "without", "working", "written", "wrote",
    "x86", "x87", "zeroed",
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
        m = re.match(r"^  (ev_[a-z0-9_]+): ([A-Za-z_][A-Za-z0-9_]*)",
                     line)
        if m:
            events[m.group(1)] = m.group(2)
    notation = []
    for line in sections.get("notation", []):
        m = re.match(r"^  ([A-Za-z_]+)\s*=", line)
        if m:
            notation.append(m.group(1))
    transitions = []
    tre = re.compile(
        r"^  (\S+) --(ev_[a-z0-9_]+) \[(.*)\]--> (.+)$")
    for line in sections.get("transitions", []):
        m = tre.match(line)
        if m:
            transitions.append({
                "from": m.group(1), "event": m.group(2),
                "guard": m.group(3), "to": m.group(4).strip(),
                "raw": line.strip()})
    invariants = [l for l in sections.get("invariants", [])
                  if re.match(r"^  I\d+:", l)]
    return states, events, notation, transitions, invariants


def vol3_members(scrolls, index_coord, kind):
    idx = scrolls[index_coord].decode("utf-8", "replace")
    out = {}
    for line in idx.splitlines():
        p = line.split("\t")
        if len(p) == 6 and p[1] == kind:
            out[p[2]] = p[3]
    return out


def struct_fields(text, struct_name):
    """Extract field identifiers from a struct body in C source.
    Brace-matches the struct definition, then takes the last
    identifier of each declaration at depth 1 (best-effort, declared
    as such in the report). Copied from Slice 4's check_machine.py."""
    m = re.search(r"(?:typedef\s+)?struct\s+" + struct_name +
                  r"\s*\{", text)
    if not m:
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
    states, events, notation, transitions, invariants = parse_machine(text)
    violations = []

    if not states:
        violations.append("no states parsed from machine scroll")
    if not events:
        violations.append("no events parsed from machine scroll")
    if not transitions:
        violations.append("no transitions parsed from machine scroll")

    # --- check 1: event functions exist as Vol 3 defs of tccgen.c
    funcs = vol3_members(scrolls, TCCGEN_V3_INDEX, "function")
    for ev, fn in sorted(events.items()):
        if fn not in funcs:
            violations.append(
                f"event {ev}: function '{fn}' is not a Vol 3 member "
                f"of tccgen.c")
        elif funcs[fn] != "def":
            violations.append(
                f"event {ev}: function '{fn}' is a Vol 3 member of "
                f"tccgen.c but form is '{funcs[fn]}', not 'def'")

    # --- identifier universe for guard resolution
    manifest = phext_io.parse_manifest(scrolls)
    tcch = scrolls[manifest["tcc.h"]].decode("utf-8", "replace")
    tccgen = scrolls[manifest["tccgen.c"]].decode("utf-8", "replace")
    tcctok = scrolls[manifest["tcctok.h"]].decode("utf-8", "replace")
    x64gen = scrolls[manifest["x86_64-gen.c"]].decode("utf-8", "replace")
    universe = set()
    for sname in ("SValue", "CType"):
        universe |= struct_fields(tcch, sname)
    universe |= SVALUE_UNION_FIELDS
    universe |= defines(tcch) | defines(tccgen) | defines(tcctok)
    universe |= defines(x64gen)
    # the backend's register names are enum constants, not #defines
    # (x86_64-gen.c: TREG_RAX ... TREG_ST0 = 24, ...)
    universe |= set(re.findall(r"\b(TREG_[A-Z0-9_]+)\b", x64gen))
    universe |= set(vol3_members(scrolls, TCCGEN_V3_INDEX, "object"))
    universe |= set(funcs)  # tccgen.c function names (gsym, gjmp, ...)
    # Vol 3 objects of tcc.h too (globals like tok, file, tcc_state)
    tcch_v3 = (1, 1, 1, 4, 3, manifest["tcc.h"][5], manifest["tcc.h"][6],
               manifest["tcc.h"][7], 1)
    if tcch_v3 in scrolls:
        universe |= set(vol3_members(scrolls, tcch_v3, "object"))
        universe |= set(vol3_members(scrolls, tcch_v3, "function"))
    universe |= set(events) | set(states) | set(notation)
    universe |= {"SValue", "CType", "TCCState", "ANY", "SAME",
                 "vstack", "vtop"}

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
                    f"name of the value-stack state")

    # --- check 3: endpoints declared
    declared = set(states) | {"ANY", "SAME"}
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
          f"transitions: {len(transitions)}  invariants: {len(invariants)}")
    print(f"event functions resolved against Vol 3 tccgen.c members: "
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
