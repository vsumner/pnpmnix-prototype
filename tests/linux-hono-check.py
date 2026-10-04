"""Bounded reuse/publication gates; require an existing qualified Linux preparation/checkout."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
if sys.flags.optimize:raise SystemExit('run without Python optimization')
ROOT=Path(__file__).resolve().parent.parent;sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'linux-hono/scripts'))
import flow
from trees import digest,require
p=argparse.ArgumentParser(description=__doc__)
for name in ['prepared','checkout','state','artifacts']:p.add_argument('--'+name,required=True)
a=p.parse_args();out=Path(a.artifacts).resolve();require(not out.exists() and not out.is_relative_to(ROOT),'use a fresh external artifact directory');out.mkdir(parents=True)
checkout=Path(a.checkout).resolve();state=Path(a.state).resolve();flow.host();require(flow.ROOT==ROOT,'Linux namespace source boundary differs');spec=flow.load_prepared(a.prepared)
require(spec['platform']=='aarch64-linux' and spec['profile']=='hono' and spec['hooks']==[],'unsupported exact qualification scope')
require(all(digest(checkout/rel)==sha for rel,sha in spec['inputs'].items()),'active checkout does not match original Hono inputs')
checks=[]
def run(label,command,success=True,diagnostic=''):
 logs=out/label;logs.mkdir();r=flow.command(command,ROOT,None,logs,'command',check=False)
 require((r['exit']==0)==success and diagnostic in (r['stdout']+r['stderr']).decode(),label+' outcome differs')
 checks.append({'label':label,'exit':r['exit'],'passed':True});print(label,'passed',flush=True)
run('public-input-pins',[sys.executable,str(ROOT/'linux-hono/input-paths.py'),'--verify'])
cli=[sys.executable,str(ROOT/'linux-hono/pnpmnix.py')];args=['--checkout',str(checkout),'--state',str(state)]
run('native-esbuild',cli+['pnpm',*args,'--','exec','esbuild','--version'])
run('native-default-vp',cli+['pnpm',*args,'--','exec','vp','--version'])
run('service-worker-tests',cli+['pnpm',*args,'--','--filter','@hono/service-worker','run','test','--maxWorkers=1'])
run('private-store-override',cli+['pnpm',*args,'--','install','--store-dir=/tmp/unqualified-store'],False,'stock argument overrides private/local scope')
run('unreviewed-profile',cli+['prepare','--profile','vite','--output',str(out/'unsupported')],False,'invalid choice')
require(all(digest(checkout/rel)==sha for rel,sha in spec['inputs'].items()),'bounded gates changed source inputs')
result={'passed':True,'gates':checks,'source_inputs_unchanged':len(spec['inputs']),'full_experiment_repeated':False,'new_preparation_or_restore_pair_created':False,'scope':'Existing qualified original Hono ARM64 Linux reuse/publication checks'}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
