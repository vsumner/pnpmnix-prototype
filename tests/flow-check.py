"""Focused real stock-pnpm flow qualification. Artifacts are retained outside source."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

if sys.flags.optimize: raise SystemExit('run without Python optimization')
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
import flow
from trees import copy_private, digest, inventory, require, verify

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--artifacts',required=True)
for b in 'abc': p.add_argument('--prepared-'+b)
args = p.parse_args(); artifacts = Path(args.artifacts).resolve()
require(not artifacts.is_relative_to(ROOT) and not artifacts.exists(), 'use a fresh external artifact directory')
artifacts.mkdir(parents=True); flow.host()
handles = {}
for b in 'abc':
    existing = getattr(args,'prepared_'+b)
    handles[b] = existing or flow.prepare('fixture-'+b,artifacts/('prepare-'+b))['prepared']
specs = {b:flow.load_prepared(h) for b,h in handles.items()}
producer_before = {b:inventory(Path(s['prepared'])/'workspace') for b,s in specs.items()}
store_before = {b:inventory(s['store']) for b,s in specs.items()}
checks = []

def passed(label):
    checks.append(label); flow.write_json(artifacts/'progress.json',{'passed_checks':checks})
    print('PASS '+label,flush=True)


def reject(label,fn):
    try: fn()
    except (ValueError,FileNotFoundError,subprocess.CalledProcessError): passed(label)
    else: raise AssertionError('negative case accepted: '+label)


def source(b,target):
    target.mkdir(exist_ok=True)
    for r in specs[b]['inputs']:
        q=target/r; q.parent.mkdir(parents=True,exist_ok=True)
        if q.exists(): q.chmod(q.stat().st_mode|0o200)
        shutil.copy2(Path(specs[b]['source'])/r,q); q.chmod(q.stat().st_mode|0o200)
        os.utime(q,None)  # Git checkout writes current mtimes; do not restore Nix epoch mtimes.


def switch_source(b,target):
    # Equivalent source snapshots isolate generated-tree return semantics; the
    # private follow-up also exercises actual Git branches without new commits.
    current = {r for s in specs.values() for r in s['inputs']}
    for r in current-set(specs[b]['inputs']):
        q=target/r
        if q.exists(): q.unlink()
    source(b,target)

w=artifacts/'checkout'; state=artifacts/'state'; source('a',w)
(w/'local-edit.txt').write_text('preserve this development source\n')
subprocess.run([specs['a']['tools']['git'],'init','--initial-branch=fixture'],cwd=w,capture_output=True,check=True)
a=flow.restore(handles['a'],w,state)
require(a['checkout_hooks']=='pending', 'hooks were claimed complete')
require(not (w/'.git/hooks/pre-commit').exists(), 'suppressed checkout hook ran')
flow.verify_dependencies(specs['a'],w,Path(a['store']))
passed('root/workspace restore, exact prepared payload reuse, pending lifecycle explicit')
a=flow.restore(handles['a'],w,state,True)
require(a['checkout_hooks']=='completed' and (w/'.git/hooks/pre-commit').stat().st_mode & 0o111,'checkout hook absent')
log=[json.loads(x) for x in (state/'runtime/effects/events.jsonl').read_text().splitlines()]
require({x['phase'] for x in log} >= {'root-preinstall','root-postinstall','lib-postinstall'}, 'assigned lifecycle missing')
require(all(x['root']==str(w) and x['zone']=='private-development' for x in log), 'effects outside checkout')
passed('explicit root/workspace hook replay and checkout-local executable hook')


def pnpm(*argv,offline=True): return flow.stock(w,state,list(argv),offline)

pnpm('run','test'); pnpm('exec','esbuild','--version'); pnpm('exec','semver','1.2.3')
passed('runtime, peer, patch, workspace resolution, native transform and bins')
# Confirm automatic install children get the private store via environment.
active=json.loads((state/'active.json').read_text())
env=flow.environment(specs['a'],state,Path(active['store']),True)
effective=json.loads(subprocess.check_output([specs['a']['tools']['pnpm'],'config','list','--json'],cwd=w,env=env,text=True))
require(effective['storeDir']==active['store'] and effective['packageImportMethod']=='copy' and not effective['enableGlobalVirtualStore'],'private store config not inherited')
passed('persistent store/data/home config for native child installs')

# Frozen identity is an activation condition, not a maintenance outcome.
config_path=w/'pnpm-workspace.yaml'; original_config=config_path.read_bytes()
config=json.loads(original_config); config['minimumReleaseAgeExclude']=['fixture@1.0.0']
config_path.write_text(json.dumps(config,indent=2)+'\n')
outcome=pnpm('--version')
require(outcome['exit_code']==0 and outcome['prepared_state']['refresh_required'] and
        'pnpm-workspace.yaml' in outcome['prepared_state']['changed_inputs'],'mutable config drift not reported')
reject('changed frozen configuration still blocks restore',lambda:flow.restore(handles['a'],w,state))
config['allowBuilds']['esbuild']=False; config_path.write_text(json.dumps(config,indent=2)+'\n')
reject('changed build decision rejected before maintenance',lambda:pnpm('run','test'))
config_path.write_bytes(original_config)
for flag in ['--allow-build=esbuild','--config.dangerouslyAllowAllBuilds=true','--no-strict-dep-builds',
             '--config','--config.minimum-release-age-strict=false','--trust-policy-ignore-after=0',
             '--no-verify-store-integrity','--trust-lockfile']:
 reject('build approval override requires review: '+flag,lambda flag=flag:pnpm('install',flag))
passed('ordinary configuration drift permits maintenance without changing approved build policy')

try: pnpm('exec','node','--eval','process.stdout.write("native-out\\n");process.stderr.write("native-err\\n");process.exit(23)')
except flow.PnpmCommandError as error:
 require(error.result['exit_code']==23,'native failure status masked')
 logs=Path(error.result['logs'])
 require((logs/'pnpm.stdout').read_text()=='native-out\n' and (logs/'pnpm.stderr').read_text()=='native-err\n','native streams changed')
else: raise AssertionError('native failure hidden')
passed('native nonzero status and separate output streams retained')

native_args=['exec','node','--eval','process.stdout.write(Buffer.from([255,13,10,13]));process.stderr.write(Buffer.from([254,13,10]));process.exit(23)']
native_env=flow.environment(specs['a'],state,Path(json.loads((state/'active.json').read_text())['store']),True)
control=subprocess.run([specs['a']['tools']['pnpm'],*native_args],cwd=w,env=native_env,capture_output=True)
wrapped=subprocess.run([sys.executable,str(ROOT/'pnpmnix.py'),'pnpm','--checkout',str(w),'--state',str(state),'--offline','--',*native_args],capture_output=True)
require(control.returncode==wrapped.returncode==23 and control.stdout==wrapped.stdout==bytes([255,13,10,13]),'native binary status/stdout differs')
require(wrapped.stderr.startswith(control.stderr) and control.stderr==bytes([254,13,10]),'native binary stderr differs')
receipt=json.loads(wrapped.stderr[len(control.stderr):]);require(receipt['exit_code']==23,'native CLI receipt status differs')
passed('CLI preserves binary/CR/CRLF output bytes and exact native exit')

extra=w/'dist/example/package.json'; extra.parent.mkdir(parents=True); extra.write_text('{"name":"generated-example"}\n')
inert=w/'dist/.pnpmfile.cjs'; inert.write_text('throw new Error("unconsumed output must not run");\n')
flow.matching(specs['a'],w,env)
before_output=inventory(w/'dist')
flow.restore(handles['a'],w,state)
require(inventory(w/'dist')==before_output,'non-workspace generated files changed')
passed('non-workspace generated manifests/config filenames preserved without project exceptions')

before={r:digest(w/r) for r in specs['a']['inputs']}
reject('cold offline add safely rejects unavailable registry metadata', lambda:pnpm('--filter','@maintenance/app','add','picocolors@1.1.1','--save-exact','--offline'))
require(before=={r:digest(w/r) for r in before},'failed offline add changed inputs')
pnpm('--filter','@maintenance/app','add','picocolors@1.1.1','--save-exact',offline=False)
require(json.loads((w/'packages/app/package.json').read_text())['dependencies']['picocolors']=='1.1.1','add failed')
pnpm('--workspace-root','update','semver@7.8.5','--save-exact',offline=False)
require(json.loads((w/'package.json').read_text())['dependencies']['semver']=='7.8.5','update failed')
pnpm('--filter','@maintenance/app','remove','picocolors','--offline')
require(not (w/'packages/app/node_modules/picocolors').exists(),'remove link retained')
pnpm('run','test')
passed('stock add/update/remove with manifest/lock edits and scripts enabled')

# Native automatic branch refresh after returning to A, using the warmed store.
switch_source('a',w); pnpm('run','test')
require(json.loads((w/'node_modules/semver/package.json').read_text())['version']=='6.3.1','automatic branch refresh failed')
passed('stock automatic source return refreshes active version with inherited private store')

copy_private(ROOT/'tests/fixtures/c/packages/new-workspace',w/'packages/new-workspace')
pnpm('--filter','@maintenance/app','add','@maintenance/new-workspace@workspace:*','--offline')
require((w/'packages/app/node_modules/@maintenance/new-workspace').resolve()==w/'packages/new-workspace','new workspace missing')
pnpm('--filter','@maintenance/app','exec','maintenance-workspace')
pnpm('--filter','@maintenance/new-workspace','run','test')
require('packages/new-workspace:' in (w/'pnpm-lock.yaml').read_text(),'native importer absent')
passed('stock native workspace discovery/add, peer resolution, lifecycle and executable bin')

switch_source('b',w); a=flow.restore(handles['b'],w,state,True)
require(not (w/'packages/app/node_modules/.bin/maintenance-workspace').is_symlink(),'obsolete bin retained')
require(not (w/'packages/new-workspace/node_modules').exists(),'orphan generated dependencies retained')
require(not (w/'packages/new-workspace').exists(),'empty obsolete generated workspace directory retained')
require('packages/new-workspace:' not in (w/'node_modules/.pnpm/lock.yaml').read_text(),'obsolete importer retained')
pnpm('run','test')
passed('matching B clears removed workspace link/bin/dependency directory/importer')
switch_source('c',w); a=flow.restore(handles['c'],w,state,True)
pnpm('run','test'); pnpm('--filter','@maintenance/app','exec','maintenance-workspace')
passed('matching C return restores root/workspace native tree and checkout effects')

# Mismatches and corruptions must not alter an already active dependency tree.
def dependencies(): return inventory(w,omit=('.git',))
before_deps=dependencies(); old_active=(state/'active.json').read_bytes()
pkg=w/'package.json'; old=pkg.read_bytes(); pkg.write_bytes(old+b'\n')
reject('changed manifest rejected before activation',lambda:flow.restore(handles['c'],w,state))
pkg.write_bytes(old); require(dependencies()==before_deps and (state/'active.json').read_bytes()==old_active,'mismatch altered active state')
(w/'.npmrc').write_text('node-linker=hoisted\n')
reject('undeclared configuration rejected',lambda:flow.restore(handles['c'],w,state))
(w/'.npmrc').unlink()
(w/'packages/undeclared').mkdir(); (w/'packages/undeclared/package.json').write_text('{"name":"undeclared","version":"1.0.0"}')
reject('undeclared workspace rejected',lambda:flow.restore(handles['c'],w,state))
(w/'packages/undeclared/package.json').unlink(); (w/'packages/undeclared').rmdir()
handle=json.loads(Path(handles['c']).read_text());handle['manifest_sha256']='0'*64
flow.write_json(artifacts/'corrupt-handle.json',handle)
reject('corrupt prepared manifest identity rejected',lambda:flow.restore(artifacts/'corrupt-handle.json',w,state))
for flag in ['--store-dir=/tmp/other','--config.storeDir=/tmp/other','--config.packageImportMethod=hardlink','--dir=/tmp','--global',
             '--workspace-packages=../outside','--config.pm-on-fail=ignore','--runtime-on-fail=download']:
 reject('private scope override rejected: '+flag,lambda flag=flag:pnpm(flag,'install'))
for cmd in ['with','runtime','rt']:
 reject('unqualified engine management rejected: '+cmd,lambda cmd=cmd:pnpm(cmd,'12.8.1'))

original_copy=flow.copy_private
for case in ['corrupt','missing','external-link']:
 def bad_copy(src,dst,check=lambda:None,case=case):
  original_copy(src,dst,check)
  if Path(dst).name=='workspace':
   q=Path(dst)/'node_modules/.pnpm/esbuild@0.28.2/node_modules/esbuild/bin/esbuild'
   if case=='corrupt': q.write_bytes(b'X'*q.stat().st_size)
   elif case=='missing': q.unlink()
   else:
    q=Path(dst)/'packages/app/node_modules/react';q.unlink();q.symlink_to(Path(specs['c']['prepared'])/'workspace/node_modules/react')
 flow.copy_private=bad_copy
 reject('staged '+case+' rejected before successful activation',lambda:flow.restore(handles['c'],w,state))
 flow.copy_private=original_copy
 require(dependencies()==before_deps and (state/'active.json').read_bytes()==old_active,'corruption altered active dependencies')

original_command=flow.command
for failure in [ValueError('injected link failure'),KeyboardInterrupt()]:
 def bad_command(*a,**kw): raise failure
 flow.command=bad_command
 try: flow.restore(handles['c'],w,state)
 except (ValueError,KeyboardInterrupt): pass
 else: raise AssertionError('failed command activated')
 flow.command=original_command
 require(dependencies()==before_deps and (state/'active.json').read_bytes()==old_active and not (state/'pending.json').exists(),'failed activation did not roll back')
 passed('rollback after '+type(failure).__name__)

# Abrupt process exit after directory moves leaves a journal; recovery retains
# partial trees and restores exactly the prior dependencies without deleting logs.
pid=os.fork()
if pid==0:
 flow.command=lambda *a,**kw:os._exit(73)
 flow.restore(handles['c'],w,state);os._exit(1)
_,status=os.waitpid(pid,0);require(os.WEXITSTATUS(status)==73 and (state/'pending.json').exists(),'abrupt-exit control failed')
reject('stock command blocks interrupted activation',lambda:pnpm('run','test'))
with flow.locked(w,state) as (wc,st): flow.rollback(wc,st)
require(dependencies()==before_deps and (state/'active.json').read_bytes()==old_active,'recovery differs')
passed('abrupt-exit journal recovery restores previous generated trees')

sibling=artifacts/'sibling';source('a',sibling);sibling_state=artifacts/'sibling-state'
b=flow.restore(handles['a'],sibling,sibling_state)
sibling_before=inventory(sibling); sibling_store=inventory(b['store'])
(w/'node_modules/react/README.md').write_text('mutable dependency edit\n')
require(inventory(sibling)==sibling_before and inventory(b['store'])==sibling_store,'sibling mutated')
for key,s in specs.items():
 require(inventory(Path(s['prepared'])/'workspace')==producer_before[key] and inventory(s['store'])==store_before[key],'immutable output changed')
require((w/'local-edit.txt').read_text()=='preserve this development source\n','source edit lost')
passed('mutable dependency/source edits isolated from all immutable outputs and sibling checkout/store')
# Permanent regressions for the independent review findings.
reject('compact -C scope override rejected',lambda:pnpm('-C'+str(artifacts),'run','test'))
marker=artifacts/'undeclared-pnpmfile-effect.txt'
(w/'.pnpmfile.cjs').write_text('require("node:fs").writeFileSync('+json.dumps(str(marker))+',"executed"); module.exports={};')
reject('pnpmfile rejected before native discovery executes it',lambda:flow.restore(handles['c'],w,state))
require(not marker.exists(),'undeclared pnpmfile executed before rejection');(w/'.pnpmfile.cjs').unlink()
nested=w/'packages/app/pnpm-workspace.yaml';nested.write_text('{"pnpmfile":"hooks.cjs"}\n')
reject('new nested executable workspace context rejected before maintenance',lambda:pnpm('--version'))
nested.rename(artifacts/'retained-nested-workspace.yaml')
# Postflight diagnostics may require review, but cannot replace native status.
for code in [0,29]:
 body='require("node:fs").writeFileSync(".pnpmfile.cjs",'+json.dumps('require("node:fs").writeFileSync('+json.dumps(str(marker))+',"executed");module.exports={};')+');process.exit('+str(code)+')'
 try: result=pnpm('exec','node','--eval',body)
 except flow.PnpmCommandError as error: result=error.result
 require(result['exit_code']==code and result['warnings'] and result['prepared_state']['refresh_required'],'postflight masked native result')
 require(not marker.exists(),'postflight executed unreviewed config')
 reject('postflight config change blocks next preflight '+str(code),lambda:pnpm('--version'))
 (w/'.pnpmfile.cjs').rename(artifacts/('retained-postflight-'+str(code)+'.cjs'))
passed('native success/failure survives postflight review warnings without executing changed config')
saved=state/'saved-hooks';(w/'.git/hooks').rename(saved)
outside=artifacts/'outside-hooks';outside.mkdir();(w/'.git/hooks').symlink_to(outside)
reject('external Git hooks symlink rejected before activation',lambda:flow.restore(handles['c'],w,state,True))
require(not (outside/'pre-commit').exists(),'hook escaped checkout')
(w/'.git/hooks').unlink();saved.rename(w/'.git/hooks')
reject('second state cannot claim same checkout',lambda:flow.restore(handles['c'],w,artifacts/'other-state'))
with flow.locked(w,state):
 reject('same checkout concurrent command rejected',lambda:pnpm('run','test'))
late=artifacts/'late-root-checkout';source('a',late)
def late_root(src,dst,check=lambda:None):
 original_copy(src,dst,check)
 if Path(dst).name=='workspace':
  (late/'node_modules').mkdir();(late/'node_modules/source-created.txt').write_text('keep unowned data')
flow.copy_private=late_root
reject('late unowned dependency directory rejected after staging',lambda:flow.restore(handles['a'],late,artifacts/'late-state'))
flow.copy_private=original_copy
require((late/'node_modules/source-created.txt').read_text()=='keep unowned data','late unowned data moved')
flow.write_json(artifacts/'result.json',{'passed':True,'checks':checks,'count':len(checks),
 'handles':handles,'checkout':str(w),'state':str(state),'ordinary_copy':True,
 'limits':['source-return controls use exact snapshots; separate private Git branch control required',
           'injected failures/crash; no real disk exhaustion or power-loss test',
           'fixture hooks/esbuild binary reconstruction; arbitrary lifecycle and native source compilation unqualified']})
print(json.dumps({'passed':True,'checks':len(checks),'artifacts':str(artifacts)},indent=2))
