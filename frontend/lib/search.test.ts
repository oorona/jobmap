import {describe,it,expect} from 'vitest';
import {active,eligibility,jewel,search,related,acceptRefinement,safeLink,mergeRefinement} from './search';
import fixtures from '../fixtures/jobs.json';
import type {Job,Preferences} from './types';
const jobs=(fixtures as unknown as Job[]).map((j,i)=>({...j,source_posted_at:new Date(Date.now()-(i+1)*86400000).toISOString(),expires_at:new Date(Date.now()+86400000).toISOString()}));
const preferences:Preferences={remote:false,country:'',weights:{}};
describe('evidence-based local search',()=>{
 it('excludes known conflicts despite positive weights',()=>{const p={...preferences,remote:true,weights:{ownership:1}};expect(eligibility(jobs[5],p)).toBe('conflict');expect(search(jobs,'',p).some(j=>j.id===jobs[5].id)).toBe(false);});
 it('does not invent country eligibility or reward missing evidence',()=>{expect(eligibility(jobs[2],{...preferences,country:'MX'})).toBe('clarify');expect(jewel(jobs[0],preferences)).toBe(false);expect(jewel(jobs[0],{...preferences,weights:{learning:1}})).toBe(false);expect(jewel(jobs[0],{...preferences,weights:{ownership:1}})).toBe(true);});
 it('matches skills and text and bounds related connections',()=>{expect(search(jobs,'python',preferences).every(j=>j.search_text.toLowerCase().includes('python'))).toBe(true);expect(related(jobs,jobs[0])).toHaveLength(3);});
 it('purges expired roles and ignores stale responses',()=>{expect(active(jobs[0],Date.parse(jobs[0].expires_at))).toBe(false);expect(acceptRefinement({generation:1,catalog_version:'old'},2,'new')).toBe(false);expect(acceptRefinement({generation:2,catalog_version:'new'},2,'new')).toBe(true);});
 it('rejects executable and credential-bearing links',()=>{expect(safeLink('javascript:alert(1)')).toBe(false);expect(safeLink('https://a:b@example.org')).toBe(false);expect(safeLink('https://example.org')).toBe(true);});
 it('includes semantic candidates beyond keyword matches without bypassing requirements',()=>{const p={...preferences,remote:true};const rows=mergeRefinement([],jobs,[{id:jobs[0].id,relevance:.9},{id:jobs[5].id,relevance:.99},{id:jobs[1].id,relevance:.3}],p);expect(rows.map(j=>j.id)).toEqual([jobs[0].id]);});
 it('uses intent words for immediate natural-language results',()=>{const rows=[{...jobs[0],title:'Robotics engineer',search_text:'Robotics systems',skills:[]},{...jobs[1],title:'Web engineer',search_text:'I want to build a web platform',skills:[]}];expect(search(rows,'I want to build robots',preferences).map(j=>j.id)).toEqual([rows[0].id]);});
 it('Jev removes irrelevant and unevaluated jobs instead of merely reranking them',()=>{expect(mergeRefinement(jobs,jobs,[{id:jobs[0].id,relevance:.9},{id:jobs[1].id,relevance:.2}],preferences).map(j=>j.id)).toEqual([jobs[0].id]);expect(mergeRefinement(jobs,jobs,[],preferences)).toEqual([]);});
 it('agent includes Agent Builder and agentic roles',()=>{const rows=['Agent Builder','Agentic AI engineer','Web engineer'].map((title,i)=>({...jobs[i],title,search_text:title,skills:[]}));expect(search(rows,'agent',preferences).map(j=>j.title)).toEqual(['Agent Builder','Agentic AI engineer']);});
 it('measures local ranking over 10000 records',()=>{const rows=Array.from({length:10000},(_,i)=>({...jobs[i%jobs.length],id:String(i),expires_at:'2099-01-01T00:00:00Z'}));const timings=[];for(let i=0;i<25;i++){const start=performance.now();search(rows,'python remote',preferences);timings.push(performance.now()-start);}timings.sort((a,b)=>a-b);const p95=timings[23];console.log(`LOCAL_SEARCH_P95_MS=${p95.toFixed(2)}; records=10000`);expect(p95).toBeLessThan(100);});
});
