#!/usr/bin/env python3
"""phcc_prune.py — phcc -O2, rung A: member-graph pruning.

    phcc prune --phext X.phext --out Y.phext --harvest H.json
               [--report R.json] [--root SYM ...] [--keep-prefix P ...]

Rung A of the -O2 ladder (Will's ruling, 2026-11-08): for a project
carried in a phext, the phext member graph (Collection 4, Volume 3)
plus the compiler's own symbol knowledge price the optimisation
before it is built — reachability over the member graph from the
link's entry/export roots, validated against the linker's
undefined-symbol closure. What reachability proves dead is dropped;
the output is a pruned phext (and, by unpack, a pruned tree) for ONE
named build configuration. The compiler sources are not touched;
this is a tools-side transform of the carried form.

Inputs
  --phext    the carried phext (canonical layout: placement manifest
             at Meta 1.1.1/1.2.10/1.1.1, Source at Collection 4
             Volumes 2+3, optional Sec-14 addendum manifest).
  --harvest  harvest.py output for a tree built from this phext:
             per-object defined/undefined symbols (nm), archive
             membership, object->source mapping. This is the ground
             truth for what the build compiled and what the link
             needed; the graph is never trusted over it.
  --root     extra root symbols (repeatable).
  --keep-prefix  extra keep-whole path prefixes (repeatable).

Graph model
  Nodes are Volume 3 members (kind function/object/type; gap
  segments are not nodes and are never dropped). A member's names
  come from its index row (comma-split). Edges follow identifier
  tokens in member payloads — raw text, so comments, string
  literals (dlsym names, __attribute__((alias("...")))), inline
  asm operands and macro bodies all contribute edges in the safe
  direction. A referenced token no member is named by falls back
  to a provider index over payloads: identifiers a member defines
  without being named by them — enum enumerators are the corpus's
  witnesses (ERROR_WARN, the TCC_OPTION_* table, both enums inside
  libtcc.c) — are provided by the type members whose payloads
  carry the token (carrier-capped; C keywords and preprocessor
  directive words excluded — the first word of a #-line is a
  directive, not a reference). A token with neither a bearer nor
  a provider falls to a suffix index over member names: paste
  families reference a definition by its suffix alone
  (ELFW(R_INFO) pastes to ELF64_R_INFO). Members in files the configuration does
  not compile are not nodes: an edge into them is an edge into a
  build that does not happen.

Roots (the link's own surface)
  - definers of main;
  - every member of a token-table file (*-tok.h, tcctok.h):
    enumerator factories whose rows are positional and whose
    identifiers are manufactured by token pasting, so no payload
    scan can see their references — rooted as units;
  - every member carrying an #if-family or #endif line: the two
    halves of a conditional region may live in different members,
    and dropping one half unbalances the file for every
    configuration — rooted as units;
  - definers of every symbol the links in this configuration
    actually demand: the undefined-symbol closure is replayed over
    the harvest (seed = every non-archive object's undefineds;
    archive members are pulled when they define a demanded symbol
    and inherit their own undefineds to a fixpoint), and the final
    demanded set is rooted. A pulled archive object's globals that
    nothing demanded are not rooted — they survive only on payload
    edges. Consumers outside the configuration (a future program
    pulling a runtime helper today's tests never call) are outside
    the prune's claim, and the prune manifest says so;
  - members whose payload carries __attribute__((constructor)),
    ((destructor)) or ((used)) — the dynamic loader, not the
    linker, is their caller;
  - members named in ambient text: the bytes of every keep-whole
    file and every gap segment of a graph file (data surfaces the
    graph cannot see: runtime sources, shipped headers, test
    inputs);
  - members whose name survives only as a substring of another
    payload (token-pasted names, e.g. tcctok.h DEF tables) — the
    paste net, applied to names with no token edge;
  - --root symbols.

Validation (the bug loop, mechanised)
  After BFS, every undefined symbol of every compiled object must
  have a kept definer; a miss force-keeps the definer, records the
  forcing (symbol, requiring file, member) in the report, and BFS
  resumes. A prune that cannot close is reported, not hidden.

File classes (v1 configuration: default host build + test suite.
The keep-whole prefix set, the keep-whole file set, and the
runtime prefix are per-project parameters — --keep-prefixes,
--keep-files, --runtime-prefix — whose defaults are phcc's; a
project whose recipe never builds its tests and whose lib/ is a
compiled library (coreutils/gnulib) passes empty sets instead.)
  - graph files: compiled sources, library-constituent sources,
    and the #include closure over them (quoted includes, plus
    angle includes the configured build graph vouches for —
    gnulib's <libc-config.h> shape) — member-prunable;
  - keep-whole: tests/**, examples/**, include/**, tools/**,
    lib/** files the build did not compile (the compiler's
    runtime-source surface), tcclib.h (consumed by the compiler
    as data), the Sec-14 addendum files, and every non-source
    file (build machinery, docs) — pruning is a statement about
    compilable source, not about the tree's data. Keep-whole
    wins over graph membership: a compiled test program is a
    test input, and pruning it would prune the receipt itself
    (its undefined symbols still feed the demand closure);
  - drop-whole: source files (.c/.h/.S/.s) in no class above —
    except build-referenced files, rescued in two tiers:
    reachable as a prerequisite from the default goal in the
    configured build's dependency graph (the harvest's make
    database; generation templates live here), or named by
    basename in a kept build-instruction file (conftest.c).

Emission
  The pruned phext carries Volume 1 verbatim, Source Volumes 2+3
  with pruned files rewritten (index spans re-tiled, segment
  headers re-spanned, manifest rows re-hashed), the placement
  manifest rewritten for the pruned file set, the layout notes
  verbatim, and a prune manifest at Meta 1.1.1/1.2.10/2.1.1
  recording the base hash, the configuration, the root policy,
  every dropped file and every dropped member (auditable), and
  the closure-forced keeps. Derived phases of the base phext
  (Design, Tests, Regressions, Docs, Proofs, gate verdicts, the
  Library-10000 build region) are NOT carried: their hash
  bindings name the unpruned source set, and carrying them would
  assert provenance that no longer holds — the same doctrine as
  pack (METHODS.md). They are regenerated by their own passes.

Failure behaviour: any inconsistency (segment hash mismatch,
span tiling break, unclosable validation) aborts with exit 1 and
nothing written to --out.
"""
import argparse, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phext_io import walk_bytes, implode, fmt, sha256, parse_coord
import phcc_migrate

MANIFEST_COORD = phcc_migrate.MANIFEST_COORD
NOTES_COORD = phcc_migrate.NOTES_COORD
ADDENDUM_COORD = (1, 1, 1, 1, 2, 10, 1, 14, 1)
PRUNE_MANIFEST_COORD = (1, 1, 1, 1, 2, 10, 2, 1, 1)
SOURCE_EXTS = (".c", ".h", ".S", ".s")
IDENT_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*")
PATTERN_ROOTS = (b"__attribute__((constructor", b"__attribute__((destructor",
                 b"__attribute__((used", b"__attribute__ ((constructor",
                 b"__attribute__ ((destructor", b"__attribute__ ((used")


# ------------------------------------------------------------ phext model
class Member:
    __slots__ = ("path", "scr", "kind", "names", "form", "span", "psha",
                 "payload", "seg_coord")

    def __init__(self, path, scr, kind, names, form, span, psha, payload,
                 seg_coord):
        self.path, self.scr, self.kind = path, scr, kind
        self.names, self.form, self.span = names, form, span
        self.psha, self.payload, self.seg_coord = psha, payload, seg_coord

    @property
    def mid(self):
        return (self.path, self.scr)


class CarriedFile:
    __slots__ = ("path", "coord", "sha", "size", "mode", "structured",
                 "members", "index_head", "data")

    def __init__(self, entry):
        self.path, self.coord = entry["path"], entry["coord"]
        self.sha, self.size, self.mode = entry["sha"], entry["size"], \
            entry["mode"]
        self.structured = False
        self.members = []       # Member rows in index order (gaps incl.)
        self.index_head = []    # original index header lines (str)
        self.data = None        # Vol 2 bytes


def load_carried(phext_path):
    """Return (scrolls, [CarriedFile]) — main manifest + Sec-14 addendum."""
    scrolls = dict(walk_bytes(open(phext_path, "rb").read()))
    entries = phcc_migrate.manifest_entries(scrolls)
    add = scrolls.get(ADDENDUM_COORD, b"").decode("utf-8", "replace")
    for line in add.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 5:
            path, coord_s, sha, size, mode = parts
            entries.append({"path": path, "coord": parse_coord(coord_s),
                            "sha": sha, "size": int(size), "mode": mode})
    files = []
    for e in entries:
        cf = CarriedFile(e)
        cf.data = scrolls.get(cf.coord)
        if cf.data is None or sha256(cf.data) != cf.sha:
            raise SystemExit(f"FATAL: Vol 2 scroll for {cf.path} missing or "
                             f"hash-mismatched vs manifest")
        v2 = cf.coord
        idx_coord = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        raw_idx = scrolls.get(idx_coord, b"")
        structured = raw_idx.startswith(b"# phcc file index") and \
            f"# path: {cf.path}\n".encode() in raw_idx and \
            f"# sha256: {cf.sha} ".encode() in raw_idx
        if structured:
            cf.structured = True
            for line in raw_idx.decode("utf-8").splitlines():
                if line.startswith("#"):
                    cf.index_head.append(line)
                    continue
                if not line:
                    continue
                scr_s, kind, name, form, span, psha = line.split("\t")
                scr = int(scr_s)
                seg_coord = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], scr)
                seg = scrolls.get(seg_coord)
                if seg is None or b"\n" not in seg:
                    raise SystemExit(f"FATAL: segment {fmt(seg_coord)} for "
                                     f"{cf.path} missing/headerless")
                payload = seg.split(b"\n", 1)[1]
                if sha256(payload) != psha:
                    raise SystemExit(f"FATAL: segment {fmt(seg_coord)} "
                                     f"payload hash mismatch")
                s, en = (int(x) for x in span.split("-"))
                names = [] if name == "-" else \
                    [n.strip() for n in name.split(",") if n.strip()]
                cf.members.append(Member(cf.path, scr, kind, names, form,
                                         (s, en), psha, payload, seg_coord))
            tiled = b"".join(m.payload for m in cf.members)
            if tiled != cf.data:
                raise SystemExit(f"FATAL: {cf.path} segments do not tile "
                                 f"the Vol 2 bytes")
        files.append(cf)
    return scrolls, files


# ------------------------------------------------------------ harvest
class Harvest:
    def __init__(self, path):
        d = json.load(open(path))
        self.objects = d["objects"]            # objpath -> info
        self.archives = d["archives"]          # libpath -> {member: info}
        # configured build's prerequisite set (make -qp harvest);
        # older harvests lack it — build-references then rest on
        # the in-phext scan alone
        self.build_prereqs = set(d.get("build_prereqs", []))
        self.by_source = {}                    # source -> [obj infos]
        for info in self.objects.values():
            if info["source"]:
                self.by_source.setdefault(info["source"], []).append(info)
        # archive member objects: resolve to sources by basename
        self.archive_sources = set()
        base2src = {}
        for src in self.by_source:
            base2src.setdefault(os.path.basename(src), src)
        for lib, members in self.archives.items():
            for mname in members:
                stem = mname.rsplit(".", 1)[0]
                cand = [s for s in self.by_source
                        if os.path.basename(s).rsplit(".", 1)[0] == stem]
                if len(cand) == 1:
                    self.archive_sources.add(cand[0])
        self.compiled_sources = set(self.by_source)
        # symbol -> defining sources (global / local), per nm
        self.def_global, self.def_local = {}, {}
        for src, infos in self.by_source.items():
            for info in infos:
                for s in info["defined_global"]:
                    self.def_global.setdefault(s, set()).add(src)
                for s in info["defined_local"]:
                    self.def_local.setdefault(s, set()).add(src)
        # archive members may exist only inside the archive (no loose .o):
        # fold their symbol tables in under their resolved source too.
        for lib, members in self.archives.items():
            for mname, info in members.items():
                stem = mname.rsplit(".", 1)[0]
                cand = [s for s in self.compiled_sources
                        if os.path.basename(s).rsplit(".", 1)[0] == stem]
                if len(cand) != 1:
                    continue
                src = cand[0]
                for s in info["defined_global"]:
                    self.def_global.setdefault(s, set()).add(src)
                for s in info["defined_local"]:
                    self.def_local.setdefault(s, set()).add(src)
        self.undefined_by_source = {}
        for src, infos in self.by_source.items():
            u = set()
            for info in infos:
                u.update(info["undefined"])
            self.undefined_by_source[src] = u


INCLUDE_RE = re.compile(rb'#\s*include\s*"([^"]+)"')
ANGLE_INCLUDE_RE = re.compile(rb"#\s*include\s*<([^>]+)>")


def include_closure(files_by_path, seeds, build_prereqs=frozenset()):
    """#include closure over carried files, starting at seeds.
    Quoted includes resolve: including file's directory, tree root,
    include/ — then any carried directory holding the basename.
    Angle includes are system includes: they are followed only
    when the configured build itself vouches for the target — the
    name resolves to exactly one carried file AND that file is in
    the harvest's build-prerequisite set (automake depfiles put
    real header dependencies there). The vouching matters: a
    payload textually contains #include <windows.h> behind a
    Windows-only #ifdef (libtcc.c), and following text alone
    dragged the whole win32 header tree into a Linux prune.
    Gnulib's <libc-config.h> is the true positive: unique in the
    tree and a depfile prerequisite of the objects that use it
    (subject-2 receipts build, bug 7). With no build graph in the
    harvest, angle includes are not followed."""
    by_base = {}
    for p in files_by_path:
        by_base.setdefault(os.path.basename(p), []).append(p)

    def resolve(p, name):
        cands = [os.path.normpath(os.path.join(os.path.dirname(p), name)),
                 name, os.path.join("include", name)]
        hit = next((c for c in cands if c in files_by_path), None)
        if hit is None:
            base = by_base.get(os.path.basename(name), [])
            if len(base) == 1:
                hit = base[0]
        return hit

    seen, stack = set(), list(seeds)
    while stack:
        p = stack.pop()
        if p in seen or p not in files_by_path:
            continue
        seen.add(p)
        data = files_by_path[p].data or b""
        for inc in INCLUDE_RE.findall(data):
            hit = resolve(p, inc.decode("utf-8", "replace"))
            if hit is not None:
                stack.append(hit)
        for inc in ANGLE_INCLUDE_RE.findall(data):
            name = inc.decode("utf-8", "replace")
            base = by_base.get(os.path.basename(name), [])
            if len(base) == 1 and base[0] in build_prereqs:
                stack.append(base[0])
    return seen


# ------------------------------------------------------------ graph
KEEP_WHOLE_PREFIXES = ("tests/", "examples/", "include/", "tools/",
                       "phext/")
LIB_PREFIX = "lib/"


KEEP_WHOLE_FILES = ("tcclib.h",)   # consumed by the compiler as data


def is_build_ref_file(path):
    """Files whose text the build itself reads as instructions —
    a source file named here is build-referenced, not dead."""
    base = path.rsplit("/", 1)[-1]
    return (base.startswith(("Makefile", "makefile", "configure"))
            or base.endswith((".mk", ".am", ".in", ".sh", ".bat")))


def classify_files(files, graph_files, extra_keep,
                   keep_prefixes=KEEP_WHOLE_PREFIXES,
                   runtime_prefix=LIB_PREFIX,
                   keep_files=KEEP_WHOLE_FILES,
                   build_prereqs=frozenset()):
    """path -> 'graph' | 'keep' | 'drop' for manifest files.

    Keep-whole classes win over graph membership: a test program the
    build happens to compile (tests/tcctest.c) is an input to the
    test suite, and pruning it would prune the receipt itself. The
    harvest still hears those objects — their undefined symbols feed
    the demand closure exactly as before; only their own members are
    exempt from dropping. The class parameters are per-project:
    phcc's defaults (tests/** keep-whole, lib/** as the runtime
    surface) are wrong for e.g. coreutils, whose test suite the
    box recipe never runs and whose lib/ is gnulib — compiled
    members are graph-class there, uncompiled ones drop."""
    out = {}
    for cf in files:
        p = cf.path
        if p in keep_files or any(
                p.startswith(k) for k in
                tuple(keep_prefixes) + tuple(extra_keep)):
            out[p] = "keep"
        elif p in graph_files:
            out[p] = "graph"
        elif runtime_prefix and p.startswith(runtime_prefix):
            out[p] = "keep"   # runtime-source surface (header docstring)
        elif p.endswith(SOURCE_EXTS):
            out[p] = "drop"
        else:
            out[p] = "keep"   # build machinery, docs, data
    # build-referenced rescue, two tiers. Tier 1 (structural):
    # the configured build's own dependency graph — a drop
    # candidate reachable as a prerequisite from the default
    # goal in the harvest's make database is a build input for
    # this configuration (generation templates: coreutils'
    # lib/arpa_inet.in.h, from which arpa/inet.h is sed-generated
    # — subject-2 bug 6; unreachable rules, which automake emits
    # for unconfigured objects, do not rescue).
    # Tier 2 (textual): a drop candidate whose basename is named
    # by a kept build-instruction file (the phcc Makefile names
    # conftest.c, a c2str.exe input no link ever pulls — first
    # receipts build, bug 2). A path-qualified TEXT scan is NOT a
    # tier: template files (Makefile.in, gnulib Makefile.am) name
    # every file that could build under any configuration, which
    # rescued the entire cu tree and pruned nothing.
    for cf in files:
        if out[cf.path] == "drop" and cf.path in build_prereqs:
            out[cf.path] = "keep"
    hay = [cf.data for cf in files
           if out[cf.path] == "keep" and is_build_ref_file(cf.path)]
    if hay:
        blob = b"\n".join(hay)
        for cf in files:
            if out[cf.path] == "drop":
                base = cf.path.rsplit("/", 1)[-1].encode()
                if base and re.search(rb"(?<![\w./-])" + re.escape(base) +
                                      rb"(?![\w.-])", blob):
                    out[cf.path] = "keep"
    return out


def build_graph(files, classes):
    """Members of graph-class files; name index; raw payload store."""
    members = {}
    name2members = {}
    for cf in files:
        if classes[cf.path] != "graph":
            continue
        for m in cf.members:
            if m.kind == "gap":
                continue
            members[m.mid] = m
            for n in m.names:
                name2members.setdefault(n, []).append(m.mid)
    return members, name2members


C_KEYWORDS = frozenset(
    "auto break case char const continue default do double else enum "
    "extern float for goto if inline int long register restrict return "
    "short signed sizeof static struct switch typedef union unsigned "
    "void volatile while _Bool _Complex _Imaginary".split())
# preprocessor directive vocabulary: the first word of a #-line is a
# directive, never an identifier reference
PP_COND_RE = re.compile(
    rb"(?m)^\s*#\s*(?:if|ifdef|ifndef|elif|else|endif)\b")
PP_WORDS = frozenset(
    "define undef include ifdef ifndef if elif else endif error "
    "pragma line defined warning assert".split())
PROVIDER_CAP = 40


def build_suffix_index(name2members):
    """name-suffix -> [member ids]: for every member name, every
    suffix after an underscore (ELF64_R_INFO registers R_INFO and
    INFO). Paste families (ELFW(R_INFO) -> ELF64_##R_INFO) reference
    a name by its suffix alone; the suffix index is their edge."""
    idx = {}
    for name, mids in name2members.items():
        parts = name.split("_")
        for i in range(1, len(parts)):
            suf = "_".join(parts[i:])
            if len(suf) >= 3:
                idx.setdefault(suf, []).extend(mids)
    return idx


def member_edges(m, name2members, toks, providers, suffix_index):
    """Out-edges of one member: every member bearing a name tokenised
    in its payload (raw scan — comments/strings/asm included); for a
    referenced token with no name-bearing member, fall back to the
    provider index — members whose payload carries the token at all.
    The fallback exists for identifiers a member DEFINES without
    being NAMED by them: enum enumerators (ERROR_WARN and the
    TCC_OPTION_* table in tcc.h are the corpus's witnesses) live
    inside a type member whose index name is the enum's, and only a
    payload-level index can see them. A token with neither a bearer
    nor a provider falls to the suffix index: paste families name a
    definition by suffix (ELFW(R_INFO) in x86_64-link.c pastes to
    ELF64_R_INFO in elf.h — receipts build, bug 4)."""
    out = set()
    for name in toks[m.mid]:
        # the suffix fallback is for macro-style paste fragments
        # (R_INFO, R_SYM): a plain lowercase token is vocabulary —
        # without this gate the keyword 'static' suffix-matches
        # every *_static member in the corpus
        targets = name2members.get(name) or providers.get(name) \
            or (suffix_index.get(name)
                if any(c.isupper() for c in name) else None)
        if targets:
            for mid in targets:
                if mid != m.mid:
                    out.add(mid)
    return out


def build_providers(members, name2members, toks):
    """token -> [member ids] for referenced tokens no member is
    named by. Keywords and corpus-common tokens (> PROVIDER_CAP
    carriers) are excluded: they are vocabulary, not definitions."""
    referenced = set()
    for t in toks.values():
        referenced |= t
    orphans = {t for t in referenced
               if t not in name2members and t not in C_KEYWORDS
               and t not in PP_WORDS and len(t) >= 3}
    providers = {}
    for mid, tset in toks.items():
        if members[mid].kind != "type":
            continue  # payload-defined identifiers live in type
            # members: enum enumerators are the witnessed class
        for t in tset & orphans:
            providers.setdefault(t, []).append(mid)
    return {t: ms for t, ms in providers.items()
            if len(ms) <= PROVIDER_CAP}


# ------------------------------------------------------------ prune core
def prune(phext_path, harvest_path, extra_roots, extra_keep,
          runtime_prefix=LIB_PREFIX, keep_prefixes=None,
          keep_files=None):
    if keep_prefixes is None:
        keep_prefixes = KEEP_WHOLE_PREFIXES
    if keep_files is None:
        keep_files = KEEP_WHOLE_FILES
    scrolls, files = load_carried(phext_path)
    files_by_path = {cf.path: cf for cf in files}
    hv = Harvest(harvest_path)

    # Archive members with no loose object in the harvest were still
    # compiled from a carried source: resolve member stems against
    # the carried file set and fold their symbol tables in, so the
    # source joins the graph and its undefineds join the validation.
    by_stem = {}
    for p in files_by_path:
        by_stem.setdefault(os.path.basename(p).rsplit(".", 1)[0],
                           []).append(p)
    for lib, amembers in hv.archives.items():
        for mname, info in amembers.items():
            stem = mname.rsplit(".", 1)[0]
            cands = by_stem.get(stem, [])
            if len(cands) != 1:
                continue
            src = cands[0]
            if src in hv.by_source:
                continue  # the loose object already speaks for it
            hv.compiled_sources.add(src)
            hv.archive_sources.add(src)
            for s in info["defined_global"]:
                hv.def_global.setdefault(s, set()).add(src)
            for s in info["defined_local"]:
                hv.def_local.setdefault(s, set()).add(src)
            hv.undefined_by_source.setdefault(src, set()).update(
                info["undefined"])

    graph_files = set(hv.compiled_sources) | hv.archive_sources
    graph_files |= include_closure(files_by_path,
                                   {p for p in graph_files
                                    if p in files_by_path},
                                   hv.build_prereqs)
    graph_files &= set(files_by_path)
    classes = classify_files(files, graph_files, extra_keep,
                             keep_prefixes=keep_prefixes,
                             runtime_prefix=runtime_prefix,
                             keep_files=keep_files,
                             build_prereqs=hv.build_prereqs)
    members, name2members = build_graph(files, classes)

    # definer maps, nm-truthed: symbol -> [member ids]
    sym_definers = {}
    for mid, m in members.items():
        for n in m.names:
            if m.path in hv.def_global.get(n, ()):
                sym_definers.setdefault(n, []).append(mid)
    toks = {mid: {t.decode("ascii", "replace")
                  for t in IDENT_RE.findall(m.payload)}
            for mid, m in members.items()}
    providers = build_providers(members, name2members, toks)
    suffix_index = build_suffix_index(name2members)
    edges = {mid: member_edges(m, name2members, toks, providers,
                               suffix_index)
             for mid, m in members.items()}

    # ---- roots
    roots, root_why = set(), {}

    def add_root(mid, why):
        if mid not in roots:
            roots.add(mid)
            root_why.setdefault(mid, []).append(why)

    for mid in sym_definers.get("main", []):
        add_root(mid, "entry: main")
    # positional tables: token-table files (*-tok.h, tcctok.h) are
    # enumerator factories — each row's meaning is its position, the
    # identifiers are manufactured by token pasting (TOK_ASM_##x) so
    # no payload anywhere names them, and dropping one row silently
    # renumbers every later token. Rooted as units. (Receipts build,
    # bug 3: TOK_ASM_int undeclared in i386-asm.c.)
    for mid, m in members.items():
        base = m.path.rsplit("/", 1)[-1]
        if base.endswith("-tok.h") or base == "tcctok.h":
            add_root(mid, "tok-table (positional)")
    # preprocessor-conditional structure: a member carrying an
    # #if-family or #endif line is one half of a brace pair whose
    # other half may live in another member — dropping either half
    # unbalances the file for every configuration, not just this
    # one. Rooted as units. (Receipts build, bug 5: bcheck.c
    # '#endif expected'.)
    for mid, m in members.items():
        if PP_COND_RE.search(m.payload):
            add_root(mid, "pp-conditional structure")
    # archive pull closure: the link's own symbol resolution, replayed
    # over the harvest — seed with every non-archive object's
    # undefineds (the executable, the test programs, the loose
    # runtime objects), pull archive members that define a needed
    # symbol, inherit their undefineds, to a fixpoint.
    needed = set()
    for info in hv.objects.values():
        needed.update(info["undefined"])
    pulled, changed = set(), True
    while changed:
        changed = False
        for lib, amembers in hv.archives.items():
            for mname, info in amembers.items():
                if (lib, mname) in pulled:
                    continue
                if needed & set(info["defined_global"]):
                    pulled.add((lib, mname))
                    needed.update(info["undefined"])
                    changed = True
    res_pulled = sorted(f"{lib}[{m}]" for lib, m in pulled)
    unpulled = sorted(f"{lib}[{m}]" for lib, mem in hv.archives.items()
                      for m in mem if (lib, m) not in pulled)
    # root the definers of exactly the demanded symbols: the final
    # needed-set is the link closure's demand list (the executable's,
    # the tests', the pulled members' own undefineds). Globals of a
    # pulled object that nothing demanded are NOT rooted — they
    # survive only on payload edges, which is the pruning.
    for sym in sorted(needed):
        for mid in sym_definers.get(sym, []):
            add_root(mid, f"demanded by link closure: {sym}")
    for mid, m in members.items():
        if any(p in m.payload for p in PATTERN_ROOTS):
            add_root(mid, "loader-called (constructor/destructor/used)")
    ambient = bytearray()
    for cf in files:
        if classes[cf.path] == "keep":
            ambient += cf.data or b""
        elif classes[cf.path] == "graph":
            for m in cf.members:
                if m.kind == "gap":
                    ambient += m.payload
    ambient = bytes(ambient)
    for mid, m in members.items():
        for n in m.names:
            if len(n) >= 3 and n.encode() in ambient:
                add_root(mid, f"ambient text names {n}")
                break
    indeg = set()
    for outs in edges.values():
        indeg |= outs
    graph_blob = {}
    for cf in files:
        if classes[cf.path] == "graph":
            graph_blob[cf.path] = cf.data or b""
    for mid, m in members.items():
        if mid in indeg or mid in roots:
            continue
        for n in m.names:
            if len(n) >= 4 and any(n.encode() in blob for p, blob
                                   in graph_blob.items() if p != m.path):
                add_root(mid, f"paste net: {n} survives as substring")
                break
    for sym in extra_roots:
        for mid in sym_definers.get(sym, []):
            add_root(mid, f"--root {sym}")

    # ---- BFS + validation fixpoint
    kept, forced = set(roots), []
    changed = True
    while changed:
        changed = False
        stack = list(kept)
        seen = set(kept)
        while stack:
            cur = stack.pop()
            for nxt in edges.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if seen != kept:
            kept = seen
            changed = True
        for src, undefs in hv.undefined_by_source.items():
            for u in sorted(undefs):
                ds = sym_definers.get(u, [])
                if ds and not any(d in kept for d in ds):
                    for d in ds:
                        kept.add(d)
                        forced.append({"symbol": u, "required_by": src,
                                       "member": list(d)})
                    changed = True
    dropped = {mid for mid in members if mid not in kept}
    buildref_keeps = sorted(
        cf.path for cf in files
        if classes[cf.path] == "keep" and cf.path.endswith(SOURCE_EXTS)
        and cf.path not in graph_files
        and not cf.path.startswith(
            tuple(keep_prefixes) +
            ((runtime_prefix,) if runtime_prefix else ()) +
            tuple(extra_keep))
        and cf.path not in keep_files)
    return {"scrolls": scrolls, "files": files, "classes": classes,
            "buildref_keeps": buildref_keeps,
            "members": members, "kept": kept, "dropped": dropped,
            "forced": forced, "roots": roots, "root_why": root_why,
            "graph_files": graph_files, "harvest": hv,
            "pulled": res_pulled, "unpulled": unpulled}


# ------------------------------------------------------------ emission
def emit(res, phext_path):
    scrolls, files = res["scrolls"], res["files"]
    classes, dropped = res["classes"], res["dropped"]
    out = {}
    # Volume 1 verbatim (library 1, collection 1, volume 1)
    for c, b in scrolls.items():
        if c[0] == 1 and c[3] == 1 and c[4] == 1:
            out[c] = b
    # Source Volume 3 scrolls keyed by their file's (book, chapter, section)
    v3_by_file = {}
    for c, b in scrolls.items():
        if c[3] == 4 and c[4] == 3:
            v3_by_file.setdefault((c[5], c[6], c[7]), {})[c[8]] = (c, b)
    file_keys = {(cf.coord[5], cf.coord[6], cf.coord[7]) for cf in files}
    orphan_v3 = 0
    for key, scr_map in v3_by_file.items():
        if key not in file_keys:
            for c, b in scr_map.values():
                out[c] = b
                orphan_v3 += 1
    manifest_rows, dropped_files, per_file = [], [], {}
    base_sha = sha256(open(phext_path, "rb").read())
    for cf in files:
        cls = classes[cf.path]
        if cls == "drop":
            dropped_files.append(cf.path)
            continue
        drops_here = [m for m in cf.members if m.mid in dropped] \
            if cf.structured else []
        per_file[cf.path] = {"class": cls, "structured": cf.structured,
                             "members_before": len(cf.members),
                             "members_dropped": len(drops_here)}
        if cls == "keep" or not cf.structured or not drops_here:
            out[cf.coord] = cf.data
            key = (cf.coord[5], cf.coord[6], cf.coord[7])
            for scr, (c, b) in v3_by_file.get(key, {}).items():
                out[c] = b
            manifest_rows.append((cf.path, cf.coord, cf.sha, cf.size,
                                  cf.mode))
            continue
        # graph file with drops: re-tile kept rows, rewrite spans
        kept_rows = [m for m in cf.members if m.mid not in dropped]
        cursor, new_rows, new_parts = 0, [], []
        v2 = cf.coord
        for m in kept_rows:
            nspan = (cursor, cursor + len(m.payload))
            cursor = nspan[1]
            new_rows.append((m, nspan))
            new_parts.append(m.payload)
            hdr = (f"#phcc-member\tkind={m.kind}\t"
                   f"name={','.join(m.names) if m.names else '-'}\t"
                   f"form={m.form}\tspan={nspan[0]}-{nspan[1]}\t"
                   f"sha256={m.psha}\n").encode()
            out[m.seg_coord] = hdr + m.payload
        new_data = b"".join(new_parts)
        new_sha = sha256(new_data)
        out[v2] = new_data
        head = []
        for line in cf.index_head:
            if line.startswith("# sha256:"):
                head.append(f"# sha256: {new_sha}  size: {len(new_data)}")
            elif line.startswith("# parse:"):
                head.append(line + f"; pruned by phcc prune (rung A): "
                                   f"dropped {len(drops_here)} of "
                                   f"{len(cf.members)} rows")
            else:
                head.append(line)
        idx_lines = list(head)
        for m, nspan in new_rows:
            idx_lines.append(f"{m.scr}\t{m.kind}\t"
                             f"{','.join(m.names) if m.names else '-'}\t"
                             f"{m.form}\t{nspan[0]}-{nspan[1]}\t{m.psha}")
        idx_coord = (1, 1, 1, 4, 3, v2[5], v2[6], v2[7], 1)
        out[idx_coord] = ("\n".join(idx_lines) + "\n").encode()
        manifest_rows.append((cf.path, cf.coord, new_sha, len(new_data),
                              cf.mode))
    # placement manifest, rewritten for the pruned file set
    orig_man = scrolls[MANIFEST_COORD].decode("utf-8")
    man_head = [l for l in orig_man.splitlines() if l.startswith("#")]
    man = list(man_head)
    man.append("# pruned by phcc prune (rung A) — placement rows below "
               "describe the PRUNED file set; dropped files are listed "
               "in the prune manifest (1.1.1/1.2.10/2.1.1)")
    for path, coord, sha, size, mode in manifest_rows:
        man.append(f"{path}\t{fmt(coord)}\t{sha}\t{size}\t{mode}")
    out[MANIFEST_COORD] = ("\n".join(man) + "\n").encode()
    out[NOTES_COORD] = scrolls[NOTES_COORD]
    stats = {"base_sha256": base_sha, "dropped_files": dropped_files,
             "per_file": per_file, "orphan_v3_carried": orphan_v3}
    return out, stats


def prune_manifest_text(res, stats):
    kept_n = sum(1 for cf in res["files"]
                 if res["classes"][cf.path] != "drop")
    mem_before = sum(len(cf.members) for cf in res["files"] if cf.structured)
    mem_dropped = len(res["dropped"])
    lines = [
        "# phcc prune manifest — phcc prune (phcc -O2 rung A: member-graph pruning)",
        f"# base phext sha256: {stats['base_sha256']}",
        "# configuration: default host build + test suite (harvest-driven); "
        "see tool docstring for the root policy and file classes",
        f"# files: {kept_n} kept of {len(res['files'])} carried "
        f"({len(stats['dropped_files'])} dropped whole)",
        f"# member rows (structured files): {mem_before} before, "
        f"{mem_dropped} dropped, {mem_before - mem_dropped} kept",
        f"# closure-forced keeps: {len(res['forced'])}",
        "# derived phases of the base phext (Design/Tests/Regressions/"
        "Docs/Proofs collections, gate verdicts, Library-10000 build "
        "region, Vol-3 rebind manifest) are NOT carried: their hash "
        "bindings name the unpruned source set. Regenerate by their "
        "own passes.",
        "",
        "## dropped files (whole)",
    ]
    lines += stats["dropped_files"]
    lines += ["", "## build-referenced keeps (reachable in the "
                  "configured build graph, or named by kept "
                  "build-instruction files)"]
    lines += res["buildref_keeps"]
    lines += ["", "## archive members pulled by the link closure"]
    lines += res["pulled"]
    lines += ["", "## archive members NOT pulled (their undemanded "
                  "globals are the pruning frontier)"]
    lines += res["unpulled"]
    lines += ["", "## closure-forced keeps (symbol, required_by, member)"]
    for f in res["forced"]:
        lines.append(f"{f['symbol']}\t{f['required_by']}\t"
                     f"{f['member'][0]}#{f['member'][1]}")
    lines += ["", "## dropped members (path, scroll, kind, name, form, "
                  "span, sha256)"]
    by_path = {}
    for mid in res["dropped"]:
        by_path.setdefault(mid[0], []).append(res["members"][mid])
    for path in sorted(by_path):
        for m in sorted(by_path[path], key=lambda m: m.scr):
            lines.append(f"{path}\t{m.scr}\t{m.kind}\t"
                         f"{','.join(m.names) if m.names else '-'}\t"
                         f"{m.form}\t{m.span[0]}-{m.span[1]}\t{m.psha}")
    return ("\n".join(lines) + "\n").encode()


# ------------------------------------------------------------ cli
def cli(argv):
    ap = argparse.ArgumentParser(prog="phcc prune",
                                 description="phcc -O2 rung A: member-graph "
                                             "pruning of a carried phext")
    ap.add_argument("--phext", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--harvest", required=True,
                    help="harvest.py JSON for a tree built from --phext")
    ap.add_argument("--report", default=None)
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--keep-prefix", action="append", default=[])
    ap.add_argument("--runtime-prefix", default=LIB_PREFIX,
                    help="prefix kept whole as the runtime-source "
                         "surface (default 'lib/'; '' disables — "
                         "right for coreutils' gnulib lib/)")
    ap.add_argument("--keep-prefixes", default=None,
                    help="comma list REPLACING the default keep-whole "
                         "prefix set (tests/,examples/,include/,"
                         "tools/,phext/); '' for none — right when "
                         "the recipe never builds the test suite")
    ap.add_argument("--keep-files", default=None,
                    help="comma list REPLACING the keep-whole file "
                         "set (default tcclib.h); '' for none")
    a = ap.parse_args(argv)

    kp = None if a.keep_prefixes is None else tuple(
        p for p in a.keep_prefixes.split(",") if p)
    kf = None if a.keep_files is None else tuple(
        p for p in a.keep_files.split(",") if p)
    res = prune(a.phext, a.harvest, a.root, a.keep_prefix,
                runtime_prefix=a.runtime_prefix,
                keep_prefixes=kp, keep_files=kf)
    out, stats = emit(res, a.phext)
    man = prune_manifest_text(res, stats)
    out[PRUNE_MANIFEST_COORD] = man
    blob = implode(out)
    # self-check: the emitted phext must load and verify end-to-end
    import tempfile
    with tempfile.NamedTemporaryFile("wb", suffix=".phext",
                                     delete=False) as tf:
        tf.write(blob)
        tmp = tf.name
    try:
        load_carried(tmp)
    except SystemExit as e:
        os.unlink(tmp)
        print(f"phcc prune: SELF-CHECK FAILED: {e}", file=sys.stderr)
        return 1
    os.replace(tmp, a.out)
    def source_bytes(scrolls):
        v2 = sum(len(b) for c, b in scrolls.items()
                 if c[3] == 4 and c[4] == 2)
        v3 = sum(len(b) for c, b in scrolls.items()
                 if c[3] == 4 and c[4] == 3)
        return v2, v3

    sv2b, sv3b = source_bytes(res["scrolls"])
    sv2a, sv3a = source_bytes(out)
    report = {
        "base_phext": a.phext, "base_sha256": stats["base_sha256"],
        "out_phext": a.out, "out_bytes": len(blob),
        "source_vol2_bytes_before": sv2b, "source_vol2_bytes_after": sv2a,
        "source_vol3_bytes_before": sv3b, "source_vol3_bytes_after": sv3a,
        "out_sha256": sha256(blob),
        "files_carried": len(res["files"]),
        "files_kept": len(res["files"]) - len(stats["dropped_files"]),
        "files_dropped": stats["dropped_files"],
        "buildref_keeps": res["buildref_keeps"],
        "members_total": sum(len(cf.members) for cf in res["files"]
                             if cf.structured),
        "members_dropped": len(res["dropped"]),
        "forced_keeps": res["forced"],
        "per_file": stats["per_file"],
        "graph_files": sorted(res["graph_files"]),
        "archive_pulled": res["pulled"],
        "archive_unpulled": res["unpulled"],
        "orphan_v3_carried": stats["orphan_v3_carried"],
    }
    if a.report:
        with open(a.report, "w") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
    print(f"prune OK: {a.out}  {len(blob)} bytes  sha256 {sha256(blob)}")
    print(f"  files: {report['files_kept']}/{report['files_carried']} kept, "
          f"{len(stats['dropped_files'])} dropped whole")
    print(f"  members: {len(res['dropped'])} dropped of "
          f"{report['members_total']} rows; "
          f"closure-forced keeps: {len(res['forced'])}")
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
