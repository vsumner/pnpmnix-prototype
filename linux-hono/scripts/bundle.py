"""Seal the declared prepared result and its mutable-store seed in a Nix output."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

spec = json.loads(Path(sys.argv[1]).read_text())
m = importlib.util.spec_from_file_location('trees', spec.pop('trees'))
trees = importlib.util.module_from_spec(m); m.loader.exec_module(trees)
sys.modules['trees'] = trees
c = importlib.util.spec_from_file_location('configuration', spec.pop('configuration_reader'))
configuration = importlib.util.module_from_spec(c); c.loader.exec_module(configuration)
out = Path(sys.argv[2]); out.mkdir()
workspace, source, store = Path(spec['prepared'])/'workspace', Path(spec['source']), Path(spec['store'])
os.environ.update(PNPM_CONFIG_MANAGE_PACKAGE_MANAGER_VERSIONS='false',
                  PNPM_CONFIG_STORE_DIR=str(store), PNPM_CONFIG_OFFLINE='true',
                  PNPM_CONFIG_SCRIPT_SHELL=spec['tools']['bash'],
                  PNPM_CONFIG_VERIFY_STORE_INTEGRITY='true',
                  PNPM_CONFIG_ENABLE_GLOBAL_VIRTUAL_STORE='false')
protected = configuration.protected_configuration(configuration.native_configuration(spec['tools']['pnpm'],source,os.environ))
for name in ['.pnpmfile.cjs','.pnpmfile.mjs']:
    trees.require(not (source/name).exists(), 'project pnpmfile composition is unsupported')
p = subprocess.run([spec['tools']['pnpm'], '--recursive', 'list', '--depth=-1', '--json'],
                   cwd=workspace, capture_output=True, text=True, check=True)
projects = sorted({str(Path(x['path']).relative_to(workspace)) for x in json.loads(p.stdout)} | {'.'})
generated = sorted('node_modules' if x == '.' else x+'/node_modules' for x in projects)
source_owned = []
for rel in generated:
    trees.relative(rel)
    if (source/rel).exists():
        trees.require(trees.inventory(source/rel) == trees.inventory(workspace/rel),
                      'mixed source/generated dependency directory unsupported: '+rel)
        source_owned.append(rel)
generated = [rel for rel in generated if rel not in source_owned]
workspace_inventory = trees.inventory(workspace)
trees.verify(workspace, workspace_inventory)
raw = json.loads((Path(spec['prepared'])/'raw-inventory.json').read_text())
payload_changes = {}
metadata = {'node_modules/.modules.yaml','node_modules/.pnpm-workspace-state-v1.json'}
for rel in raw.keys() | workspace_inventory.keys():
    if raw.get(rel) == workspace_inventory.get(rel) or rel in metadata or rel.startswith('node_modules/.pnpm-task-run-state-v1'): continue
    if not any(rel == x or rel.startswith(x+'/') for x in generated): continue
    parts = Path(rel).parts
    trees.require(len(parts) > 4 and parts[:2] == ('node_modules','.pnpm') and parts[3] == 'node_modules',
                  'unsupported prepared payload change: '+rel)
    row = workspace_inventory.get(rel)
    trees.require(row is not None and row['type'] in ('file','directory'), 'unsupported removal/link build output: '+rel)
    payload_changes[rel] = row
store_inventory = trees.inventory(store); trees.verify(store, store_inventory)
# Hashes explicitly include the complete lock stream, captured manifests, config,
# patches and hook inputs. Native pnpm discovery supplies the project set.
inputs = spec.pop('source_hashes')
for rel, sha in inputs.items():
    trees.relative(rel)
    trees.require(trees.digest(source/rel) == sha == trees.digest(workspace/rel), 'input differs: '+rel)
configuration_paths = configuration.configuration_paths(source,projects)
for rel in configuration_paths:
    trees.require(rel in inputs, 'configuration missing from explicit preparation inputs: '+rel)
spec.update(schema=2, platform='aarch64-linux', pnpm_version='12.6.0', node_version='24.18.0',
            projects=projects, generated=generated, source_owned=source_owned, inputs=inputs,
            configuration=configuration_paths, protected_configuration=protected,
            workspace_inventory=workspace_inventory, store_inventory=store_inventory, payload_changes=payload_changes,
            tool_hashes={k: trees.digest(v) for k,v in spec['tools'].items()},
            lifecycle={'dependency_builds':'approved hooks executed in Nix preparation; denied/deferred work remains pending',
                       'restore_link':'stock frozen offline ignore-scripts; no completion flags rewritten',
                       'checkout_hooks':'only the explicit reviewed hook list; optional at restore',
                       'deferred':spec.pop('deferred')})
(out/'environment.json').write_text(json.dumps(spec,sort_keys=True)+'\n')
print(json.dumps({'sealed':str(out),'projects':projects,'inputs':len(inputs)}))
