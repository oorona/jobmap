import {notFound} from 'next/navigation';
import type {Detail} from '@/lib/types';
import {safeLink,displayValue} from '@/lib/search';
import {cache} from 'react';
import {headers} from 'next/headers';
const get=cache(async(id:string):Promise<Detail|null>=>{
 if(!/^[a-zA-Z0-9_-]{1,100}$/.test(id))return null;
 const response=await fetch(`${process.env.INTERNAL_API_URL??'http://127.0.0.1:8000'}/api/jobs/${id}`,{cache:'no-store',headers:{'x-jev-peer':(await headers()).get('x-real-ip')??'unknown'},signal:AbortSignal.timeout(15000)});
 if(response.status===404||response.status===410)return null;
 if(!response.ok)throw new Error('The job source is temporarily unavailable.');
 return response.json();
});
export async function generateMetadata({params}:{params:Promise<{id:string}>}){
 const {id}=await params;const j=await get(id);
 return {title:j?`${j.title} at ${j.company.name} · HN Job Explorer`:'Job unavailable',description:j?.search_text.slice(0,170),openGraph:{title:j?`${j.title} at ${j.company.name}`:'Job unavailable',description:j?.search_text.slice(0,170),url:`/jobs/${id}`},alternates:{canonical:`/jobs/${id}`}};
}
export default async function JobPage({params}:{params:Promise<{id:string}>}){
 const {id}=await params;const j=await get(id);if(!j)notFound();
 return <main className="public-job"><a href="/">← Explore opportunities</a>{process.env.SOURCE_MODE!=='live'&&<p className="demo-banner">PREVIEW · Invented sample job. This is not a real hiring advertisement.</p>}<p className="eyebrow">HACKER NEWS · WHO IS HIRING</p><h1>{j.title}</h1><h2>{j.company.name}</h2><p>Posting date does not confirm this position remains open.</p><p>Posted {new Date(j.source_posted_at).toLocaleDateString('en-US',{timeZone:'UTC'})} · Expires {new Date(j.expires_at).toLocaleDateString('en-US',{timeZone:'UTC'})}</p><div className="tags">{j.skills.map(s=><span key={s.id}>{s.label}</span>)}</div><article>{j.description_text}</article><div className="detail-fields">{Object.entries({work_mode:j.work_mode,eligible_countries:j.eligible_countries,compensation:j.compensation,...j.fields}).map(([name,value])=><div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{displayValue(value.value)}{value.evidence_ids?.map(e=><a className="evidence-link" key={e} href={`#${e}`}>Source ↗</a>)}</dd></div>)}</div><h2>Source evidence</h2>{j.evidence.map(e=><blockquote id={e.id} key={e.id}><p>{e.text}</p></blockquote>)}<h2>Application links</h2>{j.application_links.filter(a=>safeLink(a.url)).map(a=><a className="application-link" key={a.url} href={a.url} rel="noopener noreferrer">{a.label} ↗</a>)}<a href={j.source_url} rel="noopener noreferrer">Read original source posting ↗</a></main>;
}
