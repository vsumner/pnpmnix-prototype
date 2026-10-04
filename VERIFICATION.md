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
