# Conformance — measured, classified, receipted

phcc's compatibility claim is not "trust us". It is a differential
programme: the same probe programs are compiled and run under
**gcc**, **clang** and **phcc**, the observable results are
compared, and **every divergence is classified** — a receipt
containing an unclassified divergence is not a receipt.

- **(a) phcc defect** — the oracles agree, phcc differs on defined
  behaviour. Fix the compiler, or file a Regression scroll.
  Release-blocking debt, never silently waived.
- **(b) intentional / documented difference** — a written-down
  property of the fork or of upstream (an extension never claimed,
  a documented dialect level). The difference text lives beside
  the receipt.
- **(c) undefined / implementation-defined** — measured and
  tabulated in the Tier C catalogue, not chased as a defect.

## The surface

| Tier | Contents |
|------|----------|
| A | C11/C17 core semantics: arithmetic/promotion/conversion edges, preprocessor, struct layout on the target ABI, enums, `_Bool`, compound literals, designated initializers, `_Generic`, `_Static_assert`, stdatomic basics |
| B | GNU C extensions TinyCC actually claims (evidence from its docs/tests): `typeof`, statement expressions, common `__builtin_*`, `__attribute__((packed))` / `((aligned))`, case ranges, VLAs, … |
| C | The implementation-defined catalogue: fundamental sizes/alignments, `char` signedness, negative right-shift, bitfield rules, `long double` width, `<float.h>`/`<limits.h>` values |
| Windows | PE target, `__declspec`, MSVC-mode pragmas, Windows SDK header compatibility — a named part of the surface; its oracle column is the manual attestation below |

## Where slice 1 stands (2026-11-07)

333 probes (Tier A 289, B 22, C 22), run on Linux x86_64 against
gcc 13.3.0 and clang 18.1.3 as automated oracles:

- gcc ≡ clang on **333/333** probes — no oracle splits, so every
  divergence is a phcc fact.
- Three-way agreement: **328/333**, with **0 unclassified**.
- Two **(a)** defects were found — `__attribute__((packed))` and
  `__attribute__((aligned))` were silently inert (glibc's headers
  macro-define `__attribute__` away for compilers that declare
  neither `__GNUC__` nor `__clang__`, and phcc's preprocessor
  obeyed). Both are **fixed** (PATCHES.md **F5**), re-probed to
  full agreement, and recorded as resolved Regressions
  REG-CONF-1 / REG-CONF-2.
- The five standing divergences are all class **(b)**:
  `__STDC_VERSION__` reports the documented C99 level (199901);
  `_Complex` is unsupported, per upstream's own documented
  disclaimer (two probes); `__builtin_bswap16/32` are absent;
  `__auto_type` is not claimed.
- Tier C matched both oracles on **22/22** catalogue items.

Receipts live inside `phcc.phext`: probes at Tests (Collection 5),
Volume 2, **Book 11** (Chapters 1/2/3 = Tiers A/B/C, Chapter 4
reserved for the Windows surface, Chapter 9 = run receipts), the
register at Meta Sec 21, and the gate's report-only `conformance`
section (gate v8.1.0) re-verifies them. Probe method: identical
flags discipline per compiler class, output compared as
(compile exit class, run exit, stdout bytes); undefined-behaviour
probes are excluded by construction.

## MSVC: a manual attestation, and its exact status

There is deliberately **no automated MSVC oracle**. MSVC
compatibility is confirmed by the maintainer, manually, at merge
time on a Windows host, and recorded in the receipt as an
attestation in the same shape as the verification tier system's
waivers — named signer, date, and a scope bound to the
probe-manifest hash and the phcc commit, so it reads STALE when
either moves. Automated tooling can only ever emit
`NOT ATTESTED`; the column never enters the agreement percentages.

> **Current status: `NOT ATTESTED`.**
> Attestation scroll: Tests Book 11, Chapter 9, Section 2 of
> `phcc.phext` — `mode: manual-attestation`, designated signer
> Will Bickford, scope = probe-manifest SHA-256 `c6eebb8a…` +
> phcc commit `94898ff9` (the slice-1 receipt's build).

What exists today on the Windows side, short of attestation: the
win32 build path is pristine upstream and was traced source-level
through the fork's changes; the PE cross targets
(`x86_64-win32`, `i386-win32`) were compile- and link-verified
with PE inspection (`examples/dll/` is that shape at toy scale);
no PE binary has been executed by this project, and no document
here claims otherwise. A three-compiler conformance claim exists
only when a current attestation does.

### Running the attestation

The tooling lives in `windows/attestation/` in this repo:
`attestation.ps1`, the 289 Tier A probe sources, and `expected.json`
(the oracle expectations it compares against). On a Windows host with
Visual Studio's C++ workload installed, run from that directory:

```
powershell -ExecutionPolicy Bypass -File .\attestation.ps1
```

The script finds `cl.exe`, compiles and runs every probe, and writes
`attestation-receipt.txt` beside itself — `ATTESTED` only when every
counted probe matches MSVC on compile class, exit code, and stdout
(stdout is compared modulo the Windows text-mode CRLF translation).
One probe, `a_pp_018` (`__STDC_VERSION__`), is a named class-(b)
divergence: it is reported on its own receipt line and excluded from
the count. Past runs are kept under `windows/attestation/records/` —
including the 2026-11-09 v1 run, which returned `NOT ATTESTED`
(3/289) for package reasons, not compiler reasons: captured CRLF
bytes were hashed against LF expectations, and MSVC's
`/experimental:c11atomics` flag was not passed.
`records/FAILURE-ANALYSIS.md` is the full classification; the
current script is the v2 that fixes both defects.
