"""Create a fresh pnpm-owned store from declared Nix archives, offline."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir()
project = Path(os.environ['TMPDIR']) / 'cold-vite-checkout'
shutil.copytree(spec['source'], project, symlinks=True)
for p in [project, *project.rglob('*')]:
    if not p.is_symlink(): p.chmod(p.stat().st_mode | 0o200)
store = out / 'store'; assert not store.exists()
assert not (project / 'node_modules/.pnpm').exists(), 'no preinstalled root dependency tree'
assert not any(project.glob('.pnpmfile*')), 'source pnpmfile requires explicit composition'
map_path = Path(spec['acquisition']) / 'archive-map.json'
trace = out / 'fetch-trace.jsonl'; trace.write_text('')
for key, value in {'ENABLE_GLOBAL_VIRTUAL_STORE': 'false', 'SCRIPT_SHELL': spec['bash'],
    'PREFER_SYMLINKED_EXECUTABLES': 'true', 'STORE_DIR': str(store), 'OFFLINE': 'true',
    'TRUST_LOCKFILE': 'true', 'VERIFY_STORE_INTEGRITY': 'true', 'PACKAGE_IMPORT_METHOD': 'copy',
    'SIDE_EFFECTS_CACHE': 'false', 'IGNORE_SCRIPTS': 'true', 'PNPMFILE': spec['adapter']}.items():
    os.environ['PNPM_CONFIG_' + key] = value
os.environ['VITE_RAW_ARCHIVE_MAP'] = str(map_path); os.environ['VITE_RAW_FETCH_TRACE'] = str(trace)
os.environ['VITE_LOCKED_SOURCE_INVENTORY'] = spec['source_inventory']
stages = []
def guard():
    assert all(hashlib.sha256((project / rel).read_bytes()).hexdigest() == value for rel,value in spec['source_hashes'].items()), 'original source input changed'
    return len(spec['source_hashes'])
def run(label, command, timeout=600):
    started = time.monotonic(); p = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=timeout)
    (out / (label + '.stdout')).write_text(p.stdout); (out / (label + '.stderr')).write_text(p.stderr)
    stages.append({'stage': label, 'command': command, 'exit': p.returncode, 'seconds': time.monotonic() - started})
    (out / 'stages.json').write_text(json.dumps(stages, indent=2) + '\n')
    print(json.dumps(stages[-1]), flush=True); print(p.stdout, end='', flush=True); print(p.stderr, end='', file=sys.stderr, flush=True)
    assert p.returncode == 0, label + ' failed'; return p.stdout + '\n' + p.stderr
guard(); started = time.monotonic()
network = run('network-denial', [spec['node'], '-e', "const s=require('node:net').connect(443,'1.1.1.1');s.on('error',e=>{console.log(e.code);process.exit(e.code==='EPERM'?0:1)});s.on('connect',()=>process.exit(2));setTimeout(()=>process.exit(3),2000)"])
assert 'EPERM' in network
profile = json.loads(run('effective-config', [spec['pnpm'], 'config', 'list', '--json']))
expected = json.loads(Path(spec['baseline_config']).read_text())
expected['patchedDependencies'] = {key: str(project / 'patches' / Path(value).name) for key,value in expected['patchedDependencies'].items()}
assert all(profile.get(k) == v for k,v in expected.items() if k != 'userAgent'), 'source configuration changed'
for key,value in {'enableGlobalVirtualStore': False,'packageImportMethod': 'copy','sideEffectsCache': False,'ignoreScripts': True,'offline': True,'storeDir': str(store),'pnpmfile': spec['adapter']}.items():
    assert profile.get(key) == value, key
(out / 'effective-config.json').write_text(json.dumps(profile, indent=2) + '\n')
text = run('cold-offline-install', [spec['pnpm'], '--store-dir', str(store), 'install', '--recursive', '--offline', '--frozen-lockfile', '--trust-lockfile', '--ignore-scripts', '--reporter=ndjson'])
events = []
for line in text.splitlines():
    try: event = json.loads(line)
    except ValueError: continue
    if isinstance(event,dict): events.append(event)
assert any(e.get('name') == 'pnpm:execution-time' for e in events), 'reporter positive control'
assert not any(e.get('name') == 'pnpm:lifecycle' for e in events), 'scripts executed during raw materialization'
assert guard() == 313
records = [json.loads(line) for line in trace.read_text().splitlines()]
begins = [r for r in records if r['event'] == 'native-extract-start']; ends = [r for r in records if r['event'] == 'native-extract-end']
directory_delegations = [r for r in records if r['event'] == 'native-directory-delegation']
locked_directories = set(json.loads(Path(spec['source_inventory']).read_text())['directories'].values())
assert directory_delegations and all(r['directory'] in locked_directories for r in directory_delegations)
assert begins and len(begins) == len(ends), 'incomplete native archive ingestion'
archive_map = json.loads(map_path.read_text())
assert all(r['pkgId'] in archive_map and r['archive'] == archive_map[r['pkgId']]['archive'] for r in begins)
run('locked-platform-packages', [spec['node'], spec['platform_check']])
layout = json.loads((project / 'node_modules/.modules.yaml').read_text())
(out / 'initial-layout.json').write_text(json.dumps(layout, indent=2) + '\n')
logical = allocated = files = 0
for p in store.rglob('*'):
    if p.is_file() and not p.is_symlink():
        st=p.stat();logical+=st.st_size;allocated+=st.st_blocks*512;files+=1
(out / 'materialization.json').write_text(json.dumps({'passed': True,'initial_store_absent': True,
    'initial_root_virtual_store_absent': True,'source_inputs_unchanged': guard(),'network_denial':'EPERM',
    'lifecycle_events':0,'native_fetch_calls':len(ends),'unique_registry_packages':len({r['pkgId'] for r in ends}),
    'native_directory_delegations':len(directory_delegations),
    'unique_native_directory_delegations':len({r['directory'] for r in directory_delegations}),
    'store_logical_bytes':logical,'store_allocated_bytes':allocated,'store_files':files,
    'phase_seconds':time.monotonic()-started,'temporary_project':str(project),
    'source_fixture_node_modules':'five tracked fixture files preserved; no host-prepared root package store',
    'extraction_timing_note':'native callback times include hashing/extraction/CAFS and bridge; calls may overlap'},indent=2)+'\n')
print(json.dumps({'offline_store_prepared':str(store),'native_fetch_calls':len(ends),'store_bytes':logical}),flush=True)
