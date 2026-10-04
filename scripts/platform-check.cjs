/* Independently enumerate Darwin/arm64-restricted packages from the wanted lock. */
const fs = require('node:fs');
const path = require('node:path');
const root = process.cwd();
const slots = fs.readdirSync(path.join(root, 'node_modules/.pnpm'));
const yamlSlot = slots.find(x => x === 'yaml@2.9.1');
if (!yamlSlot) throw Error('locked YAML reader absent');
const yaml = require(path.join(root,'node_modules/.pnpm',yamlSlot,'node_modules/yaml'));
const docs = yaml.parseAllDocuments(fs.readFileSync('pnpm-lock.yaml','utf8')).map(d => d.toJSON());
const lock = docs.find(d => d.importers?.['.']?.devDependencies);
if (!lock) throw Error('workspace dependency lock document absent');
const expected = Object.entries(lock.packages).filter(([, p]) =>
  p.os?.includes('darwin') && (!p.cpu || p.cpu.includes('arm64')));
if (!expected.length) throw Error('platform selection check empty');
const checked = expected.map(([key]) => {
  const i = key.lastIndexOf('@'), name = key.slice(0,i), version = key.slice(i+1);
  const slot = slots.find(x => x === key.replaceAll('/', '+') || x.startsWith(key.replaceAll('/', '+') + '('));
  if (!slot) throw Error('selected platform package missing: ' + key);
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'node_modules/.pnpm',slot,'node_modules',name,'package.json')));
  if (manifest.name !== name || manifest.version !== version) throw Error('platform identity differs: '+key);
  return key;
});
console.log(JSON.stringify({platform:'darwin-arm64', lock_platform_packages_checked:checked,
  scope:'all packages in the workspace lock document restricted to Darwin and compatible with arm64; not a universal optional graph solver'}));
