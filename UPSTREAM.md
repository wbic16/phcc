# UPSTREAM.md — the sealed upstream carry

`upstream.phext.xz`, at this repository's root beside `phcc.phext.xz`,
is a sealed phext carry of the **pristine upstream TinyCC source** at
phcc's current base pin — the exact tree this fork diverged from,
held byte-exact so the divergence recorded in PATCHES.md is always
measurable against the original. Will's direction, 2026-11-09:
"keep the upstream source sealed in a phext.xz."

## The pin

- Upstream: https://github.com/TinyCC/tinycc.git (branch `mob`)
- Commit: `70adbb129760b77e3bdfec447c1f986def763f2c`
- Date: 2026-11-07T14:43:30+03:00
- Subject: "arm64: fix sp offsets of 4096 and more in arm64_spoff"
  (Alexander Medvednikov; the fork's cherry-pick is PATCHES.md entry U1)

## Lineage

- The fork began from a **2022-04-01 upstream snapshot**, plus four
  fork commits written in April 2024. That pre-rebase history is
  preserved on branch `emise/pre-slice0-2026-11-07`.
- The modernization rebase (Slice 0) moved the base to
  `c638ddfb593214813aa33536fb993b9a45d23793` — upstream **0.9.28rc**.
- Upstream sync #1 (PATCHES.md **U1**, 2026-11-08) advanced the base
  pin by exactly one upstream commit to **70adbb12**, the pin this
  carry seals. Upstream drift checks at every wave boundary since
  have found upstream still at this commit.

## The carry (file grain, tools/upstream_carry.py)

- **558 files, 4,557,444 bytes**, every file placed as one scroll
  with a placement manifest inside the phext (path, coordinate,
  SHA-256 of the original bytes, size, git mode, encoding).
- **Binary scrolls: none.** Every file in the pinned tree is valid
  UTF-8 containing no phext delimiter byte, so all 558 files are
  carried as raw text scrolls; the canonical `phext-binary:1:base64`
  form (libphext 0.5.0) stands ready in the carry tool for any
  future pin that needs it.
- 0 symlinks, 9 empty files, 0 gitlinks (the phext's exclusions
  register records that the pinned tree has no gitlinks).

## Hashes

- `upstream.phext` (plain; **does not ship** — generated on demand):
  4,631,003 bytes,
  SHA-256 `54d69d4b2bd056e9438746c5fdc8f65e8e85b4f3be13be559acb3ad9f9586a5a`
- `upstream.phext.xz` (the seal; **ships**): 798,620 bytes,
  SHA-256 `5e98c6d163430874c9287ff101a964149b4e142a3a12a962604b54d439d3eec8`
- Seal recipe: the repository's own `phcc seal`
  (tools/phcc_builds.py — xz stream, CRC64 check, preset 9 extreme),
  the same recipe that seals phcc.phext.

## Regeneration

```sh
git clone https://github.com/TinyCC/tinycc.git tinycc-upstream
git -C tinycc-upstream checkout 70adbb129760b77e3bdfec447c1f986def763f2c
python3 tools/upstream_carry.py build --repo tinycc-upstream \
    --pin 70adbb129760b77e3bdfec447c1f986def763f2c \
    --out upstream.phext --stats upstream-stats.json
python3 tools/phcc seal --phext upstream.phext --out upstream.phext.xz
```

## Verification (re-runnable)

```sh
python3 tools/phcc unseal --sealed upstream.phext.xz --out upstream-check.phext
# upstream-check.phext must hash to the plain SHA-256 above
python3 tools/upstream_carry.py unpack --phext upstream-check.phext \
    --out upstream-check-tree
# unpack re-verifies every file's SHA-256 against the manifest
```

Measured at the carry's creation (2026-11-09, rock-mountain):
unseal reproduces the plain phext byte-identically; unpack writes
**558/558 files, every file SHA-256-verified, 0 failures**; an
independent `diff -r` of the unpacked tree against a second fresh
checkout of the pin shows **0 differences**, and executable-bit
parity is exact (6 files at mode 100755 in both trees).
