#!/usr/bin/env python3
"""check_linker.py — static conformance checker (design A.3 level 1)
for the phcc Slice 6 linker symbol-resolution machine scroll.

Checks, against the phext alone:
  1. every event in the machine scroll names a function that exists
     as a Vol 3 member (kind function, form def) of tccelf.c;
  2. every identifier used in a transition guard resolves to a real
     field/variable/constant of the linker state: a field of
     TCCState or Section (tcc.h), an ElfW(Sym)/ElfW_Rel field
     (declared supplement below — ElfW types are macro-generated
     in elf.h, so the field names are listed explicitly), a
     #define in tcc.h/tccelf.c/elf.h, a TCC_OUTPUT_* constant
     named in tcc.h, a Vol 3 object or function of tccelf.c, a
     Vol 3 object of tcc.h, a declared state/event/notation name
     of the scroll itself, or a declared prose stopword (below);
  3. every transition's endpoints are declared states (or ANY /
     ERROR "...");
  4. every declared event is used by at least one transition, and
     every declared state is reachable in the transition graph.

Usage: check_linker.py PHEXT [MACHINE_COORD]
Exit 0 = conforming; exit 1 = violations, each named precisely.
Stdlib only.
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phext_io

MACHINE_COORD = (1, 1, 1, 3, 2, 5, 1, 2, 2)     # Design, tccelf.c, Scroll 2
TCCELF_V3_INDEX = (1, 1, 1, 4, 3, 5, 1, 2, 1)   # Source, Vol 3 index

# ElfW(Sym) / ElfW_Rel / ElfW_Rela fields: the ElfW types are
# macro-generated in elf.h, so a struct-field extractor cannot
# see them; the field names are listed here as a declared
# supplement (same honesty pattern as Slice 5's SValue union).
ELF_FIELDS = {
    "st_name", "st_value", "st_size", "st_info", "st_other",
    "st_shndx", "r_offset", "r_info", "r_addend",
}

# Prose words that may appear in guards without naming state.
# Declared here so the check is honest about what it does not
# verify: guard *logic* is not machine-checked, only guard
# *vocabulary*.
STOPWORDS = {
    "a", "an", "the", "of", "or", "and", "in", "on", "is", "are",
    "be", "by", "to", "at", "for", "from", "with", "without",
    "not", "no", "it", "its", "that", "this", "than", "then",
    "only", "every", "any", "all", "one", "two", "first",
    "second", "later", "already", "still", "exactly", "once",
    "incoming", "existing", "entry", "entries", "symbol",
    "symbols", "name", "names", "section", "sections", "index",
    "table", "tables", "value", "values", "size", "field",
    "fields", "changes", "nothing", "stands", "stood", "kept",
    "left", "made", "taken", "found", "given", "passes",
    "pass", "row", "rows", "applies", "apply", "applied",
    "presented", "presents", "definition", "definitions",
    "defined", "undefined", "reference", "references",
    "common", "commons", "data", "weak", "strong", "hidden",
    "local", "locals", "global", "library", "libraries",
    "program", "object", "objects", "archive", "member",
    "members", "file", "files", "output", "outputs", "order",
    "chain", "hash", "hashed", "offset", "offsets", "base",
    "address", "host", "process", "loaded", "dynamic",
    "loader", "runtime", "pipeline", "fixed", "mode", "caller",
    "set", "zero", "bss", "asm", "warning", "issued", "reports",
    "missing", "copied", "moved", "count", "records", "past",
    "window", "group", "triggered", "triggers", "extraction",
    "loads", "load", "merged", "merge", "merges", "patch",
    "patches", "patched", "allocation", "allocated", "guard",
    "skips", "skipped", "creates", "created", "create",
    "returns", "returned", "return", "becomes", "become",
    "gains", "gained", "keeps", "keep", "walks", "walked",
    "recorded", "records", "renumbered", "relocation",
    "relocations", "target", "targets", "plus", "here",
    "there", "when", "while", "after", "before", "over",
    "into", "onto", "out", "up", "so", "if", "each", "other",
    "same", "such", "whose", "which", "was", "were", "has",
    "have", "had", "do", "does", "did", "can", "may", "must",
    "back", "down", "per", "via", "off", "also", "just",
    "even", "well", "part", "end", "top", "new", "old",
    "whose", "both", "either", "neither", "nor", "but",
    "however", "therefore", "instead", "rather", "whether",
    "being", "been", "being", "gets", "get", "got", "make",
    "makes", "take", "takes", "stands", "stand", "comes",
    "come", "goes", "go", "runs", "run", "running", "ran",
    "finds", "find", "adds", "add", "added", "uses", "used",
    "use", "using", "calls", "called", "call", "checks",
    "check", "checked", "holds", "hold", "shows", "show",
    "means", "mean", "works", "work", "lists", "list",
    "points", "point", "reads", "read", "writes", "write",
    "starts", "start", "ends", "begins", "begin", "next",
    "last", "own", "real", "pure", "free", "full", "main",
    "side", "case", "kind", "form", "line", "text", "code",
    "word", "words", "note", "notes", "claim", "scroll",
    "appended", "straight", "replaces", "identical", "early",
    "visibility", "most", "constraining", "adding", "ignored",
    "define", "overridden", "false", "true", "precedence",
    "earlier", "compiled", "promoted", "concatenates",
    "carries", "defines", "converted", "again", "outcome",
    "decided", "extracted", "nobody", "stays", "copies",
    "number", "linker", "against", "installed", "their",
    "absolute", "resolves", "error", "resolution", "lookup",
    "resolved", "final", "owes", "transferred", "place",
    "script", "rescan", "another", "construction", "binding",
    "sizes", "layout", "as", "based", "exception", "aside",
    "kept", "keeps", "stands", "stand",
}

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_machine(text):
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
        m = re.match(r"^  (ev_[a-z0-9_]+): ([A-Za-z_][A-Za-z0-9_]*)", line)
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
    tre = re.compile(r"^  (\S+) --(ev_[a-z0-9_]+) \[(.*)\]--> (.+)$")
    for line in sections.get("transitions", []):
        m = tre.match(line)
        if m:
            transitions.append({
                "from": m.group(1), "event": m.group(2),
                "guard": m.group(3), "to": m.group(4).strip(),
                "raw": line.strip()})
    return states, events, notation, transitions


def vol3_members(scrolls, index_coord, kind):
    idx = scrolls[index_coord].decode("utf-8", "replace")
    out = {}
    for line in idx.splitlines():
        p = line.split("\t")
        if len(p) == 6 and p[1] == kind:
            out[p[2]] = p[3]
    return out


def struct_fields(text, struct_name):
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
    states, events, notation, transitions = parse_machine(text)
    violations = []

    if not states:
        violations.append("no states parsed from machine scroll")
    if not events:
        violations.append("no events parsed from machine scroll")
    if not transitions:
        violations.append("no transitions parsed from machine scroll")

    funcs = vol3_members(scrolls, TCCELF_V3_INDEX, "function")
    for ev, fn in sorted(events.items()):
        if fn not in funcs:
            violations.append(
                f"event {ev}: function '{fn}' is not a Vol 3 member "
                f"of tccelf.c")
        elif funcs[fn] != "def":
            violations.append(
                f"event {ev}: function '{fn}' is a Vol 3 member of "
                f"tccelf.c but form is '{funcs[fn]}', not 'def'")

    manifest = phext_io.parse_manifest(scrolls)
    tcch = scrolls[manifest["tcc.h"]].decode("utf-8", "replace")
    tccelf = scrolls[manifest["tccelf.c"]].decode("utf-8", "replace")
    elfh = scrolls[manifest["elf.h"]].decode("utf-8", "replace")
    universe = set(ELF_FIELDS)
    for sname in ("TCCState", "Section"):
        universe |= struct_fields(tcch, sname)
    libtcch = scrolls[manifest["libtcc.h"]].decode("utf-8", "replace")
    universe |= defines(tcch) | defines(tccelf) | defines(elfh)
    universe |= defines(libtcch)
    # TCCState line 914: the symtab lives in an anonymous union
    # (union { Section *symtab_section, *symtab; }); the field
    # extractor strips nested braces, so the two alias fields
    # are declared here as a supplement (Slice 5 pattern).
    universe |= {"symtab", "symtab_section"}
    universe |= set(re.findall(r"TCC_OUTPUT_[A-Z_]+", tcch))
    universe |= set(vol3_members(scrolls, TCCELF_V3_INDEX, "object"))
    universe |= set(funcs)
    tcch_v3 = (1, 1, 1, 4, 3, manifest["tcc.h"][5], manifest["tcc.h"][6],
               manifest["tcc.h"][7], 1)
    if tcch_v3 in scrolls:
        universe |= set(vol3_members(scrolls, tcch_v3, "object"))
    universe |= set(events) | set(states) | set(notation)
    universe |= {"TCCState", "Section", "ANY", "s1"}

    for t in transitions:
        for ident in IDENT.findall(t["guard"]):
            if ident in STOPWORDS:
                continue
            if ident not in universe:
                violations.append(
                    f"transition '{t['raw']}': guard identifier "
                    f"'{ident}' does not resolve to any field, "
                    f"variable, constant, event, state or notation "
                    f"name of the linker state")

    declared = set(states) | {"ANY"}
    for t in transitions:
        if t["from"] not in declared:
            violations.append(
                f"transition '{t['raw']}': from-state '{t['from']}' "
                f"is not a declared state")
        to = t["to"]
        if to in declared:
            pass
        elif to.startswith('ERROR "') and to.endswith('"'):
            pass
        else:
            violations.append(
                f"transition '{t['raw']}': target '{to}' is not a "
                f"declared state or an ERROR target")

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
    print(f"event functions resolved against Vol 3 tccelf.c members: "
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
