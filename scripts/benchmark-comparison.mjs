// Run the same comparison endpoint as the UI; never infer accuracy from result counts.
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require('../frontend/node_modules/@playwright/test');
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 await page.goto(process.env.COMPARISON_URL??'https://jobmap.home.iktdts.com/',{waitUntil:'networkidle'});
 const queries=process.argv.slice(2);if(!queries.length)queries.push('I want to build robots');
 if(queries.length>3)throw new Error('Run at most three queries at a time to respect search rate limits');
 const observations=[];
 for(const query of queries){
  const result=await page.evaluate(async query=>{
   const catalog=await (await fetch('/api/catalog')).json();
   const response=await fetch('/api/search/compare',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'jev'},body:JSON.stringify({query,generation:1,catalog_version:catalog.version,preferences:{remote:false,country:'',weights:{}},days:45})});
   const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));return data;
  },query);
  observations.push({...result,recorded_at:new Date().toISOString()});
  console.log(JSON.stringify({query,corpus:result.corpus_size,methods:result.methods.map(m=>({id:m.id,available:m.available,reason:m.reason,returned:m.results.filter(r=>r.relevance>=(m.id==='jev'?.65:-1)).slice(0,10).length,elapsed_ms:Math.round(m.elapsed_ms),query_ms:m.query_ms,database_ms:m.database_ms,accuracy:'requires human relevance labels'}))}));
 }
 await mkdir('artifacts',{recursive:true});
 await writeFile('artifacts/comparison-benchmark.json',JSON.stringify({observations,note:'Timings are individual parallel runs, not latency percentiles. Results are unlabeled; counts do not measure accuracy.'},null,2));
 if(observations.some(r=>r.methods.some(m=>!m.available)))process.exitCode=1;
}finally{await browser.close();}
