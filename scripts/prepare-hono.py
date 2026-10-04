"""Exact local Hono profile; no generic inventory or configuration conversion."""
import errno,hashlib,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir()
workspace=out/'workspace';shutil.copytree(spec['source'],workspace,symlinks=True)
for p in [workspace,*workspace.rglob('*')]:
 if not p.is_symlink():p.chmod(p.stat().st_mode|0o200)
store=out/'store';trace=out/'fetch-trace.jsonl';trace.write_text('')
os.environ.update(PNPM_CONFIG_STORE_DIR=str(store),VITE_RAW_ARCHIVE_MAP=spec['archive_map'],
 VITE_RAW_FETCH_TRACE=str(trace),PNPM_CONFIG_PNPMFILE=spec['adapter'],
 PNPM_CONFIG_MANAGE_PACKAGE_MANAGER_VERSIONS='false',PNPM_CONFIG_SCRIPT_SHELL=spec['bash'],
 PNPM_CONFIG_OFFLINE='true',PNPM_CONFIG_PACKAGE_IMPORT_METHOD='copy',PNPM_CONFIG_TRUST_LOCKFILE='true',
 PNPM_CONFIG_ENABLE_GLOBAL_VIRTUAL_STORE='false',PNPM_CONFIG_SIDE_EFFECTS_CACHE='false',
 PNPM_CONFIG_VERIFY_STORE_INTEGRITY='true',PNPM_CONFIG_NPMRC_AUTH_FILE=str(out/'empty-auth.npmrc'))
(out/'empty-auth.npmrc').write_text('')
try:
 with socket.create_connection(('1.1.1.1',443),timeout=2):raise AssertionError('network allowed')
except OSError as e:assert e.errno==errno.EPERM
stages=[]
def run(label,args):
 start=time.monotonic();p=subprocess.run(list(map(str,args)),cwd=workspace,capture_output=True,text=True,timeout=600)
 (out/(label+'.stdout')).write_text(p.stdout);(out/(label+'.stderr')).write_text(p.stderr)
 stages.append({'label':label,'command':list(map(str,args)),'exit':p.returncode,'seconds':time.monotonic()-start})
 (out/'stages.json').write_text(json.dumps(stages,indent=2)+'\n');print(json.dumps(stages[-1]),flush=True)
 assert p.returncode==0,p.stdout[-2500:]+p.stderr[-2500:]
run('cold-ingest',[spec['pnpm'],'install','--recursive','--offline','--frozen-lockfile','--trust-lockfile','--ignore-scripts','--reporter=ndjson'])
# Keep Hono's default cmd shims unchanged. No header or payload adaptation.
import importlib.util
m=importlib.util.spec_from_file_location('trees',spec['trees']);trees=importlib.util.module_from_spec(m);m.loader.exec_module(trees)
(out/'raw-inventory.json').write_text(json.dumps(trees.inventory(workspace),sort_keys=True)+'\n')
run('native-pending-rebuild',[spec['pnpm'],'rebuild','--pending','--recursive','--reporter=ndjson'])
# Exercise the native bundler through declared Node without changing default
# cmd shims or source files. Normal stock build/tests and bins run on the host.
run('native-rolldown',[spec['node'],'-e',"const r=require('rolldown'); r.build({input:'src/index.ts',write:false}).then(o=>{if(!o.output.length)process.exit(1)})"])
assert all(trees.digest(workspace/r)==h for r,h in spec['source_hashes'].items())
(out/'result.json').write_text(json.dumps({'passed':True,'network_denial':'EPERM','stages':stages,'source_inputs':len(spec['source_hashes']),'header_adaptation':False},indent=2)+'\n')
