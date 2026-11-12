# attestation.ps1 — phcc MSVC manual attestation (Tier A conformance), v2
#
# Runs the 289 Tier A (C11/C17 core) conformance probes under MSVC (cl.exe)
# and compares (compile class, run exit code, stdout bytes) against the
# recorded gcc 13.3.0 / clang 18.1.3 oracle expectations in expected.json.
# Writes attestation-receipt.txt next to this script, in the T0-waiver format:
# ATTESTED only when every counted probe matches; otherwise NOT ATTESTED
# with the mismatching probes named. Tier B (GNU extensions) and Tier C
# (implementation-defined catalogue) are out of scope by design: MSVC does
# not claim the GNU surface, and Tier C outcomes are tabulated, not chased.
#
# v2 changes (the v1 run of 2026-11-09 returned NOT ATTESTED 3/289 for
# package reasons, not compiler reasons — see records/FAILURE-ANALYSIS.md):
#  1. Newline normalization: the oracle hashes are of Linux output bytes
#     (LF). A Windows program's stdout in text mode writes CRLF, so v2
#     translates CRLF -> LF on the captured raw bytes before hashing.
#     The comparison is therefore of program output modulo the platform
#     text-mode newline translation, and of nothing else: the translation
#     is applied byte-wise, so no other byte can change.
#  2. C11 atomics: MSVC gates <stdatomic.h> behind
#     /experimental:c11atomics, which v1 did not pass. v2 passes it,
#     guarded by a one-time canary compile of a_atomic_001: if cl rejects
#     the flag itself (unrecognized-option error), v2 falls back to the
#     v1 invocation for all probes and notes the fallback in the receipt.
#  3. Named divergences: probes whose expected.json entry carries a
#     named_divergence annotation (a_pp_018, __STDC_VERSION__, class b —
#     divergent-by-design across the whole conformance programme) are
#     reported on their own receipt line and excluded from the agree
#     denominator. ATTESTED requires all counted probes to agree.
#
# v2.1 fix (2026-11-11, records/FIX-2026-11-11-stderr-capture.md): native
# captures are stderr-safe. With $ErrorActionPreference = "Stop", any
# stderr line from a native tool becomes a terminating NativeCommandError
# the moment it is redirected into the pipeline — and cl.exe prints its
# banner and all diagnostics to stderr. The first v2 run died at the
# cl-version capture before running a single probe. Every native capture
# below now runs inside a scoped relaxation of $ErrorActionPreference
# (saved before, restored after), so stderr can be captured or discarded
# but never fatal. Receipt format and comparison semantics are v2's.
#
# Everything is resolved relative to this script's own path, so the script
# works identically from a zip extraction or from its in-repo location at
# windows/attestation/.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File .\attestation.ps1
# Optional:
#   -Signer "Will Bickford"     (default: git config user.name, else $env:USERNAME)
#   -PhccCommit <sha>           (default: HEAD of the git repo in the current
#                                directory, if any; the receipt records what
#                                was actually bound)
# Exit code: 0 = ATTESTED, 1 = NOT ATTESTED, 2 = environment problem.

param(
    [string]$Signer = "",
    [string]$PhccCommit = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Expected = Get-Content (Join-Path $Here "expected.json") -Raw | ConvertFrom-Json
$ManifestHash = (Get-FileHash (Join-Path $Here "expected.json") -Algorithm SHA256).Hash.ToLower()

# --- locate cl.exe (vswhere first, PATH second) -------------------------------
$cl = $null
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($install) {
        $candidate = Get-ChildItem (Join-Path $install "VC\Tools\MSVC") -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "bin\Hostx64\x64\cl.exe" } |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($candidate) { $cl = $candidate }
    }
}
if (-not $cl) {
    $onPath = Get-Command cl.exe -ErrorAction SilentlyContinue
    if ($onPath) { $cl = $onPath.Source }
}
if (-not $cl) {
    Write-Host "cl.exe not found. Install Visual Studio with the 'Desktop development with C++' workload, or run from a Developer Command Prompt."
    exit 2
}

# Import the MSVC environment (vcvars64) so includes/libs resolve.
$vcvars = Join-Path (Split-Path (Split-Path (Split-Path (Split-Path $cl)))) "..\..\..\..\Auxiliary\Build\vcvars64.bat"
# (path arithmetic above is fragile across layouts; the robust route:)
$vsRoot = $cl -replace "\\VC\\Tools\\MSVC\\.*$", ""
$vcvars = Join-Path $vsRoot "VC\Auxiliary\Build\vcvars64.bat"
if (Test-Path $vcvars) {
    cmd /c "`"$vcvars`" >nul 2>&1 && set" | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") { Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2] }
    }
}
# cl prints its banner to stderr; capture it with the error preference
# relaxed (see the v2.1 note in the header) so the banner cannot terminate
# the run as a NativeCommandError.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$clVersion = (& $cl 2>&1 | Select-Object -First 1)
$ErrorActionPreference = $prevEAP
$clVersion = "$clVersion"

# --- signer / commit defaults -------------------------------------------------
if (-not $Signer) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $g = git config user.name 2>$null
    $ErrorActionPreference = $prevEAP
    if ($g) { $Signer = $g } else { $Signer = $env:USERNAME }
}
if (-not $PhccCommit) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $h = git rev-parse HEAD 2>$null
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -eq 0 -and $h) { $PhccCommit = $h.Trim() } else { $PhccCommit = "unspecified (pass -PhccCommit)" }
}

# --- stdout hash with CRLF -> LF normalization (byte-wise) --------------------
# Reads the captured file as raw bytes and hashes the byte stream with each
# CRLF pair collapsed to LF. No other byte is touched: a lone CR survives,
# a lone LF survives, and ordering is preserved.
function Get-NormalizedHash([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $ms = New-Object System.IO.MemoryStream
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -eq 13 -and ($i + 1) -lt $bytes.Length -and $bytes[$i + 1] -eq 10) { continue }
        $ms.WriteByte($bytes[$i])
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $digest = $sha.ComputeHash($ms.ToArray()) } finally { $sha.Dispose(); $ms.Dispose() }
    return ([System.BitConverter]::ToString($digest) -replace "-", "").ToLower()
}

# --- named divergences (annotated in expected.json) ---------------------------
$namedDiv = @{}
foreach ($p in $Expected.probes) {
    if ($null -ne $p.named_divergence) { $namedDiv[$p.name] = $p.named_divergence }
}
$namedLine = "named-divergences: " + (@($namedDiv.GetEnumerator() | Sort-Object { $_.Key } | ForEach-Object {
    "$($_.Key) ($($_.Value.label), class $($_.Value.class))"
}) -join "; ")
if ($namedDiv.Count -eq 0) { $namedLine = "named-divergences: none" }

# --- run the probes ------------------------------------------------------------
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("phcc-attest-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$agree = 0; $mismatch = @()
$atomicsFlag = $null; $atomicsFallback = $false
try {
    # One-time canary: does cl accept /experimental:c11atomics? Only an
    # unrecognized-option rejection triggers the v1 fallback; any other
    # canary outcome leaves the flag in place and lets the atomic probes
    # speak for themselves in the main loop.
    $canarySrc = Join-Path $Here (Join-Path "probes" "a_atomic_001.c")
    $canaryExe = Join-Path $work "canary_atomic.exe"
    $canaryObj = Join-Path $work "canary_atomic.obj"
    $canaryOut = ""
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $canaryOut = (& $cl /nologo /std:c17 /TC /experimental:c11atomics /Fe:$canaryExe $canarySrc /Fo:$canaryObj 2>&1 | Out-String)
    } catch { $canaryOut = "$_" } finally { $ErrorActionPreference = $prevEAP }
    if ($canaryOut -match "unrecognized|unknown option|invalid option|D9002") {
        $atomicsFallback = $true
    } else {
        $atomicsFlag = "/experimental:c11atomics"
    }
    $clArgs = @("/nologo", "/std:c17", "/TC", "/W3")
    if ($atomicsFlag) { $clArgs += $atomicsFlag }

    foreach ($p in $Expected.probes) {
        if ($namedDiv.ContainsKey($p.name)) { continue }
        $src = Join-Path $Here (Join-Path "probes" $p.file)
        $exe = Join-Path $work ($p.name + ".exe")
        $obj = Join-Path $work ($p.name + ".obj")
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $cl @clArgs /Fe:$exe $src /Fo:$obj 2>$null | Out-Null
        $ErrorActionPreference = $prevEAP
        $compiled = ($LASTEXITCODE -eq 0) -and (Test-Path $exe)
        if ($compiled -ne [bool]$p.expect_compile) {
            $mismatch += "$($p.name) (compile class: msvc=$compiled, expected=$($p.expect_compile))"
            continue
        }
        if (-not $compiled) { $agree++; continue }
        if ($p.kind -ne "run") { $agree++; continue }
        $outFile = Join-Path $work ($p.name + ".out")
        $proc = Start-Process -FilePath $exe -RedirectStandardOutput $outFile -NoNewWindow -PassThru
        if (-not $proc.WaitForExit(10000)) {
            $proc.Kill(); $mismatch += "$($p.name) (run timeout)"; continue
        }
        $hash = Get-NormalizedHash $outFile
        if ($proc.ExitCode -ne $p.run_rc -or $hash -ne $p.stdout_sha256) {
            $mismatch += "$($p.name) (run: rc=$($proc.ExitCode)/$($p.run_rc), stdout match=$($hash -eq $p.stdout_sha256))"
            continue
        }
        $agree++
    }
} finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

$total = $Expected.probes.Count
$counted = $total - $namedDiv.Count
$status = if ($mismatch.Count -eq 0) { "ATTESTED" } else { "NOT ATTESTED" }
$date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$lines = @(
    "mode: manual-attestation",
    "status: $status",
    "signer: $Signer",
    "date: $date",
    "scope: phcc conformance Tier A (C11/C17 core), $total probes; manifest-sha256: $ManifestHash; phcc-commit: $PhccCommit",
    "result: msvc-agree $agree/$counted",
    "compiler: $clVersion",
    $namedLine
)
if ($atomicsFallback) {
    $lines += "note: cl rejected /experimental:c11atomics as an unrecognized option; fell back to the v1 invocation (no atomics flag) for all probes"
}
$lines += "mismatches: $(if ($mismatch.Count) { $mismatch -join "; " } else { "none" })"
$receipt = $lines -join "`n"
$receiptPath = Join-Path $Here "attestation-receipt.txt"
$receipt | Set-Content -Path $receiptPath -Encoding ASCII
Write-Host $receipt
Write-Host "Receipt written to $receiptPath"
if ($status -eq "ATTESTED") { exit 0 } else { exit 1 }
