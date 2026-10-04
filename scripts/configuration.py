"""Configuration boundaries for the pinned native pnpm reader, not a YAML parser."""
import json
from pathlib import Path
import subprocess
from trees import require

# These decisions remain reviewed; ordinary graph/catalog/release-age exclusion
# edits belong to pnpm. CLI overrides of these decisions are rejected as well.
PROTECTED = {
    'allowBuilds', 'dangerouslyAllowAllBuilds', 'strictDepBuilds',
    'onlyBuiltDependencies', 'neverBuiltDependencies', 'ignoredBuiltDependencies',
    'trustPolicy', 'trustPolicyExclude', 'trustPolicyIgnoreAfter',
    'minimumReleaseAge', 'minimumReleaseAgeStrict', 'minimumReleaseAgeIgnoreMissingTime',
    'trustLockfile', 'verifyStoreIntegrity',
    'registry', 'registries', 'strictSsl', 'ca', 'cafile', 'cert', 'key',
    'modulesDir', 'virtualStoreDir', 'lockfileDir', 'virtualStoreType',
    'useNodeVersion', 'nodeVersion', 'globalDir', 'globalBinDir',
    'pmOnFail', 'runtimeOnFail',
    'extraEnv', 'extraBinPaths', 'scriptShell',
    'configDir', 'stateDir', 'cacheDir', 'ignoreWorkspace',
}


def native_configuration(pnpm, root, env):
    # In 12.6.0 config:list dispatch calls the data-only config loader directly,
    # without prepare_config, pnpmfile hooks or config-dependency installation.
    p = subprocess.run([pnpm, 'config', 'list', '--json'], cwd=root, env=env,
                       capture_output=True, text=True, timeout=60)
    require(p.returncode == 0, 'native configuration read failed: '+p.stderr[-1500:])
    result = json.loads(p.stdout)
    require(isinstance(result, dict), 'unexpected native configuration view')
    return result


def protected_configuration(config):
    require(not any(config.get(k) for k in ['pnpmfile', 'globalPnpmfile', 'configDependencies']),
            'executable configuration composition requires separate review')
    return {k:v for k,v in config.items() if k in PROTECTED or k.endswith(':registry')}


def configuration_paths(root, projects):
    # Actual workspace manifests, the complete root lock, and the nearest
    # workspace configuration used by each project/its install children.
    # A package.json in dist, a template or a fixture is not a workspace member.
    root = Path(root)
    result = {'pnpm-lock.yaml'}
    for project in projects:
        directory = root if project == '.' else root/project
        result.add(str((directory/'package.json').relative_to(root)))
        context = directory
        while context != root and not (context/'pnpm-workspace.yaml').exists():
            context = context.parent
        for name in ['pnpm-workspace.yaml', '.npmrc', '.pnpmfile.cjs', '.pnpmfile.mjs']:
            p = context/name
            if p.exists() or p.is_symlink(): result.add(str(p.relative_to(root)))
    return sorted(result)
