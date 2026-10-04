const assert = require('node:assert/strict');
const fs = require('node:fs');
const map = JSON.parse(fs.readFileSync(process.env.VITE_RAW_ARCHIVE_MAP, 'utf8'));
const trace = process.env.VITE_RAW_FETCH_TRACE;
const inventory = process.env.VITE_LOCKED_SOURCE_INVENTORY
  ? JSON.parse(fs.readFileSync(process.env.VITE_LOCKED_SOURCE_INVENTORY, 'utf8')) : {directories: {}};
const directories = new Set(Object.values(inventory.directories));
function entry(pkgId, resolution) {
  const found = map[pkgId];
  assert.ok(found, `UNDECLARED_RAW_SOURCE: ${pkgId}`);
  assert.equal(resolution.integrity, found.integrity, `RAW_MAP_INTEGRITY_MISMATCH: ${pkgId}`);
  if (resolution.tarball) assert.equal(resolution.tarball, found.originalUrl, `RAW_MAP_URL_MISMATCH: ${pkgId}`);
  assert.ok(fs.existsSync(found.archive), `MISSING_RAW_ARCHIVE: ${pkgId}`);
  return found;
}
module.exports = { fetchers: [{
  canFetch(pkgId, resolution) {
    if (resolution.type === 'directory') {
      assert.ok(directories.has(resolution.directory) && pkgId === 'file:' + resolution.directory,
        `UNDECLARED_DIRECTORY_SOURCE: ${pkgId}`);
      fs.appendFileSync(trace, JSON.stringify({event: 'native-directory-delegation',
        pkgId, directory: resolution.directory}) + '\n');
      return false;
    }
    entry(pkgId, resolution); return true;
  },
  async fetch(cafs, resolution, opts, fetchers) {
    const pkgId = `${opts.pkg.name}@${opts.pkg.version}`;
    const found = entry(pkgId, resolution), started = performance.now();
    fs.appendFileSync(trace, JSON.stringify({event: 'native-extract-start', pkgId,
      archive: found.archive, integrity: resolution.integrity}) + '\n');
    const result = await fetchers.localTarball(cafs,
      {tarball: 'file:' + found.archive, integrity: resolution.integrity}, opts);
    const manifest = JSON.parse(fs.readFileSync(result.filesMap.get('package.json'), 'utf8'));
    assert.equal(`${manifest.name}@${manifest.version}`, pkgId, 'RAW_MANIFEST_ID_MISMATCH');
    fs.appendFileSync(trace, JSON.stringify({event: 'native-extract-end', pkgId,
      milliseconds: performance.now() - started, fileCount: result.filesMap.size,
      scripts: Object.keys(manifest.scripts || {})}) + '\n');
    return result;
  }
}] };
