# Qualified ARM64 Linux Hono reuse path

This separate entry point qualifies the pinned public Hono core flow at `08a023cbfde55b434fb0fb30fae35d42e4bf20aa`, with pnpm 12.6.0, Node 24.18.0 and Nix client/daemon 2.35.2. It preserves stock configuration, default executable shims and native mutation outcomes. The original Darwin CLI/profiles/build scripts remain separate and unchanged.

The tested environment is an isolated ARM64 Ubuntu 24.04 guest, with 2 CPU, 4 GiB RAM and a 20 GiB disk. Node's heap limit is 2,048 MiB; test runs use one worker. Strict Nix sandboxing, fallback disabled, one local build job and no remote builders are required. Checkout/ordinary maintenance scripts run in the mutable guest outside Nix preparation. This path is deliberately Hono-only.

## Input reuse prerequisite

`linux-inputs.json` names **exact already acquired public Nix inputs**: pinned nixpkgs, the pinned Hono source, and 26 reference-free archive groups. Their public NAR hashes/sizes and the registry SHA512 identities are retained. These are immutable public content identities, not personal directories. No inputs, archives, binaries, OS images or package stores are bundled.

This is **input-reuse qualification**, not cold Linux acquisition or a clean-host install. Obtain/import these exact reviewed inputs through Nix's standard APIs from the prior qualified acquisition. The input verifier checks their registered NAR metadata and reference-free boundary; preparation verifies all 1,085 exact compressed registry SHA512 hashes and all 585 source hashes before use. Do not replace missing paths with arbitrary store contents, change global trust/signature settings, or silently regenerate different platform groups to make the path pass. Missing/mismatched inputs are a concrete prerequisite failure. A fresh Linux acquisition path needs separate qualification.

Print the bounded public input list, or verify existing registered inputs:

```sh
python3 linux-hono/input-paths.py
python3 linux-hono/input-paths.py --verify
```

For a standard Nix export/import, stream the listed inputs rather than keeping a second whole-set NAR spool. The receiving Nix administrator must use their existing authorized import mechanism and verify the exact pins. This adapter does not install Nix, modify daemon/security settings, or provision a VM.

## Resource contract and commands

The CLI reserves **3 GiB inside the guest**, preflights full ordinary-copy space and polls guest free space. Run it only in the isolated qualification environment with a separately monitored **host floor of at least 10 GiB**. The guest cannot enforce its host's budget. Stop before the next stage if either budget is threatened; no automatic GC, resize or old-artifact cleanup is performed. Polling is not a hard filesystem quota and does not prove remote Nix daemon cancellation after a client dies. The completed core run remained above both floors.

Use fresh preparation/artifact/state paths outside the prototype and checkout:

```sh
python3 linux-hono/pnpmnix.py prepare --profile hono --output /tmp/hono-prepared
# Create a writable checkout at the pinned Hono revision; generated node_modules must be absent.
python3 linux-hono/pnpmnix.py restore --prepared /tmp/hono-prepared/prepared.json \
  --checkout /tmp/hono-dev --state /tmp/hono-state --run-checkout-hooks
python3 linux-hono/pnpmnix.py pnpm --checkout /tmp/hono-dev --state /tmp/hono-state -- run build
python3 linux-hono/pnpmnix.py pnpm --checkout /tmp/hono-dev --state /tmp/hono-state \
  -- run test --maxWorkers=1
python3 linux-hono/pnpmnix.py pnpm --checkout /tmp/hono-dev --state /tmp/hono-state \
  -- --filter @hono/service-worker run test --maxWorkers=1
```

Only `--profile hono` is accepted. The exact Linux pnpm executable is packaged with declared Nix ELF loader/RPATH, and the existing Node caller uses GNU compilation declarations. Preparation alone uses the acquisition pnpmfile; the mutable workspace retains native pnpm linking/configuration. Default Hono shims are unchanged. Hono's reviewed checkout-hook plan is empty; `--run-checkout-hooks` completes that empty plan, and a nonempty Linux hook plan is rejected.

Native pnpm owns workspace/manifest/lock edits and automatic release-age exclusions. The wrapper preserves native stdout/stderr and exit status, appends a separate receipt and reports `prepared_state.refresh_required`. An exact matching original source/configuration/lock identity is required for original-A restore. Restoration makes ordinary private copies, replaces only owned generated roots, retains former stores/dependencies and verifies the entire prepared payload after native linking. Source-only branch checkpoints and user source files remain owned by the checkout.

## Qualification and limits

[QUALIFICATION.json](QUALIFICATION.json) is a pathless summary of the independently reviewed core experiment. Stock baseline, strict preparation, fresh restore, paired native/wrapped workspace peer + `picocolors@1.1.1` + root workspace-bin additions, and original-source branch return/restore passed. Five root runs each passed 5,196 tests with 44 skipped; five service-worker runs each passed five tests. All 17 original shims matched; 201,553 regular files across six scopes shared no cross-scope inodes. Stale workspace dependencies and installed bin disappeared on original return, an unrelated checkout file was preserved, and six negative controls rejected as expected.

The core retained four workspace/store pairs. The initial stock baseline later served as the intentional native maintenance control; its initial logs/inventories remain evidence, without claiming its final physical dependency tree was pristine. Preparation and return retain seven native denied pending-build IDs while the stock maintenance control has none. No completion flags are forged; lifecycle metadata parity is unclaimed. Normal tests produce native cache/task/timestamp changes that are recorded separately from package payload.

`tests/linux-hono-check.py` performs bounded publication/reuse checks against an existing prepared handle and active checkout; it does not repeat preparation/restore or claim the full experiment was rerun. Namespace integration is checked against the exact previously qualified immutable preparation plan. Publication integration verified unchanged Darwin runtime/build/test bytes and all six Darwin environment plus smoke/consumer identities. Linux acquisition, preparation, sealed bundle and tool identities equal the original qualification; cached preparation and all six bounded live gates passed, including five service-worker tests. No new build or dependency pair was created.

The full original experiment's receipts were independently reviewed and retained privately; generated machine paths, account configuration and logs are not part of this source bundle.

Unqualified: arbitrary projects/lock conversion/configuration composition, generic Linux support, x86_64, another toolchain/OS, frozen experiment-B preparation/restoration, all external Hono runtime suites, cross-machine native-output reuse, performance, hard disk quotas, or proven daemon cancellation. No wider capability framework is added.
