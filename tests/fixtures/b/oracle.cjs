const fs=require('node:fs'), path=require('node:path'), a=require('node:assert/strict');
const {createRequire}=require('node:module');const root=__dirname;
const manifest=require('./package.json');const app=createRequire(path.join(root,'packages/app/package.json'));
const plugin=createRequire(path.join(root,'packages/plugin/package.json'));
a.equal(require('react').version,'19.3.0');a.equal(app('react').version,'19.3.0');a.equal(plugin('react').version,'19.3.0');
a.equal(app('@maintenance/lib').value,42);a.equal(app('@maintenance/plugin').react,'19.3.0');
a.equal(require('is-number').maintenancePatch,'verified-patch');a.equal(require('is-number')('12'),true);
a.equal(require('semver/package.json').version,manifest.dependencies.semver);
a.match(require('esbuild').transformSync('const n: number = 1',{loader:'ts'}).code,/const n = 1/);
const appManifest=JSON.parse(fs.readFileSync(path.join(root,'packages/app/package.json'),'utf8'));
if(appManifest.dependencies.picocolors) a.equal(app('picocolors/package.json').version,appManifest.dependencies.picocolors);
const expected={react:'19.3.0',semver:manifest.dependencies.semver,esbuild:require('esbuild').version,patch:true,
 lib:42,peer:true,appPicocolors:appManifest.dependencies.picocolors || null};
console.log(JSON.stringify(expected));
