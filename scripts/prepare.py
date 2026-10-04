"""Task-local stock pnpm preparation; no completion receipt or store rewriting."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]); out.mkdir()
project = out / 'workspace'
shutil.copytree(spec['source'], project, symlinks=True)
for p in [project, *project.rglob('*')]:
    if not p.is_symlink(): p.chmod(p.stat().st_mode | 0o200)

def guard():
    actual = {rel: hashlib.sha256((project / rel).read_bytes()).hexdigest()
              for rel in spec['source_hashes']}
    assert actual == spec['source_hashes'], 'captured source inputs changed'
    return len(actual)

def run(label, args, timeout=300):
    start = time.monotonic()
    command = list(map(str, args))
    print(json.dumps({'stage': label, 'command': command}), flush=True)
    p = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=timeout)
    (out / (label + '.stdout')).write_text(p.stdout)
    (out / (label + '.stderr')).write_text(p.stderr)
    print(p.stdout, end='', flush=True); print(p.stderr, end='', file=sys.stderr, flush=True)
    stages.append({'stage': label, 'command': command, 'exit': p.returncode,
                   'seconds': round(time.monotonic() - start, 4)})
    (out / 'stages.json').write_text(json.dumps(stages, indent=2) + '\n')
    assert p.returncode == 0, label + ' failed'
    return p.stdout

stages = []
guard()
for key, value in {
    'ENABLE_GLOBAL_VIRTUAL_STORE': 'false', 'SCRIPT_SHELL': spec['bash'],
    'PREFER_SYMLINKED_EXECUTABLES': 'true', 'STORE_DIR': spec['acquired'],
    'OFFLINE': 'true', 'TRUST_LOCKFILE': 'true', 'VERIFY_STORE_INTEGRITY': 'true',
    'SIDE_EFFECTS_CACHE': 'true', 'SIDE_EFFECTS_CACHE_READONLY': 'true',
    'PACKAGE_IMPORT_METHOD': 'copy',
}.items(): os.environ['PNPM_CONFIG_' + key] = value

profile = json.loads(run('effective-config', [spec['pnpm'], 'config', 'list', '--json']))
expected = json.loads(Path(spec['baseline_config']).read_text())
expected['patchedDependencies'] = {k: str(project / 'patches' / Path(v).name)
                                   for k, v in expected['patchedDependencies'].items()}
assert all(profile.get(k) == v for k, v in expected.items() if k != 'userAgent'), 'original policy changed'
assert profile.get('enableGlobalVirtualStore') is False
assert profile.get('preferSymlinkedExecutables') is True
assert profile.get('scriptShell') == spec['bash']
assert profile.get('packageImportMethod') == 'copy'
(out / 'effective-config.json').write_text(json.dumps(profile, indent=2) + '\n')
common = [spec['pnpm'], '--store-dir', spec['acquired'], '--frozen-store']
run('root-preinstall', common + ['--config.verify-deps-before-run=false', 'run', 'preinstall'])
# pnpm 12.6 deliberately no-ops this exact only-allow script. Execute the
# original manifest body separately with its normal pnpm identity environment.
os.environ['npm_config_user_agent'] = 'pnpm/12.6.0 npm/? node/v24.18.0 darwin arm64'
os.environ['npm_execpath'] = spec['pnpm']
root_script = json.loads((project / 'package.json').read_text())['scripts']['preinstall']
run('root-preinstall-original-body', [spec['bash'], '-c', root_script])
run('materialize', common + ['install', '--recursive', '--offline', '--frozen-lockfile',
                            '--trust-lockfile', '--ignore-scripts', '--reporter=ndjson'])

# Adapt interpreter headers only on detached, private registry files. Keep all
# bodies and original manifests/configuration byte-identical, including fixtures.
targets = {p.resolve() for p in project.rglob('*')
           if p.parent.name == '.bin' and p.is_file()}
adaptations = []
for target in sorted(targets):
    if not target.is_relative_to(project / 'node_modules/.pnpm'): continue
    original = target.read_bytes()
    if not original.startswith(b'#!'): continue
    header, sep, body = original.partition(b'\n')
    temporary = target.with_name('.nix-adapt-' + target.name)
    temporary.write_bytes(header.rstrip(b'\r') + sep + body)
    temporary.chmod(target.stat().st_mode); temporary.replace(target)
    subprocess.run([spec['bash'], spec['patcher'], str(target)], check=True)
    adapted = target.read_bytes()
    if adapted.partition(b'\n')[0] == ('#!' + spec['node']).encode():
        adapted = ('#!' + spec['node_launcher']).encode() + b'\n' + adapted.partition(b'\n')[2]
        target.chmod(target.stat().st_mode | 0o200)
        target.write_bytes(adapted)
    assert adapted.partition(b'\n')[2] == body, 'bin body changed'
    if adapted != original:
        adaptations.append({'path': str(target.relative_to(project)),
                            'before': hashlib.sha256(original).hexdigest(),
                            'after': hashlib.sha256(adapted).hexdigest(),
                            'header': adapted.partition(b'\n')[0].decode(), 'body_unchanged': True})
(out / 'bin-adaptations.json').write_text(json.dumps(adaptations, indent=2) + '\n')
run('pending-rebuild', common + ['rebuild', '--pending', '--recursive', '--reporter=ndjson'])
run('locked-platform-packages', [spec['node'], spec['platform_check']])
layout = json.loads((project / 'node_modules/.modules.yaml').read_text())
assert layout['hoistPattern'] == expected['hoistPattern']
assert layout['allowBuilds'] == expected['allowBuilds']
denied = [name for name, allowed in expected['allowBuilds'].items() if allowed is False]
assert all(any(entry.startswith(name + '@') for name in denied)
           for entry in layout.get('pendingBuilds', [])), 'approved lifecycle work remains pending'
assert not layout.get('enableGlobalVirtualStore', False)
guard()

# Independent bytes/topology inventory for this single experiment, not pnpm state.
inventory = {}
logical = allocated = 0
for p in sorted(project.rglob('*')):
    rel = str(p.relative_to(project)); st = p.lstat()
    if p.is_symlink():
        resolved = p.resolve(strict=True)
        assert resolved.is_relative_to(project), 'external link: ' + rel
        inventory[rel] = {'type': 'link', 'target': os.readlink(p)}
    elif p.is_file():
        inventory[rel] = {'type': 'file', 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                          'executable': bool(st.st_mode & 0o111), 'bytes': st.st_size}
        logical += st.st_size; allocated += st.st_blocks * 512
    elif p.is_dir(): inventory[rel] = {'type': 'directory'}
(out / 'inventory.json').write_text(json.dumps(inventory, sort_keys=True) + '\n')
(out / 'preparation.json').write_text(json.dumps({'source_inputs_unchanged': guard(),
    'pnpm': '12.6.0', 'GVS': False, 'logical_bytes': logical, 'allocated_bytes': allocated,
    'entries': len(inventory), 'adapted_headers': len(adaptations), 'pendingBuilds': layout.get('pendingBuilds'),
    'source_hooks': 'pnpm preinstall no-op documented; original body explicit with pnpm identity; original postinstall through stock pending rebuild',
    'browser_downloads': 'deferred by upstream CI PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1',
    'node_context_adapter': 'native launcher sets public NODE_PATH: cwd/node_modules and cwd parent; no Node preload/private API'}, indent=2) + '\n')
print(json.dumps({'prepared': str(out), 'entries': len(inventory), 'inputs': guard()}), flush=True)
