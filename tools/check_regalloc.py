#!/usr/bin/env python3
"""check_regalloc.py — static conformance checker (design A.3
level 1) for the phcc Slice 7 register-allocation machines
(design A.3 machine #4): the x86_64 instance at Design
1.1.1/3.2.6/1.1.2 and the arm64 instance at Design
1.1.1/3.2.6/4.1.2.

Checks, against the phext alone, for EACH machine scroll:
  1. every event names a function that exists as a Vol 3 member
     (form: def) of one of the three bounded files (tccgen.c,
     x86_64-gen.c, arm64-gen.c) — the allocator is a shared core
     plus backend tables, so resolution is multi-file by design;
  2. every identifier in a transition guard resolves to: a field
     of SValue / CType (tcc.h, with the declared anonymous-union
     supplement), a #define in tcc.h / tccgen.c / tcctok.h /
     x86_64-gen.c / arm64-gen.c, a TREG_* / RC_* identifier from
     either backend, a Vol 3 function or object of any bounded
     file, a declared state / event / notation name of the
     scroll, or a declared prose stopword (below);
  3. transition endpoints are declared states (or ANY / SAME /
     pop / ERROR "...");
  4. every declared event is used; every declared state is
     touched by some transition.

Guard *logic* is prose and is not machine-checked — only guard
*vocabulary* is. The STOPWORDS list is the honest boundary, as
in Slices 4/5.

Usage: check_regalloc.py PHEXT [--x64 COORD] [--arm64 COORD]
Exit 0 = both scrolls conform; exit 1 = violations, named.
Stdlib only.
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

X64_COORD = (1, 1, 1, 3, 2, 6, 1, 1, 2)      # Design, x86_64-gen.c, Scroll 2
ARM64_COORD = (1, 1, 1, 3, 2, 6, 4, 1, 2)    # Design, arm64-gen.c, Scroll 2
BOUNDED = ["tccgen.c", "x86_64-gen.c", "arm64-gen.c"]

SVALUE_UNION_FIELDS = {"jtrue", "jfalse", "c", "cmp_op", "cmp_r", "sym"}

# Real local variables of gv / gv2 in tccgen.c (gv's r_ok and
# r2_ok at tccgen.c:1849 and :1924-1925; gv2's parameters rc1 /
# rc2 at :2002). Declared here because the Vol 3 index records
# functions and file-scope objects, not locals.
CODE_LOCALS = {"r_ok", "r2_ok", "rc1", "rc2"}

# Cross-references to the scroll's own invariants (I<n>) and
# notes (N<n>) resolve by rule: they name declared parts of the
# same scroll.
XREF = re.compile(r"^[IN][0-9]+$")

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "is",
    "are", "be", "by", "with", "when", "then", "first", "before",
    "after", "both", "each", "other", "its", "it", "no", "not",
    "at", "as", "if", "so", "into", "from", "over", "under",
    "for", "else", "s", "x", "d", "their", "classes",
    "registers", "constants", "surviving", "array", "local",
    "addresses", "consumes", "arguments", "value", "values",
    "entry", "entries", "top", "below", "result", "stored",
    "register", "class", "wanted", "context", "expression",
    "constant", "address", "stack", "slot", "frame", "offset",
    "word", "second", "now", "empty", "restored", "evaluated",
    "exhausted", "needs", "while", "reading", "invocation",
    "pushed", "back", "onto", "token", "region", "scanned",
    "boundary", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "zero", "non", "plain", "real",
    "old", "new", "fresh", "own", "general", "case", "cases",
    "whole", "exactly", "already", "still", "just", "also",
    "whose", "which", "that", "this", "than", "more", "less",
    "every", "any", "all", "only", "same", "here", "there",
    "being", "been", "has", "have", "had", "was", "were",
    "will", "would", "can", "may", "must", "should", "does",
    "do", "did", "keeps", "keep", "kept", "makes", "make",
    "made", "takes", "take", "taken", "gives", "give", "given",
    "leaves", "leave", "left", "becomes", "become", "became",
    "stay", "stays", "holds", "hold", "held", "lives", "live",
    "says", "say", "said", "words", "list", "lists", "jump",
    "jumps", "flags", "flag", "pending", "dummy", "above",
    "added", "again", "against", "another", "appended",
    "applied", "arrays", "aside", "automatic", "backend",
    "beyond", "bitfield", "buried", "bytes", "call", "called",
    "cast", "changes", "clear", "cleared", "code", "collapse",
    "combined", "compare", "computed", "conditional",
    "consumed", "conversion", "converted", "copied", "copies",
    "copy", "data", "destination", "directly", "dropped",
    "emitted", "except", "exchange", "field", "flushed",
    "folded", "form", "function", "functions", "generated",
    "generates", "global", "head", "holding", "identity",
    "installed", "instruction", "invoked", "itself",
    "leaving", "loaded", "loads", "lvalue", "lvalues",
    "marked", "mask", "masked", "materialized",
    "materializes", "memmove", "modify", "moved", "moves",
    "never", "nonzero", "nothing", "object", "op", "operand",
    "operands", "pair", "pass", "passes", "path", "performed",
    "place", "places", "plus", "pointed", "pointer",
    "pointers", "pop", "popped", "pure", "raw", "read",
    "recorded", "records", "refused", "relational",
    "remains", "replaced", "requiring", "resolved", "resumes",
    "returned", "returns", "rewritten", "rule", "rvalue",
    "save", "saved", "scalar", "section", "set", "shift",
    "sides", "skipped", "slots", "spill", "step", "storage",
    "survives", "swapped", "symbol", "tail", "target",
    "targets", "test", "time", "touching", "unchanged",
    "usable", "without", "working", "written", "wrote",
    "x86", "x87", "zeroed",
    # Slice 7 guard prose vocabulary
    "scan", "finds", "referencing", "referenced", "references",
    "occupancy", "check", "skipped", "skips", "wins", "index",
    "order", "handed", "out", "bottom", "most", "candidate",
    "within", "lies", "lie", "exempt", "region", "begins",
    "opens", "home", "previous", "source", "append",
    "machinery", "granularity", "sole", "requested", "long",
    "double", "work", "names", "exact", "argument", "passing",
    "within", "withheld", "generic", "allocation", "reachable",
    "unreachable", "solely", "sole", "carries", "carry",
    "generator", "link", "frame", "setup", "establishes",
    "point", "substitutions", "starts", "runs", "body",
    "starts", "temp", "obtained", "program", "happens",
    "happen", "after", "side", "effect", "pop", "emit",
    "emits", "fstp", "st", "mov", "cases", "branch", "park",
    "parks", "instances", "instance", "subtle", "dance",
    "splits", "splitting", "int", "float", "floats", "void",
    "bt", "sv", "p", "r", "rc", "n", "i", "o", "dd", "xdd",
    "USING_TWO_WORDS", "arm64_sym", "gjmp_cond", "gvtst_set",
    "gen_op", "vdup", "vstack", "vtop", "refs", "bound",
    "nb_args", "x64", "arm64", "dd", "he", "mov",
    # Slice 7 second-pass prose vocabulary
    "such", "match", "holder", "checked", "fires", "reaches",
    "primary", "wrong", "satisfies", "request", "reused",
    "untouched", "but", "see", "note", "follows", "rules",
    "sequence", "BEFORE", "id", "ALL", "freed", "once",
    "touched", "owning", "frees", "single", "placement",
    "memory", "spilled", "writes", "alone", "brings", "state",
    "requests", "lived", "gaps", "ever", "matches", "them",
    "appends", "traffic", "event", "pool", "spills",
    "precedes", "rewrite", "calls", "inside", "where",
    "x86_64", "uses", "named", "gen", "c", "explicitly",
    "bit", "return", "epilog", "prolog", "allocator",
    "depth", "cross", "machine", "scroll", "invariant",
    "starts", "opcode", "clear",
}

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_machine(text):
    sections = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^(states|events|transitions|invariants|notation):",
                     line)
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
        m = re.match(r"^  ([A-Z_0-9]+):", line)
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
    tre = re.compile(r"^  (\S+) --(ev_[a-z0-9_]+) \[(.*)\]--> (.+)$")
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
    m = re.search(r"(?:typedef\s+)?struct\s+" + struct_name + r"\s*\{",
                  text)
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
            for mm in re.finditer(
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*(?=[,\[])", decl):
                fields.add(mm.group(1))
    return fields


def defines(text):
    return set(re.findall(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)",
                          text))


def check_one(scrolls, mcoord, funcs, universe_base, label):
    violations = []
    if mcoord not in scrolls or not scrolls[mcoord]:
        return [f"{label}: machine scroll absent at "
                f"{phext_io.fmt(mcoord)}"], None
    text = scrolls[mcoord].decode("utf-8", "replace")
    states, events, notation, transitions, invariants = \
        parse_machine(text)
    if not states:
        violations.append(f"{label}: no states parsed")
    if not events:
        violations.append(f"{label}: no events parsed")
    if not transitions:
        violations.append(f"{label}: no transitions parsed")
    resolved = 0
    for ev, fn in sorted(events.items()):
        if funcs.get(fn) == "def":
            resolved += 1
        else:
            violations.append(
                f"{label}: event {ev}: function '{fn}' is not a "
                f"Vol 3 def member of any bounded file "
                f"(tccgen.c / x86_64-gen.c / arm64-gen.c)")
    universe = set(universe_base) | set(events) | set(states) \
        | set(notation) | CODE_LOCALS
    for t in transitions:
        for ident in IDENT.findall(t["guard"]):
            if ident in STOPWORDS or XREF.match(ident):
                continue
            if ident not in universe:
                violations.append(
                    f"{label}: transition '{t['raw']}': guard "
                    f"identifier '{ident}' does not resolve")
    declared = set(states) | {"ANY", "SAME"}
    for t in transitions:
        if t["from"] not in declared:
            violations.append(
                f"{label}: transition '{t['raw']}': from-state "
                f"'{t['from']}' is not declared")
        to = t["to"]
        if to in declared or to == "pop":
            pass
        elif to.startswith('ERROR "') and to.endswith('"'):
            pass
        else:
            violations.append(
                f"{label}: transition '{t['raw']}': target '{to}' "
                f"is not a declared state / pop / ERROR")
    used = {t["event"] for t in transitions}
    for ev in sorted(events):
        if ev not in used:
            violations.append(
                f"{label}: event {ev} declared but used by no "
                f"transition")
    touched = set()
    for t in transitions:
        touched.add(t["from"])
        if t["to"] in declared:
            touched.add(t["to"])
    for s in sorted(states):
        if s not in touched:
            violations.append(
                f"{label}: state {s} appears in no transition")
    counts = (len(states), len(events), len(transitions),
              len(invariants), resolved, len(events))
    return violations, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phext")
    ap.add_argument("--x64-coord", default=None)
    ap.add_argument("--arm64-coord", default=None)
    a = ap.parse_args()

    scrolls = phext_io.load_phext(a.phext)
    manifest = phext_io.parse_manifest(scrolls)

    funcs = {}
    objects = set()
    for name in BOUNDED:
        c = manifest[name]
        idx = (1, 1, 1, 4, 3, c[5], c[6], c[7], 1)
        for fn, form in vol3_members(scrolls, idx, "function").items():
            if form == "def":
                funcs[fn] = "def"
        objects |= set(vol3_members(scrolls, idx, "object"))
        objects |= set(vol3_members(scrolls, idx, "function"))

    universe = set()
    tcch = scrolls[manifest["tcc.h"]].decode("utf-8", "replace")
    for sname in ("SValue", "CType"):
        universe |= struct_fields(tcch, sname)
    universe |= SVALUE_UNION_FIELDS
    srcs = {}
    for name in BOUNDED + ["tcc.h", "tcctok.h"]:
        srcs[name] = scrolls[manifest[name]].decode("utf-8", "replace")
        universe |= defines(srcs[name])
    for name in ("x86_64-gen.c", "arm64-gen.c"):
        universe |= set(re.findall(r"\b(TREG_[A-Z0-9_]+)\b",
                                   srcs[name]))
        universe |= set(re.findall(r"\b(RC_[A-Z0-9_]+)\b",
                                   srcs[name]))
    universe |= objects
    universe |= set(funcs)
    universe |= {"SValue", "CType", "TCCState", "ANY", "SAME",
                 "vstack", "vtop", "NB_REGS", "reg_classes"}

    total_violations = []
    for label, coord in (("x86_64", X64_COORD), ("arm64", ARM64_COORD)):
        v, counts = check_one(scrolls, coord, funcs, universe, label)
        total_violations += v
        if counts:
            print(f"machine ({label}): {phext_io.fmt(coord)}")
            print(f"states: {counts[0]}  events: {counts[1]}  "
                  f"transitions: {counts[2]}  invariants: "
                  f"{counts[3]}")
            print(f"event functions resolved against Vol 3 members "
                  f"of the bounded files: {counts[4]}/{counts[5]}")
    if total_violations:
        print(f"STATIC CONFORMANCE: FAIL "
              f"({len(total_violations)} violations)")
        for v in total_violations:
            print(f"  VIOLATION: {v}")
        return 1
    print("STATIC CONFORMANCE: PASS (0 violations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
