"""Exact public reuse-input listing and registered-NAR boundary check; no acquisition."""
import argparse,json,subprocess,sys
from pathlib import Path
if sys.flags.optimize:raise SystemExit('Verification requires Python without -O/PYTHONOPTIMIZE.')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');args=p.parse_args()
v=json.loads((Path(__file__).resolve().parent/'linux-inputs.json').read_text());pins=v['nar_pins'];paths=sorted({v['nixpkgs_source'],v['hono_source'],*v['groups'].values()})
assert set(paths)==set(pins) and len(paths)==28
if args.verify:
 nix='/nix/var/nix/profiles/default/bin/nix';rows=json.loads(subprocess.check_output([nix,'--extra-experimental-features','nix-command','path-info','--store','daemon','--json','--json-format','1',*paths],text=True))
 for path in paths:
  assert {k:rows[path][k] for k in ['narHash','narSize','references']}==pins[path],'registered public input differs: '+path
 print(json.dumps({'passed':True,'registered_public_inputs':len(paths),'reference_free':True,'operation':'metadata-only; preparation separately verifies raw SHA512 and source bytes'}))
else:
 for path in paths:print(path)
