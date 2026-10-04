"""Cold one-package controls for this integration's stock-pnpm archive adapter."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]); out.mkdir()
assert spec['mode'] in ['corrupt', 'missing']
pkg_id = 'react@19.3.0'
original_entry = json.loads((Path(spec['acquisition']) / 'archive-map.json').read_text())[pkg_id]
original_archive = Path(original_entry['archive'])
original_bytes = original_archive.read_bytes()
def integrity(data):
    return 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
assert integrity(original_bytes) == original_entry['integrity']
cases = ['corrupt'] if spec['mode'] == 'corrupt' else ['missing-map', 'missing-file']
results = []
for case in cases:
    case_out = out / case; case_out.mkdir()
    project = case_out / 'workspace'; project.mkdir()
    manifest = {'name': 'vite-raw-boundary-control', 'version': '1.0.0', 'private': True,
                'dependencies': {'react': '19.3.0'}}
    # JSON is valid YAML. This fixture freezes the real Vite package identity/SRI;
    # it tests the acquisition boundary, not the complete Vite dependency graph.
    lock = {'lockfileVersion': '9.0',
            'settings': {'autoInstallPeers': True, 'excludeLinksFromLockfile': False},
            'importers': {'.': {'dependencies': {'react': {'specifier': '19.3.0', 'version': '19.3.0'}}}},
            'packages': {pkg_id: {'resolution': {'integrity': original_entry['integrity']}}},
            'snapshots': {pkg_id: {}}}
    (project / 'package.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (project / 'pnpm-lock.yaml').write_text(json.dumps(lock, indent=2) + '\n')
    store = case_out / 'store'
    assert not store.exists() and not (project / 'node_modules').exists()
    archive_map = {pkg_id: dict(original_entry)}
    if case == 'corrupt':
        assert original_bytes[:2] == b'\x1f\x8b' and len(original_bytes) > 5
        changed = original_bytes[:4] + bytes([original_bytes[4] ^ 1]) + original_bytes[5:]
        assert len(changed) == len(original_bytes) and changed != original_bytes
        assert gzip.decompress(changed) == gzip.decompress(original_bytes)
        corrupt = case_out / 'corrupt-react.tgz'; corrupt.write_bytes(changed)
        archive_map[pkg_id]['archive'] = str(corrupt)
    elif case == 'missing-map':
        del archive_map[pkg_id]
    else:
        archive_map[pkg_id]['archive'] = str(case_out / 'deliberately-missing.tgz')
    map_file = case_out / 'archive-map.json'
    map_file.write_text(json.dumps(archive_map, indent=2) + '\n')
    trace = case_out / 'fetch-trace.jsonl'; trace.write_text('')
    env = dict(os.environ)
    for key, value in {'ENABLE_GLOBAL_VIRTUAL_STORE': 'false', 'SCRIPT_SHELL': spec['bash'],
        'STORE_DIR': str(store), 'OFFLINE': 'true', 'TRUST_LOCKFILE': 'true',
        'VERIFY_STORE_INTEGRITY': 'true', 'PACKAGE_IMPORT_METHOD': 'copy',
        'SIDE_EFFECTS_CACHE': 'false', 'IGNORE_SCRIPTS': 'true', 'PNPMFILE': spec['adapter'],
        'AUTO_INSTALL_PEERS': 'true', 'EXCLUDE_LINKS_FROM_LOCKFILE': 'false',
        'MANAGE_PACKAGE_MANAGER_VERSIONS': 'false'}.items():
        env['PNPM_CONFIG_' + key] = value
    env['VITE_RAW_ARCHIVE_MAP'] = str(map_file); env['VITE_RAW_FETCH_TRACE'] = str(trace)
    source_hashes = {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                     for name in ['package.json', 'pnpm-lock.yaml']}
    probe = subprocess.run([spec['node'], '-e',
        "const s=require('node:net').connect(443,'1.1.1.1');s.on('error',e=>{console.log(e.code);process.exit(e.code==='EPERM'?0:1)});s.on('connect',()=>process.exit(2));setTimeout(()=>process.exit(3),2000)"],
        cwd=project, env=env, capture_output=True, text=True, timeout=5)
    (case_out / 'network-denial.stdout').write_text(probe.stdout)
    (case_out / 'network-denial.stderr').write_text(probe.stderr)
    assert probe.returncode == 0 and 'EPERM' in probe.stdout, 'network denial oracle'
    command = [spec['pnpm'], '--store-dir', str(store), 'install', '--offline',
               '--frozen-lockfile', '--trust-lockfile', '--ignore-scripts', '--reporter=ndjson']
    started = time.monotonic()
    result = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=180)
    elapsed = time.monotonic() - started
    (case_out / 'install.stdout').write_text(result.stdout)
    (case_out / 'install.stderr').write_text(result.stderr)
    text = result.stdout + '\n' + result.stderr
    marker = {'corrupt': 'TARBALL_INTEGRITY', 'missing-map': 'UNDECLARED_RAW_SOURCE',
              'missing-file': 'MISSING_RAW_ARCHIVE'}[case]
    assert result.returncode != 0, case + ' unexpectedly succeeded'
    assert marker in text, case + ' failed for an unrelated reason'
    events = []
    for line in text.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if isinstance(event, dict): events.append(event)
    assert not any(event.get('name') == 'pnpm:lifecycle' for event in events)
    assert all(hashlib.sha256((project / name).read_bytes()).hexdigest() == digest
               for name, digest in source_hashes.items()), 'fixture manifest/lock changed'
    assert original_archive.read_bytes() == original_bytes, 'original archive changed'
    records = [json.loads(line) for line in trace.read_text().splitlines()]
    assert not any(record['event'] == 'native-extract-end' for record in records)
    if case == 'corrupt':
        assert records and all(record['pkgId'] == pkg_id for record in records)
    receipt = {'case': case, 'passed': True, 'command': command, 'exit': result.returncode,
               'seconds': elapsed, 'expected_failure_marker': marker, 'network_denial': 'EPERM',
               'initial_store_absent': True, 'initial_node_modules_absent': True,
               'fixture_inputs_unchanged': source_hashes, 'original_archive_unchanged': True,
               'original_archive_integrity': original_entry['integrity'],
               'lifecycle_events': 0, 'completed_native_fetch_calls': 0, 'trace': records}
    if case == 'corrupt':
        receipt.update(corrupt_integrity=integrity(changed), gzip_payload_equal=True)
    (case_out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    results.append(receipt)
    print(json.dumps({'case': case, 'passed': True, 'seconds': elapsed}), flush=True)
(out / 'controls.json').write_text(json.dumps({'passed': True, 'mode': spec['mode'],
    'scope': 'cold one-package React fixture using real Vite archive/SRI and the new adapter; full Vite graph is tested by later preparation/restore',
    'cases': results}, indent=2) + '\n')
