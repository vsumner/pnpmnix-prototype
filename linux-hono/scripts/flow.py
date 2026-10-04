"""Bounded activation around stock pnpm, for the reviewed frozen profiles."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from trees import copy_private, digest, entries, inventory, relative, require, verify
from configuration import PROTECTED, configuration_paths, native_configuration, protected_configuration

ROOT = Path(__file__).resolve().parent.parent.parent
RESERVE = 3 * 2**30


def free_guard(path, needed=0):
    free = min(shutil.disk_usage(path).free, shutil.disk_usage('/nix/store').free)
    require(free > RESERVE + needed, 'need 3 GiB guest operating floor plus copy space; host 10 GiB guard is external')
    return free


def write_json(path, value):
    p = Path(path); tmp = p.with_name(p.name + '.new')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(p)


def command(args, cwd, env, logs, label, limit=600, check=True):
    free_guard(logs)
    start = time.monotonic(); minimum = free_guard(logs)
    with (logs/(label+'.stdout')).open('x') as out, (logs/(label+'.stderr')).open('x') as err:
        p = subprocess.Popen(list(map(str,args)), cwd=cwd, env=env, stdout=out, stderr=err, start_new_session=True)
        try:
            while p.poll() is None:
                minimum = min(minimum, free_guard(logs))
                require(time.monotonic()-start < limit, 'command time cap')
                try: p.wait(timeout=.2)
                except subprocess.TimeoutExpired: pass
        except BaseException:
            try:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait(timeout=5)
            except ProcessLookupError: pass
            raise
    write_json(logs/(label+'.json'), {'command':list(map(str,args)), 'exit':p.returncode,
        'seconds':time.monotonic()-start, 'minimum_sampled_free_bytes':minimum,
        'reserve_floor_GiB':3, 'polling_guard_GiB':3})
    stdout = (logs/(label+'.stdout')).read_bytes(); stderr = (logs/(label+'.stderr')).read_bytes()
    if not check: return {'exit':p.returncode, 'stdout':stdout, 'stderr':stderr}
    text = (stdout+stderr).decode('utf-8',errors='replace')
    require(p.returncode == 0, label+' failed; retained logs: '+str(logs)+'\n'+text[-2500:])
    return text


def nix_command():
    return shutil.which('nix-build') or '/nix/var/nix/profiles/default/bin/nix-build'


def host(check_daemon=True):
    import platform
    require(platform.system() == 'Linux' and platform.machine() == 'aarch64', 'requires isolated reviewed ARM64 Linux Hono VM')
    nix = str(Path(nix_command()).parent/'nix')
    require(subprocess.check_output([nix,'--version'],text=True).strip().split()[-1] == '2.35.2', 'requires Nix 2.35.2 client')
    if not check_daemon: return
    info = json.loads(subprocess.check_output([nix,'--extra-experimental-features','nix-command','store','info','--store','daemon','--json'],text=True))
    require(info['version'] == '2.35.2', 'requires Nix 2.35.2 daemon')


def prepare(profile, destination):
    require(profile == 'hono', 'only exact Hono Linux preparation is reviewed here')
    destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'preparation destination already exists')
    require(not destination.resolve().is_relative_to(ROOT), 'artifacts must remain outside prototype source')
    destination.mkdir(parents=True)
    host()
    command([sys.executable,str(ROOT/'linux-hono/input-paths.py'),'--verify'],ROOT,None,destination,'inputs',limit=120)
    args = [nix_command(),str(ROOT/'linux-hono.nix'),'-A','environments.'+profile,
        '--out-link',str(destination/'result'),'--keep-failed','--option','sandbox','true',
        '--option','sandbox-fallback','false','--builders','','--max-jobs','1',
        '--option','substitute','true','--option','substituters','https://cache.nixos.org']
    command(args, ROOT, None, destination, 'prepare', limit=3600)
    # nix-build stdout contains exactly one output; stderr is logged separately.
    outputs = (destination/'prepare.stdout').read_text().splitlines()
    require(len(outputs) == 1, 'expected one sealed environment')
    bundle = Path(outputs[0]); require(bundle.parent == Path('/nix/store'), 'not a Nix output')
    spec = json.loads((bundle/'environment.json').read_text())
    require(spec['profile'] == profile, 'profile differs')
    verify(Path(spec['prepared'])/'workspace',spec['workspace_inventory'])
    verify(spec['store'],spec['store_inventory'])
    write_json(destination/'prepared.json', {'schema':1,'bundle':str(bundle),
        'manifest_sha256':digest(bundle/'environment.json'), 'profile':profile})
    return {'prepared':str(destination/'prepared.json'), 'source':spec['source'],
            'inputs':len(spec['inputs']), 'lifecycle':spec['lifecycle']}


def load_prepared(path):
    handle = json.loads(Path(path).read_text()); require(handle.get('schema') == 1, 'unsupported handle')
    bundle = Path(handle['bundle'])
    require(bundle.parent == Path('/nix/store') and bundle.is_dir() and not bundle.is_symlink(), 'expected immutable Nix output')
    require(digest(bundle/'environment.json') == handle['manifest_sha256'], 'prepared manifest corrupt')
    spec = json.loads((bundle/'environment.json').read_text())
    require(spec['schema'] in {1,2} and spec['platform'] == 'aarch64-linux' and spec['profile'] == 'hono' and
            spec['pnpm_version'] == '12.6.0' and spec['node_version'] == '24.18.0', 'unsupported environment')
    require(spec['profile'] == handle['profile'], 'profile differs')
    require(spec['hooks'] == [], 'this isolated Linux Hono qualification supports only the reviewed empty checkout-hook plan')
    for k,p in spec['tools'].items():
        require(digest(p) == spec['tool_hashes'][k], 'tool bytes differ: '+k)
    return spec


def environment(spec, state, store, offline=False):
    runtime = state/'runtime'
    for name in ['home','config','cache','state','data','pnpm-home','tmp','npm-cache','effects']:
        (runtime/name).mkdir(parents=True,exist_ok=True)
    auth = runtime/'empty-auth.npmrc'; auth.touch()
    require(auth.read_bytes() == b'', 'private auth file must remain empty')
    env = {'PATH':':'.join([str(Path(spec['tools'][k]).parent) for k in
           ['pnpm','launcher','node','only_allow','git','bash']]+['/usr/bin','/bin']),
        'HOME':str(runtime/'home'),'XDG_CONFIG_HOME':str(runtime/'config'),
        'XDG_CACHE_HOME':str(runtime/'cache'),'XDG_STATE_HOME':str(runtime/'state'),
        'XDG_DATA_HOME':str(runtime/'data'),'PNPM_HOME':str(runtime/'pnpm-home'),
        'TMPDIR':str(runtime/'tmp'),'npm_config_cache':str(runtime/'npm-cache'),
        'npm_config_prefix':spec['npm_prefix'],'LANG':'en_US.UTF-8','LC_ALL':'en_US.UTF-8',
        'CI':'true','NODE_OPTIONS':'--max-old-space-size=2048','TZ':'UTC','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null',
        'GIT_TERMINAL_PROMPT':'0','PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1','COREPACK_ENABLE_NETWORK':'0',
        'PNPM_DISABLE_SELF_UPDATE_CHECK':'1','PNPM_CONFIG_MANAGE_PACKAGE_MANAGER_VERSIONS':'false',
        'PNPM_CONFIG_NPMRC_AUTH_FILE':str(auth),'PNPM_CONFIG_STORE_DIR':str(store),
        'PNPM_CONFIG_PACKAGE_IMPORT_METHOD':'copy','PNPM_CONFIG_ENABLE_GLOBAL_VIRTUAL_STORE':'false',
        'PNPM_CONFIG_SIDE_EFFECTS_CACHE':'false','PNPM_CONFIG_VERIFY_STORE_INTEGRITY':'true',
        'PNPM_CONFIG_SCRIPT_SHELL':spec['tools']['bash'],'PNPM_CONFIG_OFFLINE':str(offline).lower(),
        'PNPM_CONFIG_PREFER_SYMLINKED_EXECUTABLES':'true','PNPM_CONFIG_FETCH_RETRIES':'0',
        'PNPM_CONFIG_FETCH_TIMEOUT':'15000','LIFECYCLE_LOG_DIR':str(runtime/'effects'),
        'MAINTENANCE_ZONE':'private-development'}
    # The exact local Hono profile retains stock default cmd shims.
    if spec['profile'] in {'hono','hono-experiment'}:
        env.pop('PNPM_CONFIG_PREFER_SYMLINKED_EXECUTABLES')
    return env


def discover(spec, checkout, env):
    p = subprocess.run([spec['tools']['pnpm'],'--recursive','list','--depth=-1','--json'],
                       cwd=checkout,env=env,capture_output=True,text=True,timeout=60,check=True)
    result = {'.'}
    for row in json.loads(p.stdout):
        project = Path(row['path']); require(project.resolve().is_relative_to(checkout), 'external workspace')
        rel = str(project.relative_to(checkout))
        if rel != '.': relative(rel)
        result.add(rel)
    return sorted(result)


def generated(projects, source_owned=()):
    return sorted(r for r in ('node_modules' if x == '.' else x+'/node_modules' for x in projects) if r not in source_owned)


def safe_destination(checkout, rel):
    relative(rel); p = checkout/rel
    for ancestor in [p, *p.parents]:
        require(not ancestor.is_symlink(), 'symlink activation path: '+str(ancestor))
        if ancestor == checkout: break
    return p


@contextmanager
def locked(checkout, state):
    checkout, state = Path(checkout).resolve(), Path(state).resolve()
    require(checkout.is_dir() and not checkout.is_relative_to(Path('/nix/store')), 'checkout must be mutable')
    require(not state.is_relative_to(checkout) and not checkout.is_relative_to(state) and
            not state.is_relative_to(ROOT) and not state.is_relative_to(Path('/nix/store')), 'state must be outside checkout, prototype and Nix outputs')
    state.mkdir(parents=True,exist_ok=True)
    marker = checkout/'.pnpmnix-state.json'
    require(not marker.is_symlink(), 'checkout state marker is a symlink')
    # One persistent binding and lock per checkout also exclude different state
    # directories. The marker is an owned, untracked file; source files stay intact.
    with marker.open('a+') as f, (state/'lock').open('a') as state_lock:
        try:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(state_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another activation/stock command owns this checkout/state')
        f.seek(0); content = f.read()
        expected = {'schema':1,'state':str(state),'checkout':str(checkout)}
        if content: require(json.loads(content) == expected, 'checkout is bound to another state or marker is not owned')
        else:
            json.dump(expected,f); f.write('\n'); f.flush(); os.fsync(f.fileno())
        binding = state/'checkout.json'
        if binding.exists(): require(json.loads(binding.read_text()) == {'checkout':str(checkout)}, 'state belongs to another checkout')
        else: write_json(binding,{'checkout':str(checkout)})
        yield checkout,state


def validate_active(active, checkout, state):
    require(active.get('schema') == 1 and active.get('checkout') == str(checkout), 'active state does not match checkout')
    attempt = Path(active['attempt']); store = Path(active['store'])
    require(attempt.parent == state/'attempts' and not attempt.is_symlink() and
            store == attempt/'store' and store.is_dir() and not store.is_symlink(), 'active store is outside private attempt')
    require(isinstance(active['owned'],list) and len(set(active['owned'])) == len(active['owned']), 'invalid generated-directory ownership')
    for rel in active['owned']:
        parts = relative(rel).parts
        require(parts[-1] == 'node_modules' and '.git' not in parts and parts.count('node_modules') == 1,
                'invalid generated dependency root: '+rel)


def configuration_guard(spec, checkout, env):
    # A missing root workspace would let native pnpm search outside this root.
    root = safe_destination(checkout,'pnpm-workspace.yaml')
    require(root.is_file(), 'root workspace configuration is required')
    for name in ['.npmrc','.pnpmfile.cjs','.pnpmfile.mjs']:
        p = safe_destination(checkout,name)
        if p.exists():
            require(name in spec['inputs'] and p.is_file() and digest(p) == spec['inputs'][name],
                    'undeclared/changed auth or executable configuration: '+name)
    if 'protected_configuration' not in spec:
        # Retain compatibility with existing immutable handles. Only the
        # consumed frozen configuration is read, without executing hooks.
        source = Path(spec['source'])
        for rel in ['pnpm-workspace.yaml','.npmrc']:
            p = safe_destination(source,rel)
            if p.exists(): require(rel in spec['inputs'] and digest(p) == spec['inputs'][rel], 'frozen configuration differs')
        spec['protected_configuration'] = protected_configuration(native_configuration(spec['tools']['pnpm'],source,env))
    current = protected_configuration(native_configuration(spec['tools']['pnpm'],checkout,env))
    require(current == spec['protected_configuration'],
            'build policy, access or managed scope changed; separate review required')


def matching(spec, checkout, env, owned=()):
    for rel,sha in spec['inputs'].items():
        p = safe_destination(checkout,rel)
        require(p.is_file() and not p.is_symlink() and digest(p) == sha, 'preparation input mismatch: '+rel)
    configuration_guard(spec,checkout,env)
    projects = discover(spec,checkout,env)
    require(projects == spec['projects'], 'workspace configuration/discovery differs')
    expected_configuration = spec['configuration'] if spec['schema'] == 2 else configuration_paths(spec['source'],spec['projects'])
    require(configuration_paths(checkout,projects) == expected_configuration,
            'consumed configuration/manifest topology differs')


def verify_dependencies(spec, checkout, store):
    expected = spec['workspace_inventory']
    metadata = {'node_modules/.modules.yaml','node_modules/.pnpm-workspace-state-v1.json'}
    allowed_new = 'node_modules/.pnpm-task-run-state-v1'
    current = inventory(checkout, omit=('.git',))
    wanted = {r:v for r,v in expected.items() if not r.startswith(allowed_new) and any(r == x or r.startswith(x+'/') for x in spec['generated'])}
    actual = {r:v for r,v in current.items() if any(r == x or r.startswith(x+'/') for x in spec['generated'])}
    require(set(actual)-set(wanted) <= {r for r in actual if r == allowed_new or r.startswith(allowed_new+'/')}, 'unexpected dependency entries')
    for rel,row in wanted.items():
        if rel not in metadata: require(actual.get(rel) == row, 'restored dependency differs: '+rel)
    old = json.loads((Path(spec['prepared'])/'workspace/node_modules/.modules.yaml').read_text())
    new = json.loads((checkout/'node_modules/.modules.yaml').read_text())
    differences = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    require(differences <= {'storeDir','pendingBuilds','ignoredBuilds'}, 'unexpected module metadata change')
    require(Path(new['storeDir']).resolve().is_relative_to(store), 'metadata does not use private store')
    old = json.loads((Path(spec['prepared'])/'workspace/node_modules/.pnpm-workspace-state-v1.json').read_text())
    new = json.loads((checkout/'node_modules/.pnpm-workspace-state-v1.json').read_text())
    producer = str(Path(spec['prepared'])/'workspace')
    require(all(k == producer or k.startswith(producer+'/') for k in old['projects']), 'unexpected prepared workspace state')
    relocated = {str(checkout)+k[len(producer):]:v for k,v in old['projects'].items()}
    require(isinstance(new['lastValidatedTimestamp'],int) and new['lastValidatedTimestamp'] >= old['lastValidatedTimestamp'], 'invalid native validation timestamp')
    require(new.get('pnpmfiles') == [], 'acquisition pnpmfile leaked into development')
    require(new == {**old,'projects':relocated,'pnpmfiles':[],
        'lastValidatedTimestamp':new['lastValidatedTimestamp']}, 'unexpected native workspace state')
    for rel,row in actual.items():
        p = checkout/rel
        if row['type'] == 'link': require(p.resolve(strict=True).is_relative_to(checkout), 'external dependency link: '+rel)
        if row['type'] == 'file':
            data = p.read_bytes()
            require(producer.encode() not in data and spec['store'].encode() not in data, 'immutable producer reference: '+rel)
            require(p.stat().st_mode & 0o200, 'dependency file not writable: '+rel)
    verify_task_state(checkout)


def verify_task_state(checkout):
    import re
    task = checkout/'node_modules/.pnpm-task-run-state-v1'
    if not task.exists(): return
    require(task.is_dir() and not task.is_symlink(), 'task state is not a directory')
    latest = task/'latest.json'
    require(latest.is_file() and not latest.is_symlink(), 'task state has no regular latest.json')
    row = json.loads(latest.read_text())
    require(set(row) == {'version','invocation','run'} and row['version'] == 1 and
        re.fullmatch('[0-9a-f]{64}',row['invocation']) and re.fullmatch('[0-9a-f]{12}-[0-9]+-[0-9]+',row['run']), 'unsupported native task state')
    finished = row['invocation']+'.'+row['run']+'.finished'
    require({p.name for p in task.iterdir()} == {'latest.json',finished}, 'unexpected native task files')
    for p in task.iterdir():
        require(p.is_file() and not p.is_symlink() and not p.stat().st_mode & 0o111, 'unsafe native task file')
    require((task/finished).stat().st_size == 0, 'native finished marker is not empty')


def restore_payload(spec, checkout):
    # Native pnpm owns the relocated graph and state. Reapply only declared
    # preparation deltas; do not update its indexes or build completion flags.
    changes = spec['payload_changes']
    actual = inventory(checkout,omit=('.git',))
    expected = spec['workspace_inventory']
    metadata = {'node_modules/.modules.yaml','node_modules/.pnpm-workspace-state-v1.json'}
    for rel,row in expected.items():
        if rel.startswith('node_modules/.pnpm-task-run-state-v1') or not any(rel == x or rel.startswith(x+'/') for x in spec['generated']): continue
        if rel not in changes and rel not in metadata:
            require(actual.get(rel) == row, 'native linked payload/layout differs: '+rel)
    for rel,row in sorted(changes.items(),key=lambda x:(len(Path(x[0]).parts),x[0])):
        p = safe_destination(checkout,rel)
        require(not p.is_symlink(), 'unsafe prepared payload destination: '+rel)
        if row['type'] == 'directory': p.mkdir(exist_ok=True)
        else:
            require(not p.exists() or p.is_file(), 'payload destination is not a regular file')
            temporary = p.with_name('.pnpmnix-payload-'+p.name)
            require(not temporary.exists() and not temporary.is_symlink(), 'payload temporary path exists')
            shutil.copy2(Path(spec['prepared'])/'workspace'/rel,temporary)
            temporary.chmod(temporary.stat().st_mode|0o200); temporary.replace(p)


def rollback(checkout, state):
    pending = state/'pending.json'
    require(pending.exists(), 'no interrupted activation to recover')
    journal = json.loads(pending.read_text()); attempt = Path(journal['attempt'])
    require(attempt.parent == state/'attempts', 'unsafe activation journal')
    for rel in reversed(journal['roots']):
        p = safe_destination(checkout,rel); backup = attempt/'previous'/rel
        if backup.exists() or (rel in journal['installing'] and not journal['original'][rel]):
            if p.exists():
                failed = attempt/'failed'/rel; failed.parent.mkdir(parents=True,exist_ok=True); p.rename(failed)
            if backup.exists(): p.parent.mkdir(parents=True,exist_ok=True); backup.rename(p)
    active = state/'active.json'
    if journal['previous'] is not None: write_json(active,journal['previous'])
    elif active.exists(): active.rename(attempt/'uncommitted-active.json')
    pending.rename(attempt/'rolled-back.json')
    return {'recovered':True,'retained':str(attempt),'checkout_effects':'may need repair if hooks had started; dependency moves rolled back'}


def restore(handle, checkout, state, run_hooks=False):
    with locked(checkout,state) as (checkout,state):
        require(not (state/'pending.json').exists(), 'interrupted activation; run recover before restore or pnpm')
        spec = load_prepared(handle); active_path = state/'active.json'
        previous = json.loads(active_path.read_text()) if active_path.exists() else None
        if previous is not None: validate_active(previous,checkout,state)
        attempt = state/'attempts'/uuid.uuid4().hex; attempt.mkdir(parents=True)
        store = attempt/'store'; env = environment(spec,state,store,offline=True)
        matching(spec,checkout,env,(previous or {}).get('owned',[]))
        roots = sorted(set(spec['generated']) | set(previous['owned'] if previous else []))
        for rel in roots:
            p = safe_destination(checkout,rel)
            require(not p.exists() or (previous is not None and rel in previous['owned']), 'unowned dependency directory: '+rel)
        if run_hooks and spec['hooks']:
            require((checkout/'.git').is_dir() and not (checkout/'.git').is_symlink(), 'checkout hooks require a normal Git checkout; Git worktree indirection is unsupported')
            safe_destination(checkout,'.git/hooks/pre-commit')
            hooks_path = subprocess.run([spec['tools']['git'],'config','--local','--get','core.hooksPath'],
                cwd=checkout,env=env,capture_output=True,text=True,timeout=30)
            require(hooks_path.returncode == 1, 'custom Git hooksPath is unsupported')
        original_roots = {r:(checkout/r).exists() for r in roots}
        hook = checkout/'.git/hooks/pre-commit'
        if run_hooks and spec['hooks'] and hook.exists():
            require(previous is not None and previous.get('hook_sha256') == digest(hook), 'existing checkout hook is not owned by this activation')
        verify(Path(spec['prepared'])/'workspace',spec['workspace_inventory']); verify(spec['store'],spec['store_inventory'])
        bytes_needed = sum(x.get('bytes',0) for x in spec['workspace_inventory'].values()) + sum(x.get('bytes',0) for x in spec['store_inventory'].values())
        free_guard(state,bytes_needed)
        copy_private(Path(spec['prepared'])/'workspace',attempt/'workspace',lambda:free_guard(state))
        copy_private(spec['store'],store,lambda:free_guard(state))
        verify(attempt/'workspace',spec['workspace_inventory']); verify(store,spec['store_inventory'])
        task_state = attempt/'workspace/node_modules/.pnpm-task-run-state-v1'
        if task_state.exists(): task_state.rename(attempt/'prepared-task-state')
        matching(spec,checkout,env,(previous or {}).get('owned',[]))
        for rel in roots:
            p = safe_destination(checkout,rel)
            require(p.exists() == original_roots[rel], 'dependency directory changed during staging: '+rel)
        protected = inventory(checkout,omit=tuple(roots)+('.git',))
        journal = {'attempt':str(attempt),'roots':roots,'original':original_roots,
                   'installing':[],'previous':previous}
        write_json(state/'pending.json',journal)
        try:
            for rel in roots:
                p = checkout/rel
                if p.exists():
                    backup = attempt/'previous'/rel; backup.parent.mkdir(parents=True,exist_ok=True); p.rename(backup)
                if rel in spec['generated'] and (attempt/'workspace'/rel).exists():
                    journal['installing'].append(rel); write_json(state/'pending.json',journal)
                    p.parent.mkdir(parents=True,exist_ok=True); (attempt/'workspace'/rel).rename(p)
            text = command([spec['tools']['pnpm'],'install','--recursive','--offline','--frozen-lockfile',
                '--trust-lockfile','--ignore-scripts','--reporter=ndjson'],checkout,env,attempt,'link')
            events = []
            for line in text.splitlines():
                try: row = json.loads(line)
                except ValueError: continue
                if isinstance(row,dict): events.append(row)
            require(any(x.get('name') == 'pnpm:execution-time' for x in events), 'missing reporter control')
            require(not any(x.get('name') == 'pnpm:lifecycle' for x in events), 'unexpected lifecycle replay during restore')
            matching(spec,checkout,env); restore_payload(spec,checkout); verify_dependencies(spec,checkout,store)
            if run_hooks and spec['hooks']:
                for i, task in enumerate(spec['hooks']):
                    cwd = checkout if task['project'] == '.' else checkout/relative(task['project'])
                    if task.get('original_body'):
                        body = json.loads((cwd/'package.json').read_text())['scripts'][task['event']]
                        hook_env = {**env,'npm_config_user_agent':'pnpm/12.6.0 npm/? node/v24.18.0 darwin arm64','npm_execpath':spec['tools']['pnpm']}
                        args = [spec['tools']['bash'],'-c',body]
                    else:
                        hook_env = env
                        args = [spec['tools']['pnpm'],'--config.verify-deps-before-run=false','run',task['event']]
                    command(args,cwd,hook_env,attempt,'checkout-hook-'+str(i))
                verify_dependencies(spec,checkout,store)
                require(hook.is_file() and not hook.is_symlink() and hook.stat().st_mode & 0o111, 'checkout hook effect missing')
                expected_hook = 'pnpm exec lint-staged --concurrent false' if spec['profile'] == 'vite' else '# fixture-owned activation private-development'
                require(expected_hook in hook.read_text(), 'checkout hook effect differs')
            require(inventory(checkout,omit=tuple(roots)+('.git',)) == protected, 'protected checkout sources changed during activation')
            verify(Path(spec['prepared'])/'workspace',spec['workspace_inventory']); verify(spec['store'],spec['store_inventory'])
            # Only empty, previously owned workspace directories can disappear.
            for rel in roots:
                parent = (checkout/rel).parent
                if rel not in spec['generated'] and parent != checkout and parent.is_dir() and not any(parent.iterdir()): parent.rmdir()
            result = {'schema':1,'checkout':str(checkout),'prepared':str(Path(handle).resolve()),
                'profile':spec['profile'],'store':str(store),'owned':spec['generated'],
                'mode':'prepared','checkout_hooks':'completed' if run_hooks else 'pending',
                'lifecycle':spec['lifecycle'],'attempt':str(attempt),
                'hook_sha256':digest(hook) if run_hooks and spec['hooks'] and hook.is_file() else (previous or {}).get('hook_sha256')}
            write_json(state/'active.json',result)
            (state/'pending.json').rename(attempt/'activated.json')
            return result
        except BaseException:
            rollback(checkout,state)
            raise


def maintenance_projects(spec, checkout, env):
    configuration_guard(spec,checkout,env)
    projects = discover(spec,checkout,env)
    for rel in configuration_paths(checkout,projects):
        # Native workspace/manifest/lock edits are mutable. Auth, executable
        # config and nested workspace contexts still require reviewed bytes.
        if rel in {'pnpm-workspace.yaml','pnpm-lock.yaml'} or Path(rel).name == 'package.json': continue
        p = safe_destination(checkout,rel)
        require(rel in spec['inputs'] and p.is_file() and digest(p) == spec['inputs'][rel],
                'undeclared/changed auth, executable or nested configuration: '+rel)
    return projects


def prepared_drift(spec, checkout, projects):
    changed = []
    for rel,sha in spec['inputs'].items():
        try:
            p = safe_destination(checkout,rel)
            same = p.is_file() and digest(p) == sha
        except (ValueError,OSError): same = False
        if not same: changed.append(rel)
    return {'refresh_required':bool(changed) or projects != spec['projects'],
            'changed_inputs':sorted(changed), 'workspace_projects_changed':projects != spec['projects']}


class PnpmCommandError(ValueError):
    def __init__(self, result):
        self.result = result
        super().__init__('native pnpm exited '+str(result['exit_code'])+'; retained logs: '+result['logs'])


def stock(checkout,state,args,offline=False):
    with locked(checkout,state) as (checkout,state):
        require(not (state/'pending.json').exists(), 'interrupted activation; run recover')
        require((state/'active.json').exists(), 'restore a matching prepared environment first')
        active = json.loads((state/'active.json').read_text()); validate_active(active,checkout,state)
        spec = load_prepared(active['prepared'])
        require(active['profile'] == spec['profile'], 'active profile differs from prepared handle')
        require(args, 'supply a stock pnpm command after --')
        # Keep this wrapper local; alternative/global stores and working roots are unsupported.
        import re
        forbidden = {'storedir','global','globaldir','globalbindir','dir','prefix','virtualstoredir',
            'modulesdir','lockfiledir','enableglobalvirtualstore','packageimportmethod','npmrcauthfile',
            'pnpmfile','globalpnpmfile','userconfig','globalconfig','managepackagemanagerversions','usenodeversion',
            'config','configdependencies','ignorepnpmfile','allowbuild','workspacepackages'} | {re.sub(r'[^a-z]','',k.lower()) for k in PROTECTED}
        for arg in args:
            key = re.sub(r'[^a-z]','',arg.split('=',1)[0].lower().removeprefix('--config.').removeprefix('--'))
            require(key not in forbidden and not (key.startswith('no') and key[2:] in forbidden) and
                not key.endswith('registry') and not arg.startswith('-C') and
                (not arg.startswith('-') or arg.startswith('--') or arg in ('-r','-w','-D','-P','-E','-O','-h','-v')),
                'stock argument overrides private/local scope or uses unsupported compact flags')
        # Installation/configuration of global tools is outside this local command flow.
        require(not any(x in args for x in ['setup','self-update','env','config','dlx','create','link','deploy',
                                         'approve-builds','with','runtime','rt']),
                'unsupported stock command in local scope')
        env = environment(spec,state,Path(active['store']),offline)
        projects = maintenance_projects(spec,checkout,env)
        for rel in generated(projects,spec.get('source_owned',[])):
            p = safe_destination(checkout,rel)
            require(not p.exists() or rel in active['owned'], 'unowned dependency directory: '+rel)
        active['owned'] = sorted(set(active['owned']) | set(generated(projects,spec.get('source_owned',[]))))
        active['mode'] = 'mutable'; active['checkout_hooks'] = 'not-asserted-after-stock'
        write_json(state/'active.json',active)
        logs = state/'commands'/uuid.uuid4().hex; logs.mkdir(parents=True)
        native = command([spec['tools']['pnpm'],*args],checkout,env,logs,'pnpm',check=False)
        sys.stdout.flush(); sys.stderr.flush()
        sys.stdout.buffer.write(native['stdout']); sys.stderr.buffer.write(native['stderr'])
        sys.stdout.buffer.flush(); sys.stderr.buffer.flush()
        warnings = []
        try:
            projects = maintenance_projects(spec,checkout,env)
            active['owned'] = sorted(set(active['owned']) | set(generated(projects,spec.get('source_owned',[]))))
        except (ValueError,OSError,subprocess.SubprocessError) as error:
            # Do not turn a completed native mutation into a wrapper failure.
            # The same preflight will block the next invocation if necessary.
            warnings.append('post-command inspection needs review: '+str(error))
        active['prepared_state'] = prepared_drift(spec,checkout,projects)
        if warnings: active['prepared_state']['refresh_required'] = True
        result = {'stock':True,'exit_code':native['exit'],'logs':str(logs),'store':active['store'],
                  'mode':'mutable','prepared_state':active['prepared_state'],'warnings':warnings}
        try:
            write_json(state/'active.json',active)
        except OSError as error: warnings.append('state receipt could not be saved: '+str(error))
        try: write_json(logs/'outcome.json',result)
        except OSError as error: warnings.append('command receipt could not be saved: '+str(error))
        if native['exit'] != 0: raise PnpmCommandError(result)
        return result
