"""Single guarded entry point. Run artifacts stay outside the source bundle."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time

if sys.flags.optimize:
    raise SystemExit('Python optimization disables verification; run without -O or PYTHONOPTIMIZE.')
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--full', action='store_true', help='run the frozen Vite native/patch/build/26-assertion verification')
args = parser.parse_args()
root = Path(__file__).resolve().parent
assert sys.version_info >= (3, 9), 'bootstrap Python3.9+ required'
assert platform.system() == 'Darwin' and platform.machine() == 'arm64', 'tested prototype requires Apple Silicon macOS'
nix_build = shutil.which('nix-build') or '/nix/var/nix/profiles/default/bin/nix-build'
nix = str(Path(nix_build).parent / 'nix')
version = subprocess.run([nix, '--version'], capture_output=True, text=True, check=True).stdout.strip()
assert version.split()[-1] == '2.35.2', 'prototype tested with Nix2.35.2; use that daemon/client without changing global configuration'
info = subprocess.run([nix, '--extra-experimental-features', 'nix-command', 'store', 'info', '--store', 'daemon', '--json'],
                      capture_output=True, text=True, check=True)
assert json.loads(info.stdout)['version'] == '2.35.2', 'running daemon version must match'
module = importlib.util.spec_from_file_location('stable_groups', root / 'scripts/stable-groups.py')
stable = importlib.util.module_from_spec(module); module.loader.exec_module(stable)
catalog = json.loads((root / 'data/catalog.json').read_text())
mapping = json.loads((root / 'data/groups.json').read_text())
assert stable.assign(catalog) == mapping == stable.assign(reversed(list(catalog)))
assert len(catalog) == 1301 and len(mapping) == 32
ids = [f'fixture-{index}@1.0.0' for index in range(65)]
assert stable.assign(ids) == stable.assign(reversed(ids))
assert sorted(x for members in stable.assign(ids).values() for x in members) == sorted(ids)
assert all(0 < len(members) <= 64 for members in stable.assign(ids).values())
base = ids[:64]; assert stable.assign(base) == {'b0-0': sorted(base)}
assert stable.assign(ids)['b1-0'] and stable.assign(ids)['b1-1']
assert stable.assign(ids[:-1]) == stable.assign(base)
override = os.environ.get('PNPMNIX_RUN_DIR')
run_dir = Path(override).expanduser().resolve() if override else Path(tempfile.mkdtemp(prefix='pnpmnix-run-'))
assert not run_dir.is_relative_to(root), 'run artifacts must stay outside the publication source bundle'
if override: run_dir.mkdir(parents=True, exist_ok=False)
def free(): return min(shutil.disk_usage(run_dir).free, shutil.disk_usage('/nix/store').free)
baseline = free(); assert baseline > 12 * 2**30, 'need more than12GiB free on output and Nix-store volumes'
attribute = 'consumer' if args.full else 'smokeTests'
command = [nix_build, str(root / 'default.nix'), '-A', attribute, '--keep-failed', '--out-link', str(run_dir / 'result'),
           '--option', 'sandbox', 'true', '--option', 'sandbox-fallback', 'false', '--builders', '', '--max-jobs', '4',
           '--option', 'substitute', 'true', '--option', 'substituters', 'https://cache.nixos.org']
stdout = run_dir / 'build.stdout'; stderr = run_dir / 'build.stderr'
started = time.monotonic(); minimum = baseline; limit = 3600
print('Running ' + attribute + '; retained artifacts: ' + str(run_dir), flush=True)
def record(status, **extra):
    value = {'status': status, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'attribute': attribute,
             'command': command, 'baseline_free_bytes': baseline, 'minimum_sampled_free_bytes': minimum,
             'reserve_floor_GiB': 10, 'polling_guard_GiB': 12, 'time_cap_seconds': limit,
             'sandbox': True, 'sandbox_fallback': False, 'max_jobs': 4, **extra}
    (run_dir / 'run.json').write_text(json.dumps(value, indent=2) + '\n')
record('running')
with stdout.open('x') as output, stderr.open('x') as error:
    process = subprocess.Popen(command, stdout=output, stderr=error, start_new_session=True)
    try:
        last = 0
        while process.poll() is None:
            minimum = min(minimum, free())
            if minimum < 12*2**30: raise RuntimeError('free-reserve guard: stop before10GiB floor')
            if time.monotonic() - started > limit: raise RuntimeError('one-hour phase bound')
            if time.monotonic() - last > 2:
                record('running', pid=process.pid, seconds=time.monotonic()-started); last=time.monotonic()
            try: process.wait(timeout=.2)
            except subprocess.TimeoutExpired: pass
    except BaseException as failure:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        except ProcessLookupError: pass
        record('stopped', error=str(failure), exit=process.poll(),
               cancellation='client stop requested; daemon cancellation not independently proved')
        raise
minimum = min(minimum, free())
outputs = stdout.read_text().splitlines() if process.returncode == 0 else []
record('built' if process.returncode == 0 else 'failed', exit=process.returncode,
       seconds=time.monotonic()-started, outputs=outputs)
if process.returncode:
    print(stderr.read_text(errors='replace')[-6000:], file=sys.stderr); raise SystemExit(process.returncode)
receipts=[]
try:
    for output in outputs:
        path=Path(output)
        receipt=path/('result.json' if args.full or (path/'result.json').exists() else 'controls.json')
        value=json.loads(receipt.read_text());assert value['passed']
        if args.full:
            assert value['focused_test_assertions_passed']==26 and value['source_inputs_unchanged']==313
        receipts.append({'output':output,'passed':True})
except BaseException as failure:
    record('failed', exit=process.returncode, seconds=time.monotonic()-started,
           outputs=outputs, verification_error=str(failure))
    raise
record('passed', exit=0, seconds=time.monotonic()-started, outputs=outputs)
print(json.dumps({'passed':True,'receipts':receipts,'seconds':time.monotonic()-started,
                  'minimum_sampled_free_GiB':minimum/2**30,'artifacts':str(run_dir)},indent=2))
