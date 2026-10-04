"""One real registry package, cold/warm offline native pnpm, frozen inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

spec=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir()
project=out/'workspace';project.mkdir();store=out/'store';trace=out/'fetch-trace.jsonl';trace.write_text('')
archive_map=json.loads((Path(spec['acquisition'])/'archive-map.json').read_text())
row=archive_map['react@19.3.0']
manifest={'name':'pnpmnix-offline-smoke','version':'1.0.0','private':True,'dependencies':{'react':'19.3.0'}}
lock={'lockfileVersion':'9.0','settings':{'autoInstallPeers':True,'excludeLinksFromLockfile':False},
      'importers':{'.':{'dependencies':{'react':{'specifier':'19.3.0','version':'19.3.0'}}}},
      'packages':{'react@19.3.0':{'resolution':{'integrity':row['integrity']}}},'snapshots':{'react@19.3.0':{}}}
for filename,data in [('package.json',manifest),('pnpm-lock.yaml',lock)]:
    (project/filename).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
hashes={name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in ['package.json','pnpm-lock.yaml']}
env=dict(os.environ);env['CI']='true'
for key,value in {'ENABLE_GLOBAL_VIRTUAL_STORE':'false','SCRIPT_SHELL':spec['bash'],'STORE_DIR':str(store),
    'OFFLINE':'true','TRUST_LOCKFILE':'true','VERIFY_STORE_INTEGRITY':'true','PACKAGE_IMPORT_METHOD':'copy',
    'SIDE_EFFECTS_CACHE':'false','IGNORE_SCRIPTS':'true','PNPMFILE':spec['adapter'],
    'AUTO_INSTALL_PEERS':'true','EXCLUDE_LINKS_FROM_LOCKFILE':'false','MANAGE_PACKAGE_MANAGER_VERSIONS':'false'}.items():
    env['PNPM_CONFIG_'+key]=value
env['VITE_RAW_ARCHIVE_MAP']=str(Path(spec['acquisition'])/'archive-map.json');env['VITE_RAW_FETCH_TRACE']=str(trace)
probe=subprocess.run([spec['node'],'-e',"const s=require('node:net').connect(443,'1.1.1.1');s.on('error',e=>{console.log(e.code);process.exit(e.code==='EPERM'?0:1)});s.on('connect',()=>process.exit(2));setTimeout(()=>process.exit(3),2000)"],cwd=project,env=env,capture_output=True,text=True,timeout=5)
assert probe.returncode==0 and probe.stdout.strip()=='EPERM'
stages=[]
for label in ['cold','warm']:
    trace.write_text('');started=time.monotonic()
    command=[spec['pnpm'],'--store-dir',str(store),'install','--offline','--frozen-lockfile','--trust-lockfile','--ignore-scripts','--reporter=ndjson']
    result=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=180)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    assert result.returncode==0,result.stdout[-3000:]+result.stderr[-3000:]
    events=[]
    for line in (result.stdout+'\n'+result.stderr).splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if isinstance(event,dict):events.append(event)
    assert events and not any(e.get('name')=='pnpm:lifecycle' for e in events)
    records=[json.loads(line) for line in trace.read_text().splitlines()]
    assert sum(r['event']=='native-extract-start' for r in records)==(1 if label=='cold' else 0)
    assert sum(r['event']=='native-extract-end' for r in records)==(1 if label=='cold' else 0)
    assert all(hashlib.sha256((project/name).read_bytes()).hexdigest()==value for name,value in hashes.items())
    check=subprocess.run([spec['node'],'-e',"const a=require('node:assert/strict');a.equal(require('react').version,'19.3.0');a.equal(require('react/package.json').version,'19.3.0');console.log('pass')"],cwd=project,env=env,capture_output=True,text=True,timeout=10)
    assert check.returncode==0,check.stderr
    link=project/'node_modules/react';assert link.is_symlink() and link.resolve().is_relative_to(project/'node_modules')
    stages.append({'stage':label,'seconds':time.monotonic()-started,'native_extractions':1 if label=='cold' else 0,'lifecycle_events':0,'event_streams_checked':['stdout','stderr']})
(out/'result.json').write_text(json.dumps({'passed':True,'network_denial':'EPERM','stages':stages,'frozen_input_hashes':hashes},indent=2)+'\n')
print((out/'result.json').read_text())
