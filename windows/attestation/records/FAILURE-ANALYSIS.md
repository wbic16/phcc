# MSVC attestation — failure analysis (v1 run, 2026-11-09)

Receipt filed at `attestation-receipt-2026-11-09.txt` (copy of the receipt Will
returned). Verdict: **NOT ATTESTED, msvc-agree 3/289**, under
Microsoft C/C++ Optimizing Compiler **19.51.36260** for x64, scope bound to
manifest-sha256 `9f347432fcad87e614a24d1c664b4fb4154419b178f0fcd13852dd1cadbd859e`
and phcc commit `8217e426b3c961b37635468e15647fec5ec19afd`.

This failure is a **package defect, not a compiler divergence**. The 286
mismatches classify completely into three groups, with nothing left over:

## Census (from expected.json + the receipt's mismatch list)

- 289 probes = **286 run probes** (`expect_compile: true`) + **3 reject probes**
  (`expect_compile: false`).
- The **3 agreeing probes are exactly the 3 reject probes** —
  `neg_dupcase`, `neg_incomplete`, `neg_staticassert`. They agree because
  they are never run, so no stdout is ever compared.
- The 286 mismatches = **282 run failures** + **4 compile-class failures**.
- Every one of the 282 run failures has the same shape:
  `rc=<expected>/<expected>, stdout match=False` — **every exit code matched**;
  only the stdout hash differed.

## Group 1 — 282 run probes: CRLF vs LF stdout bytes

The expected hashes in `expected.json` are hashes of the **Linux oracle
output bytes (LF newlines)**. A Windows C program's stdout in text mode
translates `\n` to `\r\n`, so every captured output file differs from the
oracle bytes by one `\r` per line. The v1 script hashed the raw captured
file, so all 282 failed on the hash alone.

Proof on the first probe: `a_arith_001` prints `1 1\n`.

- `sha256("1 1\n")` = `3f11ad6bbc7ecca0b2416b713dee77f1a635c00aaeaa946e14cde1c2bfae56d5`
- `expected.json` records `a_arith_001.stdout_sha256` =
  `3f11ad6bbc7ecca0b2416b713dee77f1a635c00aaeaa946e14cde1c2bfae56d5` — identical.

The expected value is the LF-byte hash; the Windows capture of the same
program output is the CRLF-byte string, whose hash necessarily differs.
Fix (v2): normalize CRLF→LF on the captured raw bytes before hashing, and
document that the comparison is of program output modulo the platform
text-mode newline translation.

## Group 2 — 4 probes: C11 atomics flag

`a_atomic_001`–`a_atomic_004` failed **compile class** (msvc=False,
expected=True). MSVC gates C11 atomics behind `/experimental:c11atomics`;
v1's invocation (`/std:c17 /TC`) does not pass it, so the `<stdatomic.h>`
probes do not compile. Fix (v2): pass `/experimental:c11atomics`, guarded
by a one-time canary compile; if cl rejects the flag itself, v2 falls back
to the v1 invocation for all probes and notes the fallback in the receipt.

## Group 3 — 1 of the 282: a_pp_018, named class-(b) divergence

`a_pp_018` is inside the 282 run failures and carries a second, independent
reason to differ: it prints `__STDC_VERSION__`, which is divergent-by-design
across the whole conformance programme (class (b) — phcc's default mode
advertises 199901; MSVC's C17 mode advertises its own value). CRLF
normalization cannot and should not make this probe "agree". Fix (v2): its
expected.json entry is annotated as a named class-(b) divergence; v2
reports named divergences on their own receipt line
(`named-divergences: a_pp_018 (__STDC_VERSION__, class b)`) and excludes
them from the agree denominator — ATTESTED requires all *counted* probes
to agree.

## Disposition

Attestation package v2 (`attestation-v2/`, `attestation-v2.zip`) implements
the three fixes. Its comparison logic is dress-rehearsed against the stored
oracle outputs (see the v2 build record in the conformance task register):
the Windows transform applied to the oracle bytes reproduces Will's failure
shape exactly without normalization, and every run probe agrees after
normalization. **The re-run is Will's** — MSVC exists only on his machine.
