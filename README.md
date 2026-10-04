# pnpmnix prototype

A small, frozen example of Nix-owned archive acquisition followed by native pnpm offline materialization. Native pnpm owns package-store indexes, dependency graphs, peers, patches, platform selection and linking. This prototype does not implement another package manager.

## Run

From a copy of this source directory:

```sh
python3 run.py
```

The default smoke run fetches one pinned real React archive, verifies its exact SHA512 bytes through a reference-free group, and exercises cold then warm native pnpm offline frozen installs. It also rejects missing-map, missing-file and altered-compressed-byte inputs. The warm install must perform no native archive extraction. Both pnpm event streams are checked for lifecycle activity. Stable mapping checks run before the build.

For the full frozen public Vite example:

```sh
python3 run.py --full
```

The full run acquires 1,301 pinned archives in 32 stable groups, creates a fresh pnpm store offline, prepares a private dependency tree, restores it to another checkout, and checks native execution, platform packages, three patches, three representative peer/workspace resolutions, the Vite build and 26 focused assertions. The entry point prints the output paths and a separate retained artifact directory. Run logs and receipts stay outside this source bundle. Keep them private unless you review their generated paths and data.

## Requirements and pins

- Apple Silicon macOS (`aarch64-darwin`). Linux, Intel macOS and other machines are untested and rejected by the entry point.
- An existing Nix 2.35.2 client **and running daemon**. The command checks both; it does not install or update Nix.
- Bootstrap Python 3.9 or later. Build-time Python, Node, pnpm, Git, compiler and SDK come from declared Nix inputs.
- More than 12 GiB free on both the output and Nix-store volumes before starting. A polling guard stops the client at 12 GiB, above a 10 GiB reserve. Cold toolchain/dependency acquisition can need additional space; allow several GiB beyond that margin. A polling guard cannot guarantee immediate daemon cancellation.
- Network access for the pinned Nixpkgs source, official Nix binary-cache inputs and fixed-output public archive fetches. Ordinary pnpm/build derivations run in a strict sandbox and prove network denial. Archive acquisition is the network phase.

`pins.json` contains exact public URLs, source revision/NAR hash, and archive integrity hashes. It pins pnpm 12.6.0 and Vite revision `10033218d239c927cdc375970b5741cce408e81b`. The Nixpkgs snapshot declares Node 24.18.0, Python 3.13.12, Git 2.51.2, Clang 21.1.7 and SDK 14.4. No channel or personal store path is an input. Tools can be obtained from the official Nix binary cache; otherwise Nix may build their declared derivations.

Every invocation sets sandbox=true, sandbox-fallback=false, max-jobs=4 and no remote builders. It enables per-command substitutions from `https://cache.nixos.org`; it does not change global configuration, profiles or credentials. Project builders remain local. The one-hour bound and free-space guard retain failed outputs/logs for diagnosis and perform no cleanup.

## What is supported

This is a reproducible **frozen example**, not an arbitrary-project CLI. `data/` contains a frozen archive inventory, stable map, public Vite input hashes and captured configuration. Native pnpm reads the unmodified source lockfile; this wrapper does not regenerate inventories from other lockfiles.

- The captured pnpm lockfile format is 9.0, in a two-document YAML stream. The engine is pnpm 12.6.0. Other engine versions or lockfile formats are unqualified.
- Registry tarballs require the declared URL and SHA512 integrity. The custom fetcher checks those against the map, then delegates extraction and CAFS writing to pnpm's public native `localTarball` fetcher.
- Captured relative `file:` directories and workspace links are resolved from the fetched public checkout. Directory fetches are delegated to native pnpm after checking the declared inventory. Undeclared source types/maps fail closed.
- Frozen manifests, workspace configuration, patches and 313 source-input hashes remain unchanged. Global virtual store is disabled; package import uses copies; store-integrity verification is enabled. The acquisition install ignores scripts and disables side-effect caches. Later preparation reads the immutable acquired store with `--frozen-store`.
- Peer, optional-platform, workspace and patch semantics stay with pnpm. The full example checks representative peers, target platform packages and three patches; it does not establish exhaustive graph equivalence.

Git dependencies, arbitrary URLs, local tarballs, authenticated/private registries, custom pnpmfile composition, alternative registries and general lockfile-to-inventory conversion are not supported entry paths. Changing the captured example needs a new inventory/configuration review and qualification.

## Lifecycle and filesystem contract

Archive acquisition, environment preparation and running scripts are separate phases. Scripts come from manifests and their environment, rather than directly from a lockfile.

Acquisition runs offline with `--ignore-scripts`. Preparation executes the captured root preinstall body with pnpm identity, installs offline without scripts, adapts interpreter headers only on detached package files, and invokes native pending rebuild under the captured allow/deny policy. Browser downloads remain deferred by the example's environment. Approved dependency hooks execute during preparation; denied hooks stay pending.

Restore makes a full writable private copy. It uses an explicit `--ignore-scripts` frozen offline install to relocate pnpm's own metadata, then separately runs the assigned root hook bodies. **Ordinary pnpm install can replay dependency hooks after relocation.** Transparent ordinary-install reuse is not claimed. No pnpm store/index writer is reimplemented and no completion flags are forged.

The CommonJS adapter is experimental and specific to the tested native pnpm API/version. The Darwin Node launcher sets public `NODE_PATH` before exec for generated command context; it is not a general module-resolution guarantee. Header adaptation and this launcher need separate platform qualification. Registry payload bodies and original source configuration remain checked. Copies, symlinks and metadata are verified; cross-machine native built-output sharing and hardlink/APFS-copy optimization are not implemented.

## Stable groups and costs

`scripts/stable-groups.py` hashes full package IDs and splits a binary prefix only above 64 archives. Group IDs and sorted membership require no saved assignment state. Splits/merges affect the local prefix subtree. A version update can affect two groups. The map is asserted to cover the exact inventory once, with no empty or oversized groups.

Previous bounded synthetic qualification used 3,584 distinct small archives. Stable grouping used 75 groups versus 56 contiguous groups. An early addition required one stable group rather than 57 contiguous groups; observed group-phase times were 1.10 s and 12.24 s. Sequential shared-cache ordering matters: removal reused a group from the preceding update, and later overflow reused most groups from the preceding addition. These are single observations with tiny payloads, not a general throughput or full dependency-graph benchmark. The source bundle contains no measured-machine logs or stores.

Full checkout copying, verification, native preparation, cold per-archive Nix overhead and extra stable-group count remain costs. The prototype provides a boundary for evaluation, not a blanket speed claim. See `VERIFICATION.md` for the final packaged artifact's tested commands and qualifications.

## Remaining integration work

Qualify another machine/platform and Nix setup; define arbitrary-project inventory generation and configuration composition; test actual add/update/remove/prune commands and their registry resolution; resolve ordinary hook replay; qualify native-output sharing across environments; and run full browser/socket-service behavior. The small fixture does not establish a 3,584-package pnpm semantic graph. Whole-output bit reproducibility is not claimed because experiment receipts contain timestamps and timings.

No repository creation, commit, push or publication is part of running this source. Public distribution should include only these reviewed source/data/license files, never generated artifacts, downloaded inputs, stores, executables, logs or credentials. See `LICENSE` and `THIRD-PARTY-NOTICES.md`.
