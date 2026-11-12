# Attestation script fix — v2.1 (2026-11-11): native captures are stderr-safe

## Symptom

First live run of the v2 script (Will, 2026-11-11, MSVC 19.51.36260,
`C:\source\phcc\windows\attestation`):

```
.\attestation.ps1
cl.exe : Microsoft (R) C/C++ Optimizing Compiler Version 19.51.36260 for x64
At C:\source\phcc\windows\attestation\attestation.ps1:86 char:15
+ $clVersion = (& $cl 2>&1 | Select-Object -First 1)
    + CategoryInfo          : NotSpecified: (Microsoft (R) C...1.36260 for x64:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
```

The run died at the cl-version capture, before a single probe executed.
No receipt was written. This is a script bug, not a compiler result —
the same class of package-measurement failure as the v1 run (see
FAILURE-ANALYSIS.md), one layer earlier.

## Root cause

The script sets `$ErrorActionPreference = "Stop"`. In Windows PowerShell
5.1, when a native command's stderr is redirected into the pipeline
(`2>&1`, or discarded via `2>$null` in a capture context), each stderr
line becomes an error record, and under `Stop` the first one is a
terminating `NativeCommandError`. cl.exe prints its banner — and, during
compiles, all of its diagnostics — to stderr, so the very first capture
was guaranteed to kill the run. Probe compiles write diagnostics to
stderr routinely, and reject-class probes are *supposed* to fail
compilation, so every native capture site in the script was at risk,
not just the version banner.

## Fix (attestation.ps1 only; expected.json and probes/ untouched)

Every native-command capture now runs inside a scoped relaxation of
`$ErrorActionPreference` — saved to `$prevEAP`, set to `"Continue"` for
the call, restored immediately after (in a `finally` where a try block
already existed) — so stderr can be captured or discarded but never
fatal:

1. **cl version capture** (the crash site): the banner capture
   `& $cl 2>&1 | Select-Object -First 1` runs relaxed; the result is
   coerced to a plain string for the receipt's `compiler:` line.
2. **git defaults** (`git config user.name`, `git rev-parse HEAD`, both
   `2>$null`): relaxed, so a repo-less or config-less environment reads
   as "absent" instead of terminating.
3. **Atomics canary** (`& $cl /experimental:c11atomics ... 2>&1 |
   Out-String`): was already inside try/catch, which caught the
   termination but discarded the merged output at the first stderr
   line; it now captures the full output under the relaxed preference,
   with the catch kept and the restore in `finally`. The
   unrecognized-option (D9002) test therefore sees the complete canary
   output, exactly as v2 intended.
4. **Probe compile loop** (`& $cl @clArgs ... 2>$null`): relaxed per
   probe, so diagnostics and expected reject-class failures can never
   terminate the loop; `$LASTEXITCODE` handling is unchanged.

Diagnosed and deliberately left unchanged (no stderr redirection into
the PowerShell stream, so no error records are created): the `vswhere`
lookup (stderr passes through to the console), the vcvars import via
`cmd /c` (redirection there is cmd-internal; PowerShell only reads the
`set` output on stdout), and `Start-Process` for probe executables
(a managed cmdlet with redirected output to file).

## Semantics preserved from v2

- CRLF -> LF byte-wise stdout normalization before hashing.
- `/experimental:c11atomics` with the one-time canary and the
  unrecognized-option-only fallback to the v1 invocation.
- Named-divergence handling (a_pp_018 reported on its own line and
  excluded from the denominator; 288 counted probes).
- Receipt format, exit codes (0 ATTESTED / 1 NOT ATTESTED /
  2 environment), and the ATTESTED-only-on-full-agreement rule.

## Verification

No PowerShell interpreter exists on the build VM or the ranch nodes
(the same constraint as the v2 dress rehearsal), so the patch was
reviewed by careful manual syntax inspection, restricted to
well-established Windows PowerShell 5.1 idioms (preference-variable
save/restore, try/catch/finally). The live verification is the re-run
itself: the script should now pass the version capture, print
`compiler: Microsoft (R) C/C++ Optimizing Compiler Version ...`, and
run all 289 probes to a receipt.

- attestation.ps1 v2   SHA-256: 4362a7923926f8a486b2422c240ef276511c4800a7305e264cc7718cae6a68a8
- attestation.ps1 v2.1 SHA-256: 63580bd980d210001aa234a6f827da18441710aabe55784d729777f371c7f9d9
