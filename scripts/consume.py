"""Restore one complete Vite tree and verify it independently of pnpm."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]); out.mkdir()
prepared = Path(spec['prepared']); producer = prepared / 'workspace'
project = out / 'different-checkout'
inventory = json.loads((prepared / 'inventory.json').read_text())
stages = []
start = time.monotonic()
shutil.copytree(producer, project, symlinks=True)
for p in [project, *project.rglob('*')]:
    if not p.is_symlink(): p.chmod(p.stat().st_mode | 0o200)
restore_seconds = time.monotonic() - start
assert project != producer

def verify_entry(root, rel, expected):
    p = root / rel
    if expected['type'] == 'link':
        assert p.is_symlink() and os.readlink(p) == expected['target'], 'link differs: ' + rel
        assert p.resolve(strict=True).is_relative_to(root), 'external link: ' + rel
    elif expected['type'] == 'file':
        assert p.is_file() and not p.is_symlink(), 'file missing: ' + rel
        assert hashlib.sha256(p.read_bytes()).hexdigest() == expected['sha256'], 'file corrupt: ' + rel
        assert bool(p.stat().st_mode & 0o111) == expected['executable'], 'executable bit differs: ' + rel
    else: assert p.is_dir() and not p.is_symlink(), 'directory differs: ' + rel

def verify_tree(root, exact=True, exceptions=()):
    for rel, expected in inventory.items():
        if rel not in exceptions: verify_entry(root, rel, expected)
    if exact:
        assert {str(p.relative_to(root)) for p in root.rglob('*')} == set(inventory), 'topology differs'
    for p in root.rglob('*'):
        if p.is_symlink():
            assert p.resolve(strict=True).is_relative_to(root), 'new external link: ' + str(p)
        rel = str(p.relative_to(root))
        if rel not in inventory:
            if rel == 'node_modules/.vite-temp':
                assert p.is_dir() and not any(p.iterdir()), 'unexpected Vite temp contents'
                continue
            if rel == 'node_modules/.vitest' or rel.startswith('node_modules/.vitest/'):
                assert not p.is_symlink() and (p.is_dir() or p.is_file()), 'unexpected Vitest artifact type'
                if p.is_file(): assert not p.stat().st_mode & 0o111, 'executable Vitest data artifact'
                continue
            if rel == 'packages/vite/src/node/__tests__/fixtures/file-url/node_modules':
                assert p.is_dir() and {q.name for q in p.iterdir()} <= {'.vite'}, 'unexpected fixture dependencies'
                continue
            assert any(rel == prefix or rel.startswith(prefix + '/') for prefix in
                       ['.git', 'packages/vite/dist', 'node_modules/.vite',
                        'node_modules/.pnpm-task-run-state-v1',
                        'packages/vite/src/node/__tests__/fixtures/file-url/dist',
                        'packages/vite/src/node/__tests__/fixtures/file-url/node_modules/.vite']), 'unexpected new entry: ' + rel

def producer_refs():
    needle = str(prepared).encode()
    # Generated Vitest data is validated by type/topology, never by content.
    # Validate before excluding it so an external link cannot evade the scan.
    refs = []
    for p in project.rglob('*'):
        rel = str(p.relative_to(project))
        if rel not in inventory and (rel == 'node_modules/.vitest' or
                                     rel.startswith('node_modules/.vitest/')):
            assert not p.is_symlink() and (p.is_dir() or p.is_file()), 'unexpected Vitest artifact type'
            if p.is_file(): assert not p.stat().st_mode & 0o111, 'executable Vitest data artifact'
            continue
        if p.is_file() and not p.is_symlink() and needle in p.read_bytes(): refs.append(rel)
    return refs

start = time.monotonic(); verify_tree(project)
verification_seconds = time.monotonic() - start
(out/'restore-timing.json').write_text(json.dumps({
    'restore_seconds':restore_seconds,'verification_seconds':verification_seconds,
    'method':'full shutil.copytree plus making copied files writable; symlinks retained',
    'includes':'full captured checkout and dependency tree; no APFS clone/hardlink optimization',
    'scope':'single local observation, not benchmark'},indent=2)+'\n')
for rel, row in inventory.items():
    if row['type'] == 'file':
        a = (producer / rel).stat(); b = (project / rel).stat()
        assert (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino), 'hardlinked to producer'
        assert b.st_mode & 0o200, 'consumer file not writable'
refs_before = producer_refs()
state = 'node_modules/.pnpm-workspace-state-v1.json'
assert set(refs_before) <= {state}, 'unexpected producer references before pnpm'
producer_state = json.loads((producer / state).read_text())
def verify_relocated_state():
    p = project / state
    assert p.is_file() and not p.is_symlink(), 'state is not a regular file'
    actual = json.loads(p.read_text())
    expected = {**producer_state, 'projects': {
        str(project) + k[len(str(producer)):]: v for k,v in producer_state['projects'].items()}}
    assert all(k == str(producer) or k.startswith(str(producer) + '/') for k in producer_state['projects'])
    timestamp = actual['lastValidatedTimestamp']
    assert isinstance(timestamp, int) and timestamp >= producer_state['lastValidatedTimestamp']
    expected['lastValidatedTimestamp'] = timestamp
    assert actual == expected, 'unexpected state mutation beyond project path relocation and validation timestamp'

# Real on-disk controls against the same byte/topology checks used at restore.
controls = []
native_rel = next(rel for rel in inventory if '/@esbuild/darwin-arm64/bin/esbuild' in rel)
for label, rel, operation in [('same-size-native-corruption', native_rel, 'corrupt'),
                              ('missing-required-payload', native_rel, 'missing'),
                              ('changed-root-manifest', 'package.json', 'change')]:
    p = project / rel; original = p.read_bytes(); mode = p.stat().st_mode
    if operation == 'missing': p.unlink()
    elif operation == 'corrupt': p.write_bytes(b'X' * len(original))
    else: p.write_bytes(original + b'\n')
    try:
        verify_entry(project, rel, inventory[rel])
    except AssertionError as error: controls.append({'case': label, 'rejected': True, 'reason': str(error)})
    else: raise AssertionError('bad payload accepted: ' + label)
    p.write_bytes(original); p.chmod(mode)
link_rel = 'packages/vite/node_modules/esbuild'
assert inventory[link_rel]['type'] == 'link'
p = project / link_rel; original_target = os.readlink(p)
p.unlink(); p.symlink_to(producer / link_rel)
try: verify_entry(project, link_rel, inventory[link_rel])
except AssertionError as error: controls.append({'case': 'external-producer-link', 'rejected': True, 'reason': str(error)})
else: raise AssertionError('external link accepted')
p.unlink(); p.symlink_to(original_target)
verify_tree(project)
(out / 'controls.json').write_text(json.dumps(controls, indent=2) + '\n')

for key, value in {
    'ENABLE_GLOBAL_VIRTUAL_STORE': 'false', 'SCRIPT_SHELL': spec['bash'],
    'PREFER_SYMLINKED_EXECUTABLES': 'true', 'STORE_DIR': spec['acquired'],
    'OFFLINE': 'true', 'TRUST_LOCKFILE': 'true', 'VERIFY_STORE_INTEGRITY': 'true',
    'SIDE_EFFECTS_CACHE': 'true', 'SIDE_EFFECTS_CACHE_READONLY': 'true',
    'PACKAGE_IMPORT_METHOD': 'copy',
}.items(): os.environ['PNPM_CONFIG_' + key] = value

def run(label, command, timeout=300):
    command = list(map(str, command)); start = time.monotonic()
    print(json.dumps({'stage': label, 'command': command}), flush=True)
    p = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=timeout)
    (out / (label + '.stdout')).write_text(p.stdout); (out / (label + '.stderr')).write_text(p.stderr)
    print(p.stdout, end='', flush=True); print(p.stderr, end='', file=sys.stderr, flush=True)
    stages.append({'stage': label, 'command': command, 'exit': p.returncode,
                   'seconds': round(time.monotonic() - start, 4)})
    (out / 'stages.json').write_text(json.dumps(stages, indent=2) + '\n')
    assert p.returncode == 0, label + ' failed'
    return p.stdout + '\n' + p.stderr

common = [spec['pnpm'], '--store-dir', spec['acquired'], '--frozen-store']
run('init-consumer-git', [spec['git'], 'init', '--initial-branch=experiment'])
os.environ['npm_config_user_agent'] = 'pnpm/12.6.0 npm/? node/v24.18.0 darwin arm64'
os.environ['npm_execpath'] = spec['pnpm']
run('root-preinstall-original-body', [spec['bash'], '-c', json.loads((project/'package.json').read_text())['scripts']['preinstall']])
text = run('stock-relocated-install', common + ['install', '--recursive', '--offline',
          '--frozen-lockfile', '--trust-lockfile', '--ignore-scripts', '--reporter=ndjson'])
events = []
reporter_names = []
for line in text.splitlines():
    try: row = json.loads(line)
    except json.JSONDecodeError: continue
    if not isinstance(row, dict): continue
    reporter_names.append(row.get('name'))
    if row.get('name') == 'pnpm:lifecycle': events.append(row)
for row in events:
    assert row.get('wd'), 'unclassified lifecycle event'
    wd = Path(row['wd'])
    assert wd.is_relative_to(project), 'lifecycle event outside consumer'
    assert wd == project or 'node_modules' in wd.relative_to(project).parts, 'unknown source lifecycle event'
dep_events = [row for row in events if 'node_modules' in Path(row['wd']).relative_to(project).parts]
assert not dep_events, 'dependency lifecycle hook replayed'
assert 'pnpm:execution-time' in reporter_names, 'missing NDJSON reporter positive control'
assert not producer_refs(), 'producer references retained after stock relocation'
verify_relocated_state()
layout_path = 'node_modules/.modules.yaml'
old_layout = json.loads((producer / layout_path).read_text())
new_layout = json.loads((project / layout_path).read_text())
layout_differences = {k: [old_layout.get(k), new_layout.get(k)]
                      for k in old_layout.keys() | new_layout.keys() if old_layout.get(k) != new_layout.get(k)}
assert set(layout_differences) <= {'pendingBuilds', 'ignoredBuilds'}, 'unexpected module metadata mutation'
(out/'layout-differences.json').write_text(json.dumps(layout_differences,indent=2)+'\n')
verify_tree(project, exact=False, exceptions=[state, layout_path])
run('root-postinstall-consumer', common + ['--config.verify-deps-before-run=false', 'run', 'postinstall'])
hook = project / '.git/hooks/pre-commit'
assert hook.exists() and 'pnpm exec lint-staged --concurrent false' in hook.read_text()
assert hook.stat().st_mode & 0o111

patch_checks = []
for pkg_id in json.loads((prepared / 'effective-config.json').read_text())['patchedDependencies']:
    name, version = pkg_id.rsplit('@', 1)
    matches = [p for p in (project / 'node_modules/.pnpm').iterdir()
               if p.name.startswith(name + '@' + version + '_patch_hash=')]
    assert len(matches) == 1, 'patched package layout ambiguous: ' + pkg_id
    package = matches[0] / 'node_modules' / name
    run('patch-applied-' + name, [spec['patch'], '--dry-run', '--reverse', '--batch',
        '-p1', '-d', str(package), '-i', str(project / 'patches' / (pkg_id + '.patch'))])
    patch_checks.append(pkg_id)
graph_output = run('peer-workspace-semantics', [spec['node'], spec['graph_check']])

probe = out / 'native-probe.cjs'
probe.write_text("""const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = process.cwd();
const viteReq = createRequire(path.join(root, 'packages/vite/package.json'));
const esbuild = viteReq('esbuild');
if (!esbuild.transformSync('const x: number = 1', {loader:'ts'}).code.includes('const x = 1')) throw Error('esbuild transform failed');
const css = viteReq('lightningcss').transform({filename:'test.css', code:Buffer.from('p { color: #ff0000 }'), minify:true});
if (!css.code.length) throw Error('lightningcss transform failed');
const slot = fs.readdirSync(path.join(root,'node_modules/.pnpm')).find(x=>x.startsWith('unrs-resolver@1.11.1'));
const binding = require(path.join(root,'node_modules/.pnpm',slot,'node_modules/unrs-resolver'));
const resolver = new binding.ResolverFactory({extensions:['.js']});
const expected = path.join(root,'packages/vite/package.json');
if(resolver.sync(root,'./packages/vite/package.json').path !== expected) throw Error('resolver failed');
console.log(JSON.stringify({esbuild:esbuild.version, lightningcss:true, unrs_resolver:true}));
""")
run('native-behavior', [spec['node'], probe])
run('locked-platform-packages', [spec['node'], spec['platform_check']])
workerd = project / 'node_modules/.pnpm/@cloudflare+workerd-darwin-arm64@1.20260730.1/node_modules/@cloudflare/workerd-darwin-arm64/bin/workerd'
run('workerd-native-executable', [workerd, '--version'])
run('vite-package-build', common + ['--filter', 'vite', 'run', 'build'], timeout=600)
focused = ['env', 'packages', 'resolve']
unit_output = run('focused-unit-tests', common + ['run', 'test-unit', *[
    'packages/vite/src/node/__tests__/' + name + '.spec.ts' for name in focused]], timeout=600)
clean_units = re.sub(r'\x1b\[[0-9;]*m','',unit_output)
assert re.search(r'Test Files\s+3 passed\s*\(3\)',clean_units)
assert re.search(r'Tests\s+26 passed\s*\(26\)',clean_units)
assert not producer_refs()
verify_relocated_state()
verify_tree(project, exact=False, exceptions=[state, layout_path])
final_layout_file = project / layout_path
assert final_layout_file.is_file() and not final_layout_file.is_symlink()
assert json.loads(final_layout_file.read_text()) == new_layout, 'module state changed during build/tests'
task_state = project / 'node_modules/.pnpm-task-run-state-v1'
latest = json.loads((task_state/'latest.json').read_text())
assert set(latest) == {'version', 'invocation', 'run'} and latest['version'] == 1
assert re.fullmatch('[0-9a-f]{64}',latest['invocation'])
assert re.fullmatch('[0-9a-f]{12}-[0-9]+-[0-9]+',latest['run'])
for p in task_state.iterdir():
    assert p.is_file() and not p.is_symlink(), 'unexpected task state entry'
    if p.name == 'latest.json': continue
    assert p.name == latest['invocation'] + '.' + latest['run'] + '.finished'
    assert p.stat().st_size == 0, 'finished marker is not empty'
assert {p.name for p in task_state.iterdir()} == {
    'latest.json', latest['invocation'] + '.' + latest['run'] + '.finished'}
verify_tree(producer)
for root in [project, Path(spec['source'])]:
    assert all(hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest
               for rel, digest in spec['source_hashes'].items()), 'source inputs changed'
logical = allocated = 0
for p in project.rglob('*'):
    if p.is_file() and not p.is_symlink():
        st = p.stat(); logical += st.st_size; allocated += st.st_blocks * 512
(out / 'result.json').write_text(json.dumps({'passed': True, 'pnpm': '12.6.0', 'GVS': False,
    'producer': str(producer), 'consumer': str(project), 'source_inputs_unchanged': len(spec['source_hashes']),
    'restore_seconds': restore_seconds, 'verification_seconds': verification_seconds,
    'restore_method': 'shutil.copytree: full file copy, preserved symlinks, writable private inodes',
    'consumer_logical_bytes_after_build': logical, 'consumer_allocated_bytes_after_build': allocated,
    'dependency_hook_events_on_install': len(dep_events), 'root_hook_events_on_install': events,
    'reuse_mode': 'explicit --ignore-scripts linking; root bodies assigned separately',
    'transparent_stock_install_no_replay': False,
    'normal_install_controls': 'prior frozen-source experiments replayed dependency hooks on ordinary installs; explicit ignoreScripts contract required',
    'stock_pending_builds_after_link': new_layout.get('pendingBuilds'),
    'stock_layout_differences': layout_differences,
    'focused_test_assertions_passed': 26, 'patches_reverse_dry_run_passed': patch_checks,
    'generated_vitest_artifact_metadata': [{'path': str(p.relative_to(project)),
        'type': 'directory' if p.is_dir() else 'file', 'bytes': p.stat().st_size,
        'mode': oct(p.stat().st_mode & 0o777)} for p in (project / 'node_modules/.vitest').rglob('*')],
    'peer_workspace_semantics': json.loads(graph_output),
    'socket_diagnostics': 'resolve tests log WebSocket listen EPERM under strict Nix; all 26 assertions pass, socket service unverified',
    'root_postinstall': 'explicit consumer hook installed after git init', 'producer_refs_before': refs_before,
    'producer_refs_after': [], 'controls': controls, 'focused_tests': focused,
    'browser_tests': 'unrun; upstream CI browser download opt-out retained'}, indent=2) + '\n')
print(json.dumps({'consumer_passed': str(out), 'restore_seconds': restore_seconds}), flush=True)
