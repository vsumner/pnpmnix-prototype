# Packaged artifact qualification

The source-only prototype was copied to a separate directory and exercised there with an external retained run directory. The program commands were:

```sh
python3 run.py
python3 run.py --full
```

Testing used Apple Silicon macOS and an existing Nix 2.35.2 client/daemon. The declared toolchain was obtained from the official Nix cache and public fixed-output inputs. This is **fresh-location qualification, not a clean-host test**: the full example reused previously realized registry archives. Every missing archive/tool has a declared URL/hash or pinned Nixpkgs derivation; no personal path or existing store object is named as a required input.

## Checked

- Real React cold/warm offline frozen installs: one cold extraction, zero warm extractions, correct runtime/package version, unchanged frozen inputs, internal links, network EPERM and zero lifecycle events in both output streams.
- Missing map/file and changed compressed-byte inputs rejected. The corruption preserves decompressed gzip payload, so the rejection tests exact archive integrity. pnpm's retry behavior makes that control relatively slow.
- Full Vite native execution, platform packages, three patches, three selected peer/workspace resolutions, build, 26 assertions and four restore-corruption/topology controls passed; 313 original source hashes remained unchanged.
- All 1,301 archive bytes (1,266,326,171 bytes) were rehashed in 32 groups. Actual Nix queries found every group reference-free and the aggregate referencing exactly 32 groups, with 33 closure members including itself.
- Final source/data files matched the tested fresh copy. The final normal entry point passed in both modes; warm invocations rebuilt nothing. Optimized Python was rejected before tool access/output creation.

The first smoke run took 103.80 s including declared toolchain/input acquisition and the corruption retry. The full native build took 96.16 s after the toolchain was available. Final warm entry checks took 0.54 s for smoke and 0.86 s for full, reading retained successful receipts rather than rerunning their tests. These are single local observations, not benchmarks. Minimum sampled free space across guarded phases was 69.46 GiB. Sandbox=true/fallback=false, max-jobs=4 and the 12 GiB polling guard were retained.

Packaging corrections were retested: a tool-referencing shell script now uses a declared `writeText` derivation; receipt selection distinguishes full results from negative-control results; final pass status is written after receipt verification; and the entry point rejects Python optimization. No frozen-project semantics were broadened.

## Limits

Other machines, Linux/Intel macOS, arbitrary lockfiles, authenticated sources, actual registry maintenance commands, full browser/socket-service behavior and native built-output sharing remain unqualified. Restore requires explicit `--ignore-scripts` plus assigned root hooks; ordinary hook replay is unresolved. Peer checks are representative. Whole-output bit reproducibility and hard daemon cancellation are unproved. The earlier 3,584-input work qualified archive fan-in and bounded changes, not an exhaustive pnpm dependency graph.

Detailed machine logs/receipts remain outside this publication candidate. Independent source, privacy, license and retained-receipt review returned a qualified pass with no unresolved actionable findings. Its direct daemon queries were denied; group-reference claims rely on the primary runtime audit. The review did not establish clean-host behavior or hard daemon cancellation. No generated Vitest token contents were read.

## Local command-flow qualification

The local prepare → restore → stock pnpm implementation was qualified on the same Apple Silicon Mac with pinned pnpm 12.6.0, Node 24.18.0 and Nix 2.35.2. No new platform or arbitrary-project support is claimed.

- `python3 tests/flow-check.py --artifacts <fresh external directory>` passed 33 focused gates from current source, including strict Nix A/B/C fixture preparation, exact prepared payload reuse, pending versus explicit checkout hooks, real runtime/peers/patch/native bins, inherited private store configuration, stock add/update/remove, automatic source-return refresh, new workspace discovery/bin/peer/scripts, matching removed-workspace cleanup and C return, mismatch/corruption rejection, failed/caught/abrupt activation recovery, immutable/sibling isolation, and permanent scope/ownership regressions.
- A separate private clone of existing fixture commits exercised actual Git A → B → A switches, native automatic refresh, matching restores, and the branch-local hook. No new commits were created.
- `python3 pnpmnix.py prepare --profile vite --output <fresh external directory>` and host restore with `--run-checkout-hooks` passed. Stock Vite build and esbuild/lightningcss/unrs-resolver behavior passed in the private restored environment. The 313 declared source inputs and source-owned fixture dependency directory remained unchanged.
- `python3 run.py` passed its retained smoke/negative receipts. `python3 run.py --full` passed with a newly realized consumer, including Vite build, three patches, representative peers/platform packages, 26 assertions and 313 unchanged source hashes. Strict sandbox socket diagnostics remain a limitation.
- A fresh independent GPT-6.1 Sol review found four actionable boundary bugs, all corrected with permanent regressions: external Git hooks symlink, compact `-C` scope override, pnpmfile execution before rejection, and late unowned dependency-directory takeover. Independent abrupt-exit controls passed at all six physical dependency moves. Final review found no remaining blocking findings.

Private machine paths, generated markers, logs, stores, checkouts and detailed receipts remain outside this source. The original qualification limitations above describe the original frozen consumer; the new fixture qualifies only the explicit command-flow cases listed here. Preparation is restricted to the reviewed profiles. Ordinary native scripts can replay, checkout effects are not transactionally undone, arbitrary lifecycle/native compilation/browser/socket behavior remains unqualified, and injected interruption tests do not prove real power-loss or disk-exhaustion recovery. Source `/usr/bin/env` bin headers are retained: their bodies are checked with declared Node in Nix and direct execution is checked on the host.

## Separate ARM64 Linux Hono core qualification

The [Linux Hono path](linux-hono/README.md) records a reviewed four-pair core qualification against public Hono `08a023cbfde55b434fb0fb30fae35d42e4bf20aa`, using pnpm 12.6.0, Node 24.18.0 and Nix 2.35.2 in an isolated ARM64 Ubuntu guest. See [the pathless summary](linux-hono/QUALIFICATION.json). Stock baseline, strict preparation, fresh ordinary-copy restore, paired native/wrapped workspace/dependency/root-bin additions and original-source return/restore passed. Five root runs each passed 5,196 tests with 44 skipped; five service-worker runs each passed five tests.

The source is integrated as a separate entry point and does not alter Darwin runtime/build scripts. Publication checks compare its immutable preparation plan with the tested plan and reuse retained prepared inputs for bounded live command checks; they do not repeat the full four-pair experiment or claim a clean host. Actual publication checks and review are documented in the Linux path. Frozen experiment B, x86_64, all external Hono runtimes, lifecycle-metadata parity, generic Linux support, performance and daemon-cancellation guarantees remain unqualified.
