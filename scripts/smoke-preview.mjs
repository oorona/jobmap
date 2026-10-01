import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('../frontend/node_modules/@playwright/test');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1280,height:1100}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
try{
 const response=await page.goto('https://jobmap.home.iktdts.com/',{waitUntil:'networkidle'});
 if(response.status()!==200)throw new Error(`HTTP ${response.status()}`);
 await page.locator('.job-row').first().waitFor();
 await page.locator('.bubble').first().waitFor();
 const catalog=await page.evaluate(async()=>await (await fetch('/api/catalog')).json());
 if(catalog.source_mode!=='live'||!catalog.jobs.length)throw new Error('Expected populated live catalog');
 if(await page.locator('.demo-banner').count())throw new Error('Fixture banner remains');
 const refined=page.waitForResponse(r=>r.url().includes('/api/search/refine')&&r.request().method()==='POST',{timeout:35000});
 await page.getByRole('textbox',{name:'Search jobs'}).fill(process.env.SMOKE_QUERY??'python');
 const refinementResponse=await refined;
 const refinement=await refinementResponse.json();
 if(!refinement.available)throw new Error(`Refinement unavailable (${refinementResponse.status()}): ${refinement.reason??refinement.detail}`);
 await page.getByText('Refined with Jev',{exact:true}).waitFor();
 const queryMatches=await page.locator('.job-row').count();
 if(!queryMatches||queryMatches>=catalog.jobs.length)throw new Error('Expected a nonempty relevant subset');
 const relevantIds=new Set(refinement.results.filter(r=>r.relevance>=.65).map(r=>r.id));
 for(const href of await page.locator('.job-row a[href^="/jobs/"]').evaluateAll(links=>links.map(a=>a.getAttribute('href')))){
  if(!relevantIds.has(href.split('/').at(-1)))throw new Error('Unapproved job survived Jev filtering');
 }
 await page.locator('.job-row').first().locator('.job-main').click();
 await page.getByRole('heading',{name:'Evidence',exact:true}).waitFor();
 if(!await page.locator('.drawer blockquote').count())throw new Error('Missing source evidence');
 await page.getByRole('button',{name:'Close details'}).click();
 await page.getByRole('textbox',{name:'Search jobs'}).fill('');
 await page.evaluate(()=>window.scrollTo(0,0));
 const rows=await page.locator('.job-row').count(),bubbles=await page.locator('.bubble').count();
 await page.getByRole('button',{name:'Market',exact:true}).click();
 await page.locator('.chart-point').first().waitFor();
 await page.locator('.chart-point').first().click();
 await page.locator('.market-list button').first().waitFor();
 await page.getByLabel('Intersect with').selectOption('postgresql');
 await page.locator('.market-list button').first().waitFor();
 if(errors.length)throw new Error(errors.join('\n'));
 console.log(JSON.stringify({status:'passed',https:true,sourceMode:catalog.source_mode,totalJobs:catalog.jobs.length,queryMatches,rows,bubbles,refinement:refinement.available,market:true,browserErrors:errors.length,hostnameResolution:'ordinary DNS'}));
}finally{await browser.close();}
