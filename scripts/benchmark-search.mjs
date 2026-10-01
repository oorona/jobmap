import {readFileSync,writeFileSync} from 'node:fs';
import {search} from '../frontend/lib/search.ts';
const fixture=JSON.parse(readFileSync(new URL('../frontend/fixtures/jobs.json',import.meta.url)));
const rows=Array.from({length:10000},(_,i)=>({...fixture[i%fixture.length],id:String(i),source_posted_at:new Date(Date.now()-86400000).toISOString(),expires_at:new Date(Date.now()+86400000).toISOString()}));
const samples=[];
for(let i=0;i<30;i++){const start=performance.now();search(rows,'python remote',{remote:false,country:'',weights:{}});samples.push(performance.now()-start);}
samples.sort((a,b)=>a-b);
const result={records:rows.length,samples:samples.length,p95_ms:samples[Math.ceil(samples.length*.95)-1],runtime:process.version};
writeFileSync('artifacts/search-benchmark.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
if(result.p95_ms>=100)process.exitCode=1;
