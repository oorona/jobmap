import type {Job,Preferences} from './types';
export const dimensions:Record<string,string>={specificity:'Specific responsibilities',ownership:'Ownership',learning:'Learning support',adjacent:'Adjacent experience',conditions:'Working conditions',transparency:'Compensation transparency'};
export const active=(j:Job,at=Date.now())=>Date.parse(j.source_posted_at)<=at && Date.parse(j.expires_at)>at;
export function eligibility(j:Job,p:Preferences){
 let unknown=false;
 if(p.remote){if(j.work_mode.status==='stated' && ['onsite','hybrid'].includes(String(j.work_mode.value)))return 'conflict';if(j.work_mode.status!=='stated'||j.work_mode.value!=='remote')unknown=true;}
 if(p.country){if(j.eligible_countries.status==='stated'&&Array.isArray(j.eligible_countries.value)){if(!j.eligible_countries.value.includes(p.country)&&!j.eligible_countries.value.includes('worldwide'))return 'conflict';}else unknown=true;}
 return unknown?'clarify':'match';
}
export function jewel(j:Job,p:Preferences){return eligibility(j,p)==='match'&&Object.entries(p.weights).some(([k,w])=>w>0&&(j.dimensions[k]?.score??0)>=.85&&j.dimensions[k].evidence_ids.length>0);}
const filler=new Set('i me my we our you your a an the to of for in on at with and or that where who is are be am as it want wants would like looking look find seeking job jobs role roles work working build building develop developing please can could do doing have using use'.split(' '));
const normalizeToken=(word:string)=>{const token=word.replace(/[.-]+$/,'');if(['robot','robots','robotic','robotics'].includes(token))return 'robot';if(token==='agentic')return 'agent';return token.length>4&&token.endsWith('s')&&!token.endsWith('ss')?token.slice(0,-1):token;};
const tokens=(text:string)=>(text.toLowerCase().match(/[a-z0-9][a-z0-9.+#-]*/g)??[]).map(normalizeToken);
export const queryTerms=(query:string)=>[...new Set(tokens(query).filter(t=>!filler.has(t)))];
const indexed=new WeakMap<Job,Set<string>>();
function jobTokens(job:Job){let words=indexed.get(job);if(!words){words=new Set(tokens(`${job.title} ${job.company.name} ${job.search_text} ${job.skills.map(s=>`${s.id} ${s.label}`).join(' ')}`));indexed.set(job,words);}return words;}
export function search(jobs:Job[],query:string,p:Preferences,includeClarification=true){
 const words=queryTerms(query),blank=!query.trim(),any=/\bor\b/i.test(query);
 return jobs.filter(j=>active(j)&&eligibility(j,p)!=='conflict'&&(includeClarification||eligibility(j,p)!=='clarify'))
 .map(job=>({job,hits:words.filter(w=>jobTokens(job).has(w)).length,rank:Object.entries(p.weights).reduce((s,[k,w])=>s+(job.dimensions[k]?.score??0)*w,0)}))
 .filter(({hits})=>blank||(words.length>0&&(any?hits>0:hits===words.length)))
 .map(row=>({...row,rank:row.rank+row.hits*10}))
 .sort((a,b)=>b.rank-a.rank||b.job.source_posted_at.localeCompare(a.job.source_posted_at)).map(r=>r.job);
}
export function related(jobs:Job[],job:Job){return jobs.filter(j=>j.id!==job.id).map(j=>({job:j,skills:j.skills.filter(s=>job.skills.some(x=>x.id===s.id)),company:j.company.id===job.company.id})).filter(r=>r.company||r.skills.length).sort((a,b)=>(b.skills.length+Number(b.company)*3)-(a.skills.length+Number(a.company)*3)).slice(0,3).map(r=>({job:r.job,reason:r.company?'Same company':`Shared ${r.skills.map(s=>s.label).join(', ')}`}));}
export const acceptRefinement=(r:{generation:number;catalog_version:string},generation:number,version:string)=>r.generation===generation&&r.catalog_version===version;
export function safeLink(url:string){try{const p=new URL(url);return ['http:','https:'].includes(p.protocol)&&!p.username&&!p.password;}catch{return false;}}
export function displayValue(v:unknown):string{if(v===null||v===undefined)return 'Not stated';if(Array.isArray(v))return v.map(displayValue).join(', ');if(typeof v==='object'){const record=v as Record<string,unknown>;return typeof record.original==='string'?record.original:Object.entries(record).map(([k,x])=>`${k.replaceAll('_',' ')}: ${displayValue(x)}`).join(' · ');}return String(v);}

export function mergeRefinement(local:Job[],jobs:Job[],results:{id:string;relevance:number}[],p:Preferences,threshold=.65){
 const relevant=new Set(results.filter(r=>r.relevance>=threshold).map(r=>r.id));
 return jobs.filter(j=>relevant.has(j.id)&&active(j)&&eligibility(j,p)!=='conflict');
}
