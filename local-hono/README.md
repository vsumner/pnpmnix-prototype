# Task-local Hono qualification profiles

This isolated branch extends published prototype commit `6631d7ab2b2811134e72d1d79a3f7154170ec46b` for one second real workspace. It does not add arbitrary-project inventory generation or a generic package-manager framework.

`hono` pins official [Hono](https://github.com/honojs/hono/tree/08a023cbfde55b434fb0fb30fae35d42e4bf20aa) revision `08a023cbfde55b434fb0fb30fae35d42e4bf20aa`. The original project already declares pnpm 12.6.0 and supports the existing declared Node 24.18.0. Its nine configured projects include eight HTTP/runtime adapters with `workspace:*` development links and Hono peers. The complete two-document v9 lock stream contains 1,085 exact registry records. Source/archive pins, all 585 regular source-input hashes, catalog and bounded groups are explicit static review data. All original source/configuration bytes remain unchanged.

Changesets was considered but declares pnpm 11.13.1 and additional trust/shell semantics. Consola declares pnpm 10.6.3 and has no workspace file. Hono permits the existing engine without an upgrade and tests a server framework and runtime adapters rather than Vite's tool/fixture workspace. A read-only official OpenClaw metadata reference pinned at `bb5656bf89e230bb3d6c9040b1e9b86df0306439` has 188 main-document workspace importers and 1,725 registry records; Hono has nine and 1,085. No OpenClaw install or build was repeated.

`hono-experiment` adds only the reviewed `adapters/pnpmnix-probe` source files and the lockfile produced by stock pnpm adding picocolors 1.1.1 to that workspace. It has 588 exact input hashes and shares the unchanged acquisition/catalog. The root manifest and existing eight importers are unchanged. Its source executable is tested with filtered `exec ./bin.cjs`. Separate paired native/wrapped maintenance checks also qualify a new Hono-peer workspace and a root consumer of this workspace, including normal builds, root/adapter tests, peer imports and the installed root workspace bin.

Both profiles retain default stock cmd shims. Their empty checkout-hook plans require no Git hook creation. Restore now identifies configuration from actual native workspace membership and consumed configuration. Non-workspace `dist` manifests remain ordinary build outputs and are preserved, including changed output bytes; no Hono-specific exception remains. Declared source/build inputs, actual workspace manifests and consumed configuration still require an exact frozen match. Auth/executable configuration is checked before hooks can load.

Run with fresh artifact paths:

```sh
python3 pnpmnix.py prepare --profile hono --output /tmp/hono-prepared
python3 pnpmnix.py restore --prepared /tmp/hono-prepared/prepared.json \
  --checkout /path/to/pinned-hono-checkout --state /tmp/hono-state --run-checkout-hooks
python3 pnpmnix.py pnpm --checkout /path/to/pinned-hono-checkout \
  --state /tmp/hono-state --offline -- run build
python3 pnpmnix.py pnpm --checkout /path/to/pinned-hono-checkout \
  --state /tmp/hono-state --offline -- run test
```

The baseline and restored host both pass the normal frozen install/build/root tests: 145 files, 5,196 tests passed, 44 skipped; service-worker adapter tests pass five assertions. Nix preparation proves network EPERM, native offline ingestion, original denied-build policy and a native rolldown build through declared Node. Normal complete project build/tests and default bins are qualified on the host. No Linux, other-runtime, general lifecycle or performance claim follows.

## Native maintenance and prepared identity

The earlier wrapper failed after native pnpm successfully wrote `minimumReleaseAgeExclude: [hono@4.13.13]` during two additions: a new Hono-peer workspace and a root workspace consumer. The simplified boundary preserves native results and reports that the prepared identity needs refresh. Paired checks produce identical source changes and dependency layouts under the same private settings. It does not classify native versus manual release-age exclusion changes; pnpm owns that mutable setting. Build permissions, trust/primary minimum-age controls, registry/access and managed private/tool scope remain reviewed preflight decisions. Existing exact original and filtered experiment profiles remain the frozen restore inputs; a policy-changing branch needs its own reviewed preparation before frozen restore. After the peer addition, an offline normal build failed in the native control because policy validation needed uncached registry metadata; the normal online build passes in both zones, with warmed task-private metadata reused by ordinary copies.

The prepared native metadata retains seven denied pending-build IDs (four esbuild versions, msw, sharp, workerd), whereas the normal baseline has no pending IDs. Dependency linking explicitly ignores scripts, and no completion flags are forged. The empty checkout-hook plan does not imply dependency lifecycle parity. Stock commands may replay allowed scripts and retain inactive cache entries; matching restore supplies the clean reviewed layout.

The first all-archive direct acquisition exceeded Darwin's sandbox data-size limit. The existing verified archive-group mechanism corrected that input shape: 26 groups, at most 62 records each, with every compressed SHA512 verified. Strict sandboxing, fallback disabled, max-jobs 4 and the 12 GiB guard remain. A changed branch identity requires its matching exact reviewed profile.

Hono is MIT licensed; its pinned notice is retained in [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md). Source is acquired from the exact official public archive. These exact qualification profiles do not establish arbitrary-project support.
