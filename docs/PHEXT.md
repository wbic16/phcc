# phcc.phext — the project in one file

Alongside the normal source tree, this repository carries
`phcc.phext`: the **entire project in a single phext file** —
sources at member-level granularity, generated design views, test
placements and receipts, machine-checked models of the compiler's
own state machines, proof receipts for its runtime library,
assembly listings bound by hash to the objects they describe,
binary build artifacts, and a gate verdict that says which of
those claims are currently true. The tree is what you edit; the
phext is the project's memory of itself, with receipts.

`phcc.phext.xz` next to it is the **seal**: an xz-compressed copy
for storage and transport. The working form is the plain text
phext; the seal is a seal, not a working format — unseal it to
work on it.

Canonical values for the current file (they change as the phext
evolves; `tools/README.md` always carries the current block):

| | |
|---|---|
| `phcc.phext` | 63,195,664 bytes · 63,640 scrolls · SHA-256 `82bd0745e2dc6b1320e9c00865200ec8cca6accd14689585d7168b48300c1f21` |
| `phcc.phext.xz` | 5,883,468 bytes · SHA-256 `ffadce9bf7f56a0d9f534fd7767bb928454e695097ff5c2e27232faea042ad4e` |
| Gate verdict | Meta `1.1.1/1.2.10/1.20.1` (gate v8.1.0) · SHA-256 `e32b9ee9b2939dd22ee5eeb176e7e8522228f000c170901dacd45a036bb10ec1` |

## Moving between tree and phext: pack / unpack

Everything goes through one dispatcher, `tools/phcc`
(methodology and invariants: `tools/METHODS.md`):

```sh
python3 tools/phcc unpack --phext phcc.phext --out tree/
python3 tools/phcc pack   --tree tree/ --out phcc.phext --base previous.phext
```

- **unpack** reads the placement manifest stored inside the phext
  and materialises the 558 tree files, **SHA-256-verifying every
  file against the manifest before writing it**. A tampered scroll
  means that file is withheld, the failure is named, and the exit
  code is 1. Two routes exist: `--from vol2` (default; each file is
  a whole-file scroll) and `--from vol3` (structured files
  reassembled from member-level segment scrolls).
- **pack** places every tree file by the project's placement
  (Book = module, Chapter = component, Section = file), then
  re-segments structured files into member scrolls. A file no
  placement rule covers **aborts the pack, by name** — nothing is
  silently dropped. A phext cannot byte-exactly contain itself, so
  `phcc.phext` and `monolith.phext` are excluded by design and the
  exclusions are recorded in the manifest.
- Round-trips are identities on the canonical corpus:
  tree → phext → tree reproduces all 558 files byte-identically,
  via both unpack routes.

`examples/phext-pack/` runs this exact workflow on a three-file
toy project, so you can watch it work before trusting it with
anything bigger.

> **Known gap (2026-11-07):** a whole-tree `pack` of the current
> repository tree aborts, by name, on 13 paths — the `phext/`
> library directory and the `phcc.phext.xz` seal (both added to
> the tree after the placement table was written), and this
> documentation set (`README.md`, `docs/`). The placement table
> in `tools/phcc_migrate.py` predates them. The canonical phext
> is meanwhile maintained by the slice passes' direct assembly,
> and the `phext/` sources ride in it via the Book 10 Chapter 10
> addendum; extending `place()` to cover these paths is queued
> with the next phext pass. Nothing is silently dropped in the
> meantime — the abort *is* the protection.

## The gate

`tools/phcc_gate.py` is the phext's report-only auditor. It
re-checks every hash binding in the file — sources against design
views, state-machine models against the members they claim to
describe, proof receipts against their sources, assembly listings
against their build-region objects, the conformance corpus
against its receipts — and writes a **verdict scroll** into the
phext (currently at Meta `1.1.1/1.2.10/1.20.1`). A binding whose
target moved reads **STALE**, never silently current; the gate
reports, it does not block.

```sh
python3 tools/phcc_gate.py phcc.phext            # print the tables
python3 tools/phcc_gate.py phcc.phext --verdict-out out.phext
```

The verdict content is deterministic (no timestamps): re-running
the gate on a phext that already carries its verdict reproduces
the identical verdict hash.

## The build region, and the seal

Build artifacts live in the phext too, in a deliberately wipeable
region rooted at Library 10000 (base `10000.1.1/1.1.1/1.1.1`):
object files and archives encoded in the canonical binary scroll
format — a header line `phext-binary:1:base64` followed by
unwrapped RFC 4648 base64, the format libphext-rs 0.5 defines —
each with a provenance manifest entry (source hash, compiler
commit, target, host, timestamp). The matching assembly listings
sit in the Design phase, hash-bound to the region objects.

```sh
python3 tools/phcc build-region list --phext phcc.phext
python3 tools/phcc build-region wipe --phext phcc.phext --out wiped.phext
python3 tools/phcc seal   --phext phcc.phext          # -> phcc.phext.xz
python3 tools/phcc unseal --sealed phcc.phext.xz      # -> back, byte-identical
```

## Verify a fresh clone end-to-end

Five commands take you from clone to a tree the phext itself
vouches for:

```sh
sha256sum phcc.phext phcc.phext.xz        # compare with tools/README.md
python3 tools/phcc unseal --sealed phcc.phext.xz --out /tmp/u.phext
cmp phcc.phext /tmp/u.phext               # seal round-trips byte-identically
python3 tools/phcc unpack --phext phcc.phext --out /tmp/tree
cd /tmp/tree && ./configure && make && make test   # ALL TESTS PASSED
```

At the commit these docs were written, that unpacked tree is
byte-identical to the repository tree across all 558 files.
