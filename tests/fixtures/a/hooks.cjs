const fs=require('node:fs'), path=require('node:path');
const root=__dirname, phase=process.argv[2], zone=process.env.MAINTENANCE_ZONE || 'unclassified';
const dir=process.env.LIFECYCLE_LOG_DIR || path.join(root,'.lifecycle');fs.mkdirSync(dir,{recursive:true});
let head=null;const headFile=path.join(root,'.git/HEAD');if(fs.existsSync(headFile)) head=fs.readFileSync(headFile,'utf8').trim();
const row={phase,zone,cwd:process.cwd(),root,head};
fs.appendFileSync(path.join(dir,'events.jsonl'),JSON.stringify(row)+'\n');
if(phase==='root-postinstall' && fs.existsSync(path.join(root,'.git/hooks'))) {
 const body='#!/bin/sh\n# fixture-owned activation '+zone+' '+head+'\nexit 0\n';
 fs.writeFileSync(path.join(root,'.git/hooks/pre-commit'),body,{mode:0o755});
}
console.log(JSON.stringify(row));
