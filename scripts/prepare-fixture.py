"""Small fixture: immutable archive ingestion and native stock-pnpm preparation."""
import hashlib,json,os,shutil,socket,subprocess,sys,time,errno
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir()
workspace=out/'workspace';shutil.copytree(spec['source'],workspace,symlinks=True)
for p in [workspace,*workspace.rglob('*')]:
 if not p.is_symlink():p.chmod(p.stat().st_mode|0o200)
store=out/'store';trace=out/'fetch-trace.jsonl';trace.write_text('')
inputs={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.rglob('*') if p.is_file()}
os.environ.update(PNPM_CONFIG_STORE_DIR=str(store),MAINTENANCE_ZONE='nix-preparation-'+spec['branch'],LIFECYCLE_LOG_DIR=str(out/'lifecycle'),
 VITE_RAW_ARCHIVE_MAP=spec['archive_map'],VITE_RAW_FETCH_TRACE=str(trace),
 PNPM_CONFIG_PNPMFILE=spec['adapter'],PNPM_CONFIG_MANAGE_PACKAGE_MANAGER_VERSIONS='false',
 PNPM_CONFIG_SCRIPT_SHELL=spec['bash'],PNPM_CONFIG_OFFLINE='true',PNPM_CONFIG_PACKAGE_IMPORT_METHOD='copy',
 PNPM_CONFIG_TRUST_LOCKFILE='true',
 PNPM_CONFIG_ENABLE_GLOBAL_VIRTUAL_STORE='false',PNPM_CONFIG_SIDE_EFFECTS_CACHE='false',
 PNPM_CONFIG_VERIFY_STORE_INTEGRITY='true',PNPM_CONFIG_NPMRC_AUTH_FILE=str(out/'empty-auth.npmrc'))
(out/'empty-auth.npmrc').write_text('')
try:
 with socket.create_connection(('1.1.1.1',443),timeout=2):raise AssertionError('network allowed')
except OSError as error:assert error.errno==errno.EPERM
stages=[]
def run(label,args):
 start=time.monotonic();p=subprocess.run(list(map(str,args)),cwd=workspace,capture_output=True,text=True,timeout=180)
 (out/(label+'.stdout')).write_text(p.stdout);(out/(label+'.stderr')).write_text(p.stderr)
 stages.append({'label':label,'command':list(map(str,args)),'exit':p.returncode,'seconds':time.monotonic()-start})
 (out/'stages.json').write_text(json.dumps(stages,indent=2)+'\n')
 print(json.dumps(stages[-1]),flush=True);assert p.returncode==0,p.stdout[-2500:]+p.stderr[-2500:]
common=[spec['pnpm'],'--store-dir',str(store)]
run('cold-ingest',common+['install','--recursive','--offline','--frozen-lockfile','--trust-lockfile','--ignore-scripts','--reporter=ndjson'])
# Capture raw linked payloads before header adaptation and approved builds.
raw_inventory = {}
for p in sorted(workspace.rglob('*')):
    rel = str(p.relative_to(workspace))
    if p.is_symlink(): raw_inventory[rel] = {'type':'link','target':os.readlink(p)}
    elif p.is_file(): raw_inventory[rel] = {'type':'file','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'executable':bool(p.stat().st_mode & 0o111),'bytes':p.stat().st_size}
    elif p.is_dir(): raw_inventory[rel] = {'type':'directory'}
(out/'raw-inventory.json').write_text(json.dumps(raw_inventory,sort_keys=True)+'\n')

# Reuse the reviewed shebang adaptation on detached private package files.
for target in sorted({p.resolve() for p in workspace.rglob('*') if p.parent.name=='.bin' and p.is_file()}):
 if not target.is_relative_to(workspace/'node_modules/.pnpm'):continue
 before=target.read_bytes()
 if not before.startswith(b'#!'):continue
 header,sep,body=before.partition(b'\n');tmp=target.with_name('.maintenance-adapt-'+target.name)
 tmp.write_bytes(header.rstrip(b'\r')+sep+body);tmp.chmod(target.stat().st_mode);tmp.replace(target)
 subprocess.run([spec['bash'],spec['patcher'],str(target)],check=True)
 assert target.read_bytes().partition(b'\n')[2]==body
run('root-preinstall',common+['--config.verify-deps-before-run=false','run','preinstall'])
run('native-pending-rebuild',common+['rebuild','--pending','--recursive','--reporter=ndjson'])
run('scripts-and-resolution',common+['run','test'])
run('native-bin',common+['exec','esbuild','--version'])
run('semver-bin',common+['exec','semver','1.2.3'])
if (workspace/'packages/new-workspace/package.json').exists():
 run('new-workspace-script',common+['--filter','@maintenance/new-workspace','run','test'])
 # Preserve source shebangs: /usr/bin/env is not a declared Nix input.
 # Direct executable-bin behavior is checked separately in the host flow.
 run('new-workspace-bin-body',common+['--filter','@maintenance/app','exec',spec['node'],'../new-workspace/bin.cjs'])
assert all(hashlib.sha256((workspace/r).read_bytes()).hexdigest()==h for r,h in inputs.items())
inventory={}
for p in sorted(workspace.rglob('*')):
 rel=str(p.relative_to(workspace))
 if p.is_symlink():assert p.resolve().is_relative_to(workspace);inventory[rel]=['link',os.readlink(p)]
 elif p.is_file():inventory[rel]=['file',p.stat().st_mode & 0o777,hashlib.sha256(p.read_bytes()).hexdigest()]
 elif p.is_dir():inventory[rel]=['directory',p.stat().st_mode & 0o777]
records=[json.loads(x) for x in trace.read_text().splitlines()]
result={'passed':True,'branch':spec['branch'],'pnpm':'12.6.0','node':'24.18.0','network_denial':'EPERM',
 'source_input_hashes':inputs,'native_extractions':sum(x['event']=='native-extract-end' for x in records),
 'workspace':str(workspace),'store':str(store),'stages':stages,'lifecycle_log':str(out/'lifecycle/events.jsonl')}
(out/'inventory.json').write_text(json.dumps(inventory,sort_keys=True)+'\n')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
