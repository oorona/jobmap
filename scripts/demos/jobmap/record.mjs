import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium,expect}=require('../../../frontend/node_modules/@playwright/test');
const out='artifacts/jobmap-demo-work';
const scenes=JSON.parse(await fs.readFile('scripts/demos/jobmap/scenes.json','utf8'));
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({colorScheme:'dark',viewport:{width:1600,height:1100},recordVideo:{dir:`${out}/raw`,size:{width:1600,height:1100}}});
const page=await context.newPage();const marks=[],errors=[],inference=[];let matchedCount=0;
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.url().endsWith('/api/search/refine')&&r.method()==='POST')inference.push({at:new Date().toISOString()});});
const started=Date.now();
const button=name=>page.getByRole('button',{name,exact:true});
async function scroll(selector){await page.evaluate(selector=>window.scrollTo({top:document.querySelector(selector).getBoundingClientRect().top+window.scrollY-24,behavior:'smooth'}),selector);await page.waitForTimeout(750);}
async function scene(id,action){
 const narration=scenes.find(s=>s.id===id);const audio=JSON.parse(await fs.readFile(`${out}/${id}.json`,'utf8'));
 const start=(Date.now()-started)/1000;console.log('scene',id,'audio seconds',audio.seconds);
 await page.waitForTimeout(600);await action();await page.screenshot({path:`${out}/${id}.png`});
 const elapsed=(Date.now()-started)/1000-start;
 await page.waitForTimeout(Math.max(0,(audio.seconds+2-elapsed)*1000));
 marks.push({id,start,end:(Date.now()-started)/1000,audioSeconds:audio.seconds,text:narration.text,url:page.url()});
}
try{
 await page.goto('https://jobmap.home.iktdts.com/',{waitUntil:'networkidle'});
 await page.locator('.bubble').first().waitFor();
 assert.equal(await page.locator('.demo-banner').count(),0);
 await scene('intro',async()=>{await page.waitForTimeout(3500);await page.getByRole('textbox',{name:'Search jobs'}).focus();});
 await scene('search',async()=>{
  const response=page.waitForResponse(r=>r.url().endsWith('/api/search/refine')&&r.request().method()==='POST',{timeout:35000});
  await page.getByRole('textbox',{name:'Search jobs'}).pressSequentially('I want to build AI agents',{delay:115});
  const reply=await response;const judgment=await reply.json();assert.equal(reply.status(),200);assert.equal(judgment.available,true);
  await page.getByText('Refined with Jev',{exact:true}).waitFor();
  matchedCount=await page.locator('.job-row').count();assert(matchedCount>0&&matchedCount<=30);
  await expect(page.locator('.job-row').filter({hasText:'Agent Builder'})).toHaveCount(1);
  await fs.writeFile(`${out}/search-verification.json`,JSON.stringify({query:'I want to build AI agents',generation:judgment.generation,catalogVersion:judgment.catalog_version,matches:matchedCount,scores:judgment.results.map(r=>({id:r.id,relevance:r.relevance}))},null,2));
  await page.waitForTimeout(1800);await scroll('.discovery');
 });
 await scene('results',async()=>{
  await page.locator('.bubble').first().hover();await page.waitForTimeout(5500);
  await page.mouse.move(20,20);await scroll('.results-heading');await page.waitForTimeout(1800);
 });
 await scene('evidence',async()=>{
  await page.locator('.job-row').filter({hasText:'Agent Builder'}).locator('.job-main').click();
  await page.getByRole('heading',{name:'Evidence',exact:true}).waitFor();await page.waitForTimeout(8500);
  await page.getByRole('heading',{name:'Evidence',exact:true}).evaluate(el=>el.scrollIntoView({behavior:'smooth',block:'start'}));
  await page.waitForTimeout(1500);assert(await page.locator('.drawer blockquote').count()>0);
 });
 await scene('filters',async()=>{
  await button('Close details').click();await scroll('.simple-filters');await page.waitForTimeout(2200);
  const before=inference.length;await page.getByLabel('Work type',{exact:true}).selectOption('remote');
  await page.waitForTimeout(1500);assert(await page.locator('.job-row').count()>0);
  await page.getByLabel('Minimum pay',{exact:true}).focus();await page.waitForTimeout(3000);
  assert.equal(inference.length,before);await button('Clear filters').click();
 });
 await scene('costs',async()=>{
  await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));await page.waitForTimeout(650);
  await button('Usage & costs').click();await page.getByRole('region',{name:'Jev costs'}).getByText('Today',{exact:false}).waitFor();
  await expect(page.getByRole('region',{name:'Job discovery'})).toHaveCount(0);
  await fs.writeFile(`${out}/usage-at-capture.json`,JSON.stringify(await page.evaluate(async()=>await (await fetch('/api/usage')).json()),null,2));
 });
 assert.equal(inference.length,1);assert.deepEqual(errors,[]);
}finally{
 await fs.writeFile(`${out}/capture.json`,JSON.stringify({source:'https://jobmap.home.iktdts.com',capturedAt:new Date().toISOString(),colorScheme:'dark',viewport:{width:1600,height:1100},kind:'Real browser interactions, live MexicoDev data and live Jev judgments; no substituted responses; playback at original speed',query:'I want to build AI agents',matchedCount,inferenceCalls:inference.length,errors,marks},null,2));
 const video=page.video();await context.close();await video.saveAs(`${out}/raw.webm`);await browser.close();
}
console.log(JSON.stringify({recorded:true,scenes:marks.length,matchedCount,inferenceCalls:inference.length}));
