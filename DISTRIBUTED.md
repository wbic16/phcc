# Distributed compilation for phcc

Status: working prototype (2026-11-24). `dist/phccd.c` (worker),
`dist/phcc-dist.py` (driver), `dist/build-worker.sh`.

## Why

The house runs fully-distributed builds: a compile that one machine
grinds through alone is a compile the fleet should share. phcc gains
distribution as a native capability — the compiler itself is the
worker (libtcc linked in), not an external wrapper around someone
else's daemon.

## The model: wpm's rhyme

wpm already settled the trust question for packages, and the compile
protocol takes the same shape:

- **Nodes are untrusted carriers.** A worker proves nothing by
  answering; correctness comes from hashes, not from the node.
- **Identity is hash-pinned (SHA-256).** A work unit's identity is
  `SHA256("phcc-dist-v1" || compiler_id || flags || 0x00 || src)`,
  where `src` is the preprocessed translation unit and
  `compiler_id` is the SHA-256 of the exact worker/compiler build.
  The name (file, package, node) asks; the hash decides.
- **Returned objects are verified.** The worker reports the object's
  SHA-256; the driver re-hashes the bytes it received. In
  `--verify-local` mode the driver also compiles the same unit
  locally and requires byte-identity — phcc output is deterministic
  (verified: repeated compiles and preprocessed-source compiles of
  `tccpp.c` produce byte-identical objects), so byte-identity is a
  sound acceptance test, not an aspiration.
- **No silent local fallback.** A unit that cannot be distributed
  and verified fails the build *by name* — unit hash, node, cause.
  Distribution degrading quietly into a local compile would hide
  exactly the failures this design exists to surface.

## Work unit

Preprocessing happens once, on the driver (it owns the include paths
and the source tree). The unit that travels is:

- the preprocessed translation unit (the output of `phcc -E`),
- the codegen flags that remain meaningful after preprocessing
  (carried in the identity; `-D`/`-I` belong to preprocessing and are
  already baked into the bytes and the hash),
- the compiler identity it may be built by.

A worker recomputes the unit hash on receipt and rejects bytes that
do not match their claimed identity *before* compiling.

One subtlety the prototype caught: an object records the name of
the source it was compiled from (the ELF file symbol), so
byte-identity between a node object and a local object is only
well-defined if both compile the unit *under the same name*. The
canonical name is the identity itself: both the worker and the
driver's local compile name the unit `<unit_id>.i`. The object
literally carries its unit's hash as its source name.

## Transport and coordination

Prototype: length-prefixed frames over TCP on the tailnet
(`PHCH` hello / `PHCU` unit / `PHCO` object). The worker is
fork-per-connection, one unit per connection, with a disk cache
keyed by unit hash — a cache hit is safe by construction, because
the key *is* the verified identity (ABOC: always be optimizing
compiles; the cache is the first optimization and it is free).

The driver pushes units to per-node queues (one in flight per node).
That is the prototype's coordinator: deliberately minimal, in the
TinyCC spirit — small, fast, no daemon architecture. The graduation
path is peer-claim: workers pull the next unit from a shared,
phext-addressed queue (the house's existing claim pattern), so nodes
join and leave without the driver holding a roster. The wire format
does not change when the coordination does.

## Verification ladder (hardening path)

1. **Transit check (prototype, always on):** received bytes must
   hash to the worker-reported object hash.
2. **Local byte-identity (prototype, `--verify-local`):** every unit
   also compiled locally from the same preprocessed bytes; any
   mismatch fails the build by name.
3. **Redundant dispatch (next):** each unit compiled by two
   independent nodes; agreement of hashes accepts, disagreement
   names both. This replaces local verification for large builds,
   where local recompilation would defeat the purpose.
4. **Signed results (with wpm's publisher keys):** workers sign
   (unit_id, object_hash) so a result is attributable to a carrier,
   the same signature story as package publishing.

## What the prototype proved (2026-11-24, EE ~595)

- phcc builds clean on aletheia-core (2.0 s, self-hosting its lib).
  Baselines for the 10-TU core corpus (phcc's own sources,
  `-DTCC_TARGET_X86_64 -DONE_SOURCE=0`): local sequential 0.157 s,
  local parallel (-P16) 0.030 s.
- The same corpus distributed across rock-mountain, scroll-central,
  and quacked-hill: **every object byte-identical to the local
  compile of the same unit** (hash comparison, 10/10), where the
  local compile is the unit compiled under its canonical name
  (see the file-symbol note above). Code sections were verified
  identical even before name canonicalization; the only divergence
  was the recorded source name.
- Determinism control: repeated local compiles and a
  preprocessed-source compile of the same TU are byte-identical,
  which is what makes hash-acceptance sound.
- The unit cache works: a second identical run is served from the
  workers' hash-keyed caches (marked `(cache)` in driver output).
- The failure path was exercised for real: units preprocessed by a
  newer phcc snapshot were sent to workers built from an older one,
  and the build failed *by name* — unit, node, and the compiler's
  own error (`'nullptr' undeclared`) — with no local substitution.
  Compiler identity in the unit hash is what makes that skew a
  named block instead of a silent wrong object.

## What the prototype measured against itself (stated plainly)

Distribution **loses on wall-clock for this corpus**: 0.93 s of
dispatch (1.20 s end-to-end) vs 0.157 s local sequential. The cause
is measured, not guessed: the hub↔node tailnet path is relay-grade
(ping RTT avg 89 ms; connect+hello 60–165 ms), and per-unit round
trips ran 120–170 ms even warm — against ~5 ms of actual compile
per unit on loopback. phcc is so fast that per-connection latency
is the whole cost at this translation-unit size. The protocol is
proven; the transport economics are the open problem. In order,
the hardening path is:

1. **Persistent connections + batched units** — amortize the
   connection cost across a build instead of paying it per unit.
2. **Direct tailnet paths** — the relayed route is a property of
   the current tailnet, not of the design.
3. **Larger units** — distribution pays when compile time per unit
   is comparable to transport time (amalgamations, gcc-class
   workloads); tiny TUs belong on the local machine, and a future
   driver should route by unit size rather than pretend otherwise.

## Limits, stated plainly

- Preprocessed units are target- and compiler-build-specific; the
  compiler_id in the identity enforces that, at the cost of cache
  misses across compiler builds.
- The driver is Python; the graduation path is a `-dist` mode inside
  phcc proper, with preprocessing driven through libtcc.
- TCP is unauthenticated beyond the tailnet boundary and the hash
  checks; result signing (rung 4) is the fix, not yet built.
