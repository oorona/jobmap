'use client';
import {useEffect,useRef} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '@/lib/api';
import type {Detail} from '@/lib/types';
import {displayValue,safeLink} from '@/lib/search';
import {useLocal} from '@/lib/store';
export default function Details({id,onClose}:{id:string;onClose:()=>void}){
 const {data:job,error,isPending}=useQuery({queryKey:['job',id],queryFn:()=>api<Detail>(`jobs/${encodeURIComponent(id)}`),gcTime:0,retry:false});
 const {bookmarks,bookmark}=useLocal();const root=useRef<HTMLElement>(null);
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;root.current?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose();if(e.key==='Tab'){const list=root.current?.querySelectorAll<HTMLElement>('button,a[href],[tabindex="0"]');if(!list?.length)return;const first=list[0],last=list[list.length-1];if(e.shiftKey&&(document.activeElement===first||document.activeElement===root.current)){last.focus();e.preventDefault();}else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault();}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus();};},[onClose]);
 return <div className="drawer-scrim" onClick={e=>{if(e.target===e.currentTarget)onClose();}}><aside className="drawer" ref={root} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Job details"><div className="drawer-bar"><span className="eyebrow">THE OPPORTUNITY</span><button onClick={onClose} aria-label="Close details">✕</button></div>
 {isPending?<p className="muted">Loading source evidence…</p>:error?<div role="alert"><h2>Job unavailable</h2><p>{error.message}</p><button onClick={onClose}>Back to discovery</button></div>:job&&<>
 <p className="company-line">{job.company.name}</p><h2>{job.title}</h2><div className="tags">{job.skills.map(s=><span key={s.id}>{s.label}</span>)}</div>
 <div className="detail-actions"><button className="primary" onClick={()=>bookmark(id)}>{bookmarks.includes(id)?'★ Saved':'☆ Save job'}</button><a href={`/jobs/${id}`}>Open job page ↗</a></div>
 <p className="notice">Posted {new Date(job.source_posted_at).toLocaleDateString()}. Availability is not confirmed. Check with the employer.</p>
 <h3>What the posting says</h3><p className="description">{job.description_text}</p>
 <div className="detail-fields">{Object.entries({work_mode:job.work_mode,eligible_countries:job.eligible_countries,compensation:job.compensation,...job.fields}).map(([name,field])=><div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{displayValue(field.value)} {field.status==='inferred'&&<small>(inferred)</small>}{field.evidence_ids?.map(e=><a key={e} href={`#${e}`} className="evidence-link">Source ↗</a>)}</dd></div>)}</div>
 <h3>Evidence</h3>{job.evidence.map(e=><blockquote key={e.id} id={e.id}><p>“{e.text}”</p><small>Source revision {e.source_revision_id}</small></blockquote>)}
 <h3>What we don’t know</h3><p className="muted">{job.unknowns.length?job.unknowns.map(s=>s.replaceAll('_',' ')).join(', '):'No additional unknowns reported.'}</p>
 <h3>Apply at the source</h3>{job.application_links.filter(a=>safeLink(a.url)).map(a=><a className="application-link" key={a.url} href={a.url} target="_blank" rel="noopener noreferrer">{a.label} ↗</a>)}
 {safeLink(job.source_url)&&<a className="application-link secondary" href={job.source_url} target="_blank" rel="noopener noreferrer">Original posting ↗</a>}<p className="fine-print">Automated screening is not a guarantee of employer legitimacy. Expires {new Date(job.expires_at).toLocaleDateString()}.</p>
 </>}
 </aside></div>;
}
