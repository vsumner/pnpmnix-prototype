# pnpmnix prototype

A small, frozen example of Nix-owned archive acquisition followed by native pnpm offline materialization, with a local prepare → restore → stock pnpm command flow. Native pnpm owns package-store indexes, dependency graphs, peers, patches, platform selection and linking. This prototype does not implement another package manager.

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

## Prepare → restore → stock pnpm

`run.py` and `run.py --full` remain qualification tools. `pnpmnix.py` is the usable command flow for the reviewed profiles. A small workspace example, using fresh paths:

```sh
python3 pnpmnix.py prepare --profile fixture-a --output /tmp/pnpmnix-prepared-a
mkdir /tmp/pnpmnix-dev
cp -R tests/fixtures/a/. /tmp/pnpmnix-dev/
git -C /tmp/pnpmnix-dev init
python3 pnpmnix.py restore --prepared /tmp/pnpmnix-prepared-a/prepared.json \
  --checkout /tmp/pnpmnix-dev --state /tmp/pnpmnix-state --run-checkout-hooks
python3 pnpmnix.py pnpm --checkout /tmp/pnpmnix-dev --state /tmp/pnpmnix-state \
  --offline -- run test
python3 pnpmnix.py pnpm --checkout /tmp/pnpmnix-dev --state /tmp/pnpmnix-state \
  -- --filter @maintenance/app add picocolors@1.1.1 --save-exact
```

`prepare --profile vite` uses the original frozen Vite inputs and prints its source path. Restore into a writable checkout at the pinned Vite revision listed below, with matching manifests, complete lockfile stream, workspace configuration, patches and declared source/hook inputs. The `fixture-a`, `fixture-b` and `fixture-c` profiles are qualification examples: A has semver 6, B semver 7, and C adds a workspace with a peer, script and bin. These are the only preparation inputs accepted by the CLI. Arbitrary lockfile inventory generation remains unsupported.

Preparation produces an immutable Nix environment and a local `prepared.json` handle. It seals exact dependency/store inventories, explicit input hashes, native project discovery, platform/tool bytes and the checkout hook plan. A changed preparation identity needs a matching reviewed profile; ordinary development edits can continue with stock pnpm without preparing again. Unrelated source files and edits are preserved during restore. A source-owned workspace dependency directory is preserved only when the frozen source and prepared subtree are identical; mixed source/generated directories are rejected.

Restore verifies inputs and configuration before invoking native discovery, checks both immutable trees, copies to private writable inodes, and verifies the copies. It replaces only owned root/workspace dependency directories, including directories remembered from removed workspaces. First restore requires those generated directories to be absent. An existing unowned `node_modules`, redirected Git hook, changed hook owned outside the flow, or unsupported configuration fails safely. Empty obsolete workspace directories are removed only after their owned generated trees have been retained outside the checkout.

Stock relocation to a new private store can reimport raw package files. Preparation records the regular package payload changes made by header adaptation and approved builds; restore reapplies those exact bytes after native linking and verifies the complete resulting dependency tree. pnpm still writes its own graph, workspace paths and private store metadata. No package-store index or build-completion flag is forged. Mutable pnpm operations retain an inherited `PNPM_CONFIG_STORE_DIR`, private data/home/config/cache paths, copy imports and empty auth configuration, including for automatic install children. The stock wrapper rejects global operations, alternate roots/stores, pnpmfile composition and managed configuration overrides. Use its `--offline` flag before `--` to make offline intent persist into children; available metadata and payloads are still required.

Restore's linking install explicitly uses `--ignore-scripts`. Its default result says **checkout hooks pending**. `--run-checkout-hooks` runs only the profile's assigned root/workspace hooks and verifies the executable checkout Git hook before reporting completion. It requires a normal Git checkout; Git worktree indirection and custom `core.hooksPath` are unsupported. For Vite, the original preinstall body is executed explicitly because this pnpm version no-ops its only-allow script, followed by the root postinstall hook. The fixture runs root preinstall/postinstall and lib postinstall; C also runs the new workspace postinstall. Browser downloads and denied dependency hooks remain deferred. The source workspace bin retains its original `/usr/bin/env node` header: strict Nix preparation checks its body with declared Node, and host qualification checks direct bin execution.

Ordinary stock pnpm maintenance uses scripts enabled unless the caller explicitly requests otherwise. Dependency/root/workspace hooks can replay; the wrapper does not claim their completion after an arbitrary stock command. Those development commands run outside the Nix build sandbox and own their normal mutable effects. Inactive virtual-store package versions are harmless. Matching restore provides clean generated layout and approved payload reuse; stock workspace removal alone is not promised to clean every dangling bin or orphan directory.

A checkout has one private state directory and an owned `.pnpmnix-state.json` binding/lock file. That generated marker contains a local path: keep it out of commits and public bundles. Do not move or hand-edit the state/marker. Restore journals directory moves and publishes `active.json` only after verification. Ordinary errors and caught interruption roll back dependency trees, retaining failed/staged trees and all previous artifacts. After an abrupt process exit, stock commands stop until recovery:

```sh
python3 pnpmnix.py recover --checkout /tmp/pnpmnix-dev --state /tmp/pnpmnix-state
```

Recovery restores the previous dependencies. Checkout hooks or arbitrary script effects are not transactionally undone and may need repair after a hook failure. Locking excludes concurrent wrapper operations; other tools must not write the checkout during activation. No power-loss or real disk-exhaustion guarantee is claimed. Every attempt and previous private store is retained; this command performs no GC or automatic artifact cleanup.

Run the focused flow checks with a fresh external artifact directory:

```sh
python3 tests/flow-check.py --artifacts /tmp/pnpmnix-flow-check
```

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

The full qualification consumer makes a full writable private copy. It uses an explicit `--ignore-scripts` frozen offline install to relocate pnpm's own metadata, then separately runs the assigned root hook bodies. **Ordinary pnpm install can replay dependency hooks after relocation.** Transparent ordinary-install reuse is not claimed. No pnpm store/index writer is reimplemented and no completion flags are forged.

The CommonJS adapter is experimental and specific to the tested native pnpm API/version. The Darwin Node launcher sets public `NODE_PATH` before exec for generated command context; it is not a general module-resolution guarantee. Header adaptation and this launcher need separate platform qualification. Registry payload bodies and original source configuration remain checked. Copies, symlinks and metadata are verified; cross-machine native built-output sharing and hardlink/APFS-copy optimization are not implemented.

## Stable groups and costs

`scripts/stable-groups.py` hashes full package IDs and splits a binary prefix only above 64 archives. Group IDs and sorted membership require no saved assignment state. Splits/merges affect the local prefix subtree. A version update can affect two groups. The map is asserted to cover the exact inventory once, with no empty or oversized groups.

Previous bounded synthetic qualification used 3,584 distinct small archives. Stable grouping used 75 groups versus 56 contiguous groups. An early addition required one stable group rather than 57 contiguous groups; observed group-phase times were 1.10 s and 12.24 s. Sequential shared-cache ordering matters: removal reused a group from the preceding update, and later overflow reused most groups from the preceding addition. These are single observations with tiny payloads, not a general throughput or full dependency-graph benchmark. The source bundle contains no measured-machine logs or stores.

Full checkout copying, verification, native preparation, cold per-archive Nix overhead and extra stable-group count remain costs. The prototype provides a boundary for evaluation, not a blanket speed claim. See `VERIFICATION.md` for the final packaged artifact's tested commands and qualifications.

## Remaining integration work

Qualify another machine/platform and Nix setup; define arbitrary-project inventory generation and configuration composition; qualify standalone prune and arbitrary lifecycle behavior; qualify native-output sharing across environments; and run full browser/socket-service behavior. The command flow qualifies stock add/update/remove and workspace/source return in its small fixture; ordinary hook replay remains an explicit native behavior. The small fixture does not establish a 3,584-package pnpm semantic graph. Whole-output bit reproducibility is not claimed because experiment receipts contain timestamps and timings.

No repository creation, commit, push or publication is part of running this source. Public distribution should include only these reviewed source/data/license files, never generated artifacts, downloaded inputs, stores, executables, logs or credentials. See `LICENSE` and `THIRD-PARTY-NOTICES.md`.
