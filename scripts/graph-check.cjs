const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module');
const root = process.cwd();
const lock = require(path.join(root, 'node_modules/.pnpm/yaml@2.9.1/node_modules/yaml')).parseAllDocuments(fs.readFileSync('pnpm-lock.yaml', 'utf8'))[1].toJSON();
const checks = [];
for (const [name, version, peers] of [
  ['@vitejs/plugin-vue', '6.0.8', ['vue', 'vite']],
  ['eslint-plugin-import-x', '4.17.1', ['eslint']]
]) {
  const keys = Object.keys(lock.snapshots).filter(k => k.startsWith(name + '@' + version + '('));
  assert.equal(keys.length, 1, 'locked peer context ambiguous: ' + name);
  const directories = fs.readdirSync('node_modules/.pnpm').filter(k => k.startsWith(name.replace('/', '+') + '@' + version + '_'));
  assert.equal(directories.length, 1, 'installed peer context ambiguous: ' + name);
  const pkg = path.join(root, 'node_modules/.pnpm', directories[0], 'node_modules', name, 'package.json');
  const req = createRequire(pkg);
  assert.equal(JSON.parse(fs.readFileSync(pkg)).version, version);
  for (const peer of peers) {
    const resolved = fs.realpathSync(req.resolve(peer + '/package.json'));
    assert.ok(resolved.startsWith(root + path.sep), 'peer outside restored checkout');
    const wanted = lock.snapshots[keys[0]].dependencies[peer];
    const actual = JSON.parse(fs.readFileSync(resolved)).version;
    if (peer === 'vite') {
      assert.equal(wanted, 'link:packages/vite', 'wanted workspace peer differs');
      assert.equal(resolved, path.join(root, 'packages/vite/package.json'));
    } else assert.equal(actual, wanted.split('(')[0], 'peer version differs from wanted lock');
    checks.push({package: name, peer, wanted, actual, resolved});
  }
}
console.log(JSON.stringify({passed: true, checks}));
