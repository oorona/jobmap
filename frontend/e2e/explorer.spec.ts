import {test,expect} from '@playwright/test';

test.beforeEach(async({page},info)=>{await page.setExtraHTTPHeaders({'x-real-ip':`test-${info.project.name}-${info.testId}`});await page.goto('/');await expect(page.getByText('Invented sample jobs.',{exact:false})).toBeVisible();await expect(page.locator('.job-row').first()).toBeVisible();});

test('typing, evidence, bookmarks, and saved searches',async({page})=>{
 await page.getByRole('textbox',{name:'Search jobs'}).fill('python');
 await expect(page.locator('.job-row')).not.toHaveCount(0);
 for(const text of await page.locator('.job-row').allTextContents())expect(text.toLowerCase()).toContain('python');
 await page.getByRole('button',{name:'＋ Save search'}).click();
 await page.locator('.job-row').first().locator('.save-button').click();
 await page.locator('.job-row').first().locator('.job-main').click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Evidence',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Close details'}).click();
 await page.getByRole('button',{name:/^Saved/}).first().click();
 await expect(page.locator('.job-row')).toHaveCount(1);
 await page.reload();
 await expect(page.getByRole('button',{name:'python',exact:true})).toBeVisible();
 await page.getByRole('button',{name:/^Saved/}).first().click();
 await expect(page.locator('.job-row')).toHaveCount(1);
});

test('requirements, unknown eligibility, list view, and jewels',async({page})=>{
 await page.getByRole('button',{name:/Your preferences|⚙/}).click();
 await page.getByLabel('Remote only').check();
 await page.getByLabel('Work eligibility').selectOption('MX');
 await page.getByLabel('Ownership',{exact:true}).check();
 await expect(page.locator('.job-row')).not.toHaveCount(0);
 await expect(page.locator('.job-row').filter({hasText:'onsite'})).toHaveCount(0);
 await expect(page.getByText('Potential jewel',{exact:false}).first()).toBeVisible();
 await page.getByRole('button',{name:/Needs clarification/}).click();
 await expect(page.locator('.job-row')).not.toHaveCount(0);
 await page.getByRole('button',{name:'List view',exact:true}).click();
 await expect(page.locator('.graph')).toHaveCount(0);
});

test('graph keyboard navigation and reduced motion',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await expect(page.getByText('Reduced motion on',{exact:false})).toBeVisible();
 const bubble=page.locator('.bubble').first();await bubble.focus();
 await expect(page.locator('.graph-tooltip')).toBeVisible();
 await bubble.press('Enter');await expect(page.getByRole('dialog')).toBeVisible();
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(bubble).toBeFocused();
});

test('graph pointer dragging and hover',async({page},info)=>{
 test.skip(info.project.name==='mobile','Desktop pointer test; touch selection is covered separately');
 const bubble=page.locator('.bubble').first();await bubble.hover();await expect(page.locator('.graph-tooltip')).toBeVisible();
 const box=await bubble.boundingBox();if(!box)throw new Error('Missing bubble');
 await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+90,box.y+50,{steps:10});await page.mouse.up();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 const moved=await bubble.boundingBox();expect(Math.abs((moved?.x??0)-box.x)).toBeGreaterThan(8);
});

test('touch selects a job',async({page},info)=>{
 test.skip(info.project.name!=='mobile','Touch interaction');
 await page.locator('.bubble').first().tap();await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'Close details'}).tap();await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('market timeline expands evidence records and skill intersection',async({page})=>{
 await page.getByRole('button',{name:'Market',exact:true}).click();
 await expect(page.getByRole('heading',{name:'A view of the hiring market'})).toBeVisible();
 await page.getByLabel('Compare',{exact:true}).selectOption('all');
 await expect(page.locator('.chart-point').first()).toBeVisible();
 await page.locator('.chart-point').first().click();
 await expect(page.locator('.market-list button').first()).toBeVisible();
 await page.getByLabel('Intersect with').selectOption('postgresql');
 await expect(page.locator('.market-list button').first()).toBeVisible();
 await page.locator('.market-list button').first().click();await expect(page.getByRole('dialog')).toBeVisible();
});

test('late refinement cannot replace a newer query',async({page})=>{
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.refinement.available=true;await route.fulfill({response,json:body});});
 let requests=0;
 await page.route('**/api/search/refine',async route=>{requests++;const body=route.request().postDataJSON();if(body.query==='python')await new Promise(r=>setTimeout(r,1400));await route.fulfill({json:{generation:body.generation,catalog_version:body.catalog_version,available:true,results:[{id:body.query==='python'?'demo_001':'demo_002',relevance:1,eligibility:'match',evidence_ids:[]}]}}).catch(()=>{});});
 await page.reload();await expect(page.locator('.job-row').first()).toBeVisible();
 await page.getByRole('textbox',{name:'Search jobs'}).fill('python');await expect.poll(()=>requests).toBe(1);
 await page.getByRole('textbox',{name:'Search jobs'}).fill('react');await expect.poll(()=>requests).toBe(2);
 await expect(page.locator('.job-row').first()).toContainText('Fieldwork');
 await page.waitForTimeout(1500);await expect(page.locator('.job-row').first()).toContainText('Fieldwork');
});

test('public detail page is readable and has source link',async({page})=>{
 await page.goto('/jobs/demo_001');await expect(page.getByRole('heading',{name:'Platform engineer',exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:/original.*posting|original.*advertisement/i})).toHaveAttribute('href',/example.com/);
});

test('visual preview and interaction performance with 100 bubbles',async({page},info)=>{
 if(info.project.name==='desktop')await page.setViewportSize({width:1280,height:1100});
 await page.screenshot({path:`../artifacts/explorer-${info.project.name}.png`,fullPage:false});
 test.skip(info.project.name==='mobile','Desktop performance target');
 let liveIds:string[]=Array.from({length:100},(_,i)=>`perf_${i}`);
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();const originals=body.jobs;body.jobs=Array.from({length:100},(_,i)=>({...originals[i%originals.length],id:`perf_${i}`,source_posted_at:new Date(Date.now()-86400000).toISOString()}));liveIds=body.jobs.map((j:{id:string})=>j.id);await route.fulfill({response,json:body});});
 await page.route('**/api/status',async route=>{const response=await route.fetch();const body=await response.json();body.live_ids=liveIds;await route.fulfill({response,json:body});});
 await page.reload();await expect(page.locator('.bubble')).toHaveCount(100);
 const bubble=page.locator('.bubble').first();await bubble.hover();const box=await bubble.boundingBox();if(!box)throw new Error('Missing drag target');const x=box.x+box.width/2,y=box.y+box.height/2;await page.mouse.move(x,y);await page.mouse.down();
 const measurement=page.evaluate(async()=>{const frames:number[]=[];let previous=performance.now();return await new Promise<{fps:number;p95:number}>(resolve=>{const tick=(now:number)=>{frames.push(now-previous);previous=now;if(frames.length<120)requestAnimationFrame(tick);else{const sorted=frames.slice(5).sort((a,b)=>a-b);const mean=frames.slice(5).reduce((s,v)=>s+v,0)/(frames.length-5);resolve({fps:1000/mean,p95:sorted[Math.floor(sorted.length*.95)]});}};requestAnimationFrame(tick);});});
 for(let i=0;i<12;i++){await page.mouse.move(x+Math.sin(i/2)*65,y+Math.cos(i/2)*45,{steps:6});await page.waitForTimeout(30);}
 await page.mouse.up();const metric=await measurement;
 console.log(`GRAPH_PERFORMANCE=${JSON.stringify(metric)}; nodes=100; viewport=${JSON.stringify(page.viewportSize())}`);
 expect(metric.fps).toBeGreaterThanOrEqual(50);
});

test('freshness control removes withdrawn jobs before adopting new results',async({page})=>{
 let refreshed=false;
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.version=refreshed?'new-version':'old-version';if(refreshed)body.jobs=body.jobs.filter((j:{id:string})=>j.id!=='demo_001');await route.fulfill({response,json:body});});
 await page.route('**/api/status',async route=>{const response=await route.fetch();const body=await response.json();body.version='new-version';body.live_ids=body.live_ids.filter((id:string)=>id!=='demo_001');await route.fulfill({response,json:body});});
 await page.reload();await expect(page.getByRole('button',{name:/New postings available/})).toBeVisible();
 await expect(page.locator('a[href="/jobs/demo_001"]')).toHaveCount(0);
 refreshed=true;await page.getByRole('button',{name:/New postings available/}).click();
 await expect(page.getByRole('button',{name:/New postings available/})).toHaveCount(0);
});

test('semantic refinement broadens keyword results without calls on preference weights',async({page})=>{
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.refinement.available=true;await route.fulfill({response,json:body});});
 let calls=0;
 await page.route('**/api/search/refine',async route=>{calls++;const body=route.request().postDataJSON();await route.fulfill({json:{generation:body.generation,catalog_version:body.catalog_version,available:true,results:[{id:'demo_001',relevance:.95,eligibility:'match',evidence_ids:[]}]}});});
 await page.reload();await page.getByRole('textbox',{name:'Search jobs'}).fill('autonomy');
 await expect(page.locator('.job-row').first()).toContainText('Northstar Labs');
 await expect.poll(()=>calls).toBe(1);
 await page.getByRole('button',{name:/Your preferences|⚙/}).click();await page.getByLabel('Ownership',{exact:true}).check();
 await page.waitForTimeout(1200);expect(calls).toBe(1);
});

test('natural-language intent becomes only the subset approved by Jev',async({page})=>{
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.refinement.available=true;for(const job of body.jobs.slice(0,2)){job.title='Robotics engineer';job.search_text='Build robotics systems';}await route.fulfill({response,json:body});});
 await page.route('**/api/search/refine',async route=>{const body=route.request().postDataJSON();await new Promise(r=>setTimeout(r,500));await route.fulfill({json:{generation:body.generation,catalog_version:body.catalog_version,available:true,results:[{id:'demo_001',relevance:.98,eligibility:'match',evidence_ids:[]},{id:'demo_002',relevance:.1,eligibility:'match',evidence_ids:[]}]}});});
 await page.reload();await page.getByRole('textbox',{name:'Search jobs'}).fill('I want to build robots');
 await expect(page.locator('.job-row')).toHaveCount(2);
 await expect(page.getByText('Refined with Jev',{exact:true})).toBeVisible();
 await expect(page.locator('.job-row')).toHaveCount(1);
 await expect(page.locator('.job-row')).toContainText('Northstar Labs');
 await expect(page.locator('.bubble[data-raised=true]')).toHaveCount(1);
});

test('Jev waits until typing and composition finish and clearing cancels pending work',async({page})=>{
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.refinement.available=true;await route.fulfill({response,json:body});});
 const queries:string[]=[];
 await page.route('**/api/search/refine',async route=>{const body=route.request().postDataJSON();queries.push(body.query);await route.fulfill({json:{generation:body.generation,catalog_version:body.catalog_version,available:true,results:[]}});});
 await page.reload();const input=page.getByRole('textbox',{name:'Search jobs'});
 await input.pressSequentially('I want to build robots',{delay:70});
 expect(queries).toEqual([]);
 await expect.poll(()=>queries).toEqual(['I want to build robots']);
 await input.fill('python');await page.getByRole('button',{name:'Clear search'}).click();
 await page.waitForTimeout(1200);expect(queries).toHaveLength(1);
 await input.dispatchEvent('compositionstart');await input.fill('rust');
 await page.waitForTimeout(1200);expect(queries).toHaveLength(1);
 await input.dispatchEvent('compositionend');await expect.poll(()=>queries).toEqual(['I want to build robots','rust']);
});

test('costs are visible and refresh without inference',async({page})=>{
 let calls=0;
 await page.route('**/api/search/refine',async route=>{calls++;await route.abort();});
 await page.route('**/api/usage',async route=>{const period={spent:.001234,reserved:.002,committed:.003234,remaining:.746766,limit:.75,charged_calls:3,pending_reservations:1,resets_at:'2026-10-02T00:00:00Z'};await route.fulfill({json:{currency:'USD',daily:period,monthly:{...period,limit:7.5,remaining:7.496766},refinement_available:true,status:'Available'}});});
 await page.reload();await expect(page.getByRole('region',{name:'Jev costs'})).toHaveCount(0);await page.getByRole('button',{name:'Usage & costs',exact:true}).click();const costs=page.getByRole('region',{name:'Jev costs'});
 await expect(costs).toBeVisible();await expect(costs.getByText('$0.001234',{exact:true})).toHaveCount(2);
 await expect(costs.getByText(/\$0.002000 reserved/)).toHaveCount(2);
 await costs.getByRole('button',{name:'Refresh costs'}).click();
 await expect(costs.getByText(/\$0.746766 remaining/)).toBeVisible();expect(calls).toBe(0);
});

test('color legend explains every graph category on desktop and mobile',async({page})=>{
 const legend=page.getByRole('region',{name:'Graph color legend'});await expect(legend).not.toBeVisible();await page.locator('.graph-guide summary').click();await expect(legend).toBeVisible();
 for(const label of ['Backend & other roles','Frontend & mobile','Infrastructure','Data & AI','Cyan ring · Hovered or selected','Amber halo · Potential jewel'])await expect(legend.getByText(label,{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'List view',exact:true}).click();await expect(legend).toHaveCount(0);
});

test('simple location, work and salary filters combine without inference',async({page})=>{
 let calls=0;await page.route('**/api/search/refine',async route=>{calls++;await route.abort();});
 await page.route('**/api/catalog',async route=>{const response=await route.fetch();const body=await response.json();body.jobs[0].location={status:'stated',value:'Mexico City',evidence_ids:[]};body.jobs[0].compensation={status:'stated',value:{min:100000,max:160000,currency:'USD',period:'year'},evidence_ids:[]};await route.fulfill({response,json:body});});
 await page.reload();await page.getByRole('button',{name:'Filters',exact:true}).click();await page.getByLabel('Location or eligible country',{exact:true}).fill('Mexico City');
 await page.getByLabel('Work type',{exact:true}).selectOption('remote');await page.getByLabel('Minimum pay',{exact:true}).fill('90000');
 await expect(page.locator('.job-row')).toHaveCount(1);await expect(page.locator('.job-row')).toContainText('Northstar Labs');
 await page.getByLabel('Salary currency',{exact:true}).selectOption('MXN');await expect(page.locator('.job-row')).toHaveCount(0);
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();await expect(page.locator('.job-row')).not.toHaveCount(1);expect(calls).toBe(0);
});

 test('bubbles settle below search and only matches rise',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 const graph=page.locator('.graph');
 await expect(page.getByRole('region',{name:'Job filters'})).toHaveCount(0);
 const bounds=await graph.boundingBox();const search=await page.locator('.search-box').boundingBox();
 expect(Math.abs(search!.width-bounds!.width)).toBeLessThan(3);
 const centers=()=>graph.locator('.bubble').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();const parent=n.closest('.graph')!.getBoundingClientRect();return (r.y+r.height/2-parent.y)/parent.height;}));
 await expect.poll(async()=>Math.min(...await centers())).toBeGreaterThan(.5);
 const before=await graph.locator('.bubble').evaluateAll(nodes=>nodes.map(n=>(n as HTMLElement).style.transform));
 await page.waitForTimeout(500);
 expect(await graph.locator('.bubble').evaluateAll(nodes=>nodes.map(n=>(n as HTMLElement).style.transform))).toEqual(before);
 await page.getByRole('textbox',{name:'Search jobs'}).fill('python');
 await expect(graph.locator('.bubble[data-raised=true]')).not.toHaveCount(0);
 await expect(graph.locator('.bubble[data-raised=false]')).not.toHaveCount(0);
 await expect.poll(async()=>graph.locator('.bubble').evaluateAll(nodes=>{const ys=(raised:string)=>nodes.filter(n=>n.getAttribute('data-raised')===raised).map(n=>{const r=n.getBoundingClientRect();return r.y+r.height/2;});return Math.max(...ys('true'))<Math.min(...ys('false'));})).toBe(true);
 await page.getByRole('button',{name:'Clear search'}).click();
 await expect(graph.locator('.bubble[data-raised=true]')).toHaveCount(0);
 await expect.poll(async()=>Math.min(...await centers())).toBeGreaterThan(.5);
 });

test('embedding selection uses cosine results without calling Jev',async({page})=>{
 let jevCalls=0,vectorCalls=0;
 await page.route('**/api/search/refine',async route=>{jevCalls++;await route.abort();});
 await page.route('**/api/search/vector',async route=>{vectorCalls++;const body=route.request().postDataJSON();expect(body.model).toBe('minilm');await route.fulfill({json:{available:true,generation:body.generation,catalog_version:body.catalog_version,threshold:-1,results:[{id:'demo_001',relevance:.2,evidence_ids:[]}],elapsed_ms:15}});});
 await page.getByLabel('Search method').selectOption('minilm');
 await page.getByRole('textbox',{name:'Search jobs'}).fill('robots');
 await expect(page.locator('.job-row')).toHaveCount(1);
 await expect(page.locator('.job-row')).toContainText('Northstar Labs');
 expect(vectorCalls).toBe(1);expect(jevCalls).toBe(0);
});

test('comparison shows independent results, ratings, cutoffs and descriptions',async({page})=>{
 const catalog=await page.evaluate(async()=>await (await fetch('/api/catalog')).json());
 await page.route('**/api/search/models',route=>route.fulfill({json:{enabled:true,running:false,total_jobs:catalog.jobs.length,models:[]}}));
 await page.route('**/api/search/compare',async route=>{const body=route.request().postDataJSON();await route.fulfill({json:{query:body.query,catalog_version:catalog.version,preferences:body.preferences,days:body.days,corpus_size:catalog.jobs.length,elapsed_ms:100,methodology:{},jobs:[{...catalog.jobs[0],description_text:'Build robots with a small engineering team.'}],methods:[{id:'jev',name:'Jev',model:'jev-1.13.0',available:true,results:[{id:catalog.jobs[0].id,relevance:.9}],elapsed_ms:95,evaluated_jobs:30},{id:'minilm',name:'MiniLM L6',model:'minilm',available:true,results:[{id:catalog.jobs[0].id,relevance:.4}],elapsed_ms:15,query_ms:12,database_ms:2,searched_jobs:catalog.jobs.length},{id:'bge',name:'BGE small',model:'bge',available:false,results:[],reason:'Index incomplete',elapsed_ms:1},{id:'arctic',name:'Snowflake Arctic',model:'arctic',available:true,results:[],elapsed_ms:18}]}});});
 await page.getByRole('button',{name:'Compare',exact:true}).click();
 await page.getByRole('textbox',{name:'Comparison query'}).fill('robots');
 await page.getByRole('button',{name:'Run comparison'}).click();
 const jev=page.getByRole('region',{name:'Jev results',exact:true});
 const mini=page.getByRole('region',{name:'MiniLM L6 results',exact:true});
 await expect(jev).toContainText('1 returned');await expect(mini).toContainText('1 returned');
 await jev.getByText('Read posting',{exact:true}).click();await expect(jev).toContainText('Build robots with a small engineering team.');
 await jev.getByRole('button',{name:'Relevant',exact:true}).click();
 await expect(mini.getByRole('button',{name:'Relevant',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(mini).toContainText('Precision among judged: 100%');
 await mini.getByLabel('MiniLM L6 cutoff').fill('0.5');await expect(mini).toContainText('0 returned');
 await expect(page.getByRole('region',{name:'BGE small results'})).toContainText('Index incomplete');
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export results & ratings'}).click();expect((await download).suggestedFilename()).toBe('job-search-comparison.json');
 await page.getByRole('button',{name:'Run comparison'}).click();
 await expect(page.getByRole('button',{name:'Run comparison'})).toBeEnabled();
 await expect(jev.getByRole('button',{name:'Relevant',exact:true})).toHaveAttribute('aria-pressed','true');
});

test('search animates bubbles upward once and then stops',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.waitForTimeout(1000);
 await page.getByRole('textbox',{name:'Search jobs'}).fill('python');
 await expect.poll(()=>page.locator('.bubble[data-raised=true]').evaluateAll(nodes=>nodes.some(n=>n.getAnimations().some(a=>a.playState==='running')))).toBe(true);
 await expect.poll(()=>page.locator('.bubble').evaluateAll(nodes=>nodes.every(n=>n.getAnimations().every(a=>a.playState!=='running')))).toBe(true);
});
