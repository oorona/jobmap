'use client';
import {useEffect,useRef,useState,useMemo} from 'react';
import {forceSimulation,forceCollide,forceX,forceY,SimulationNodeDatum} from 'd3-force';
import type {Job,Preferences} from '@/lib/types';
import {jewel,related} from '@/lib/search';
type Node=SimulationNodeDatum & {id:string;job:Job;r:number;group:number;raised:boolean};
const restingIds=new Set<string>();
const palette=[{color:'#65d7dc',label:'Backend & other roles'},{color:'#a79beb',label:'Frontend & mobile'},{color:'#91b5c7',label:'Infrastructure'},{color:'#8aa7db',label:'Data & AI'}];
function group(j:Job){const s=j.skills.map(x=>x.id);return s.some(x=>['react','typescript','javascript','swift'].includes(x))?1:s.some(x=>['machine-learning','sql'].includes(x))?3:s.includes('kubernetes')?2:0;}
export default function Graph({jobs,raisedIds=restingIds,selected,onSelect,preferences,query}:{jobs:Job[];raisedIds?:Set<string>;selected:string|null;onSelect:(id:string)=>void;preferences:Preferences;query:string}){
 const container=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null),positions=useRef(new Map<string,Node>()),elements=useRef(new Map<string,HTMLButtonElement>());
 const simulation=useRef<ReturnType<typeof forceSimulation<Node>>|null>(null),drag=useRef<{id:string;x:number;y:number;moved:boolean}|null>(null);
 const [size,setSize]=useState({w:900,h:450}),[hover,setHover]=useState<string|null>(null),[reduced,setReduced]=useState(false);
 const focus=hover??selected;const focusRef=useRef(focus);focusRef.current=focus;
 const layoutKey=useRef('');
 const motion=useRef(!reduced);motion.current=!reduced&&!(typeof window!=='undefined'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 const draw=useRef<()=>void>(()=>{});
 const picked=jobs.find(j=>j.id===focus);const relations=useMemo(()=>picked?related(jobs,picked):[],[jobs,picked]);
 useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(media.matches);update();media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
 useEffect(()=>{const observer=new ResizeObserver(([entry])=>setSize({w:entry.contentRect.width,h:Math.max(350,Math.min(500,entry.contentRect.width*.53))}));if(container.current)observer.observe(container.current);return()=>observer.disconnect();},[]);
 useEffect(()=>{
  const nodes:Node[]=jobs.map((job,index)=>{const old=positions.current.get(job.id);const node={...old,id:job.id,job,group:group(job),raised:raisedIds.has(job.id),r:(query.trim()&&!raisedIds.has(job.id)?12:14+(index%4)*3)*Math.max(.6,Math.min(1,size.w/700)),x:old?.x??size.w*.5+(Math.sin(index*2.4)*size.w*.3),y:old?.y??size.h-65-(index%3)*30};positions.current.set(job.id,node);return node;});
  const visible=new Set(nodes.map(n=>n.id));
  const ctx=canvas.current?.getContext('2d');const dpr=window.devicePixelRatio||1;
  if(canvas.current){canvas.current.width=size.w*dpr;canvas.current.height=size.h*dpr;}
  draw.current=()=>{
   if(!ctx)return;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,size.w,size.h);
   const chosen=nodes.find(n=>n.id===focusRef.current);
   if(chosen){for(const r of related(jobs,chosen.job)){const end=nodes.find(n=>n.id===r.job.id);if(end){ctx.beginPath();ctx.moveTo(chosen.x!,chosen.y!);ctx.lineTo(end.x!,end.y!);ctx.strokeStyle='#67d9dc80';ctx.lineWidth=1;ctx.stroke();}}}
   for(const node of nodes){node.x=Math.max(node.r+8,Math.min(size.w-node.r-8,node.x??0));node.y=Math.max(node.r+52,Math.min(size.h-node.r-40,node.y??0));const el=elements.current.get(node.id);if(el)el.style.transform=`translate(${node.x-node.r}px,${node.y-node.r}px)`;}
  };
  const sim=forceSimulation(nodes).force('collision',forceCollide<Node>().radius(n=>n.r+3).iterations(4)).force('x',forceX<Node>(n=>size.w*(.12+((jobs.findIndex(j=>j.id===n.id)*.618)%1)*.76)).strength(.045)).force('y',forceY<Node>(n=>n.raised?size.h*.22:size.h-55).strength(n=>n.raised?.24:.3)).alphaDecay(.045).stop();
  simulation.current=sim;
  // Keep the displayed positions while calculating destinations offscreen.
  const starts=new Map(nodes.map(n=>[n.id,{x:n.x!,y:n.y!}]));
  // Settle the layout before painting; animate once, then remain still.
  const nextLayout=JSON.stringify([size,query,nodes.map(n=>[n.id,n.r,n.raised])]);
  if(layoutKey.current!==nextLayout)for(let i=0;i<150;i++){sim.tick();for(const node of nodes){node.x=Math.max(node.r+8,Math.min(size.w-node.r-8,node.x??0));node.y=Math.max(node.r+52,Math.min(size.h-node.r-40,node.y??0));}}
  layoutKey.current=nextLayout;
  for(const node of nodes){const el=elements.current.get(node.id);if(!el)continue;const start=starts.get(node.id)!;
   const displayed=el.getAnimations().length?getComputedStyle(el).transform:el.style.transform;
   el.getAnimations().forEach(a=>a.cancel());
   const from=displayed||`translate(${start.x-node.r}px,${size.h-node.r-42}px)`;
   const to=`translate(${node.x!-node.r}px,${node.y!-node.r}px)`;
   el.style.transform=to;
   if(motion.current&&from!==to)el.animate([{transform:from},{transform:to}],{duration:850,easing:'cubic-bezier(.22,1,.36,1)'});
  }
  draw.current();
  const frame=requestAnimationFrame(()=>draw.current());
  // Retain bounded positions so returning search results keep their place.
  if(positions.current.size>2000)for(const id of positions.current.keys())if(!visible.has(id))positions.current.delete(id);
  return()=>{sim.stop();cancelAnimationFrame(frame);};
 },[jobs,size,query,raisedIds]);
 useEffect(()=>draw.current(),[focus]);
 useEffect(()=>{if(reduced){elements.current.forEach(el=>el.getAnimations().forEach(a=>a.cancel()));draw.current();}},[reduced]);
 const down=(e:React.PointerEvent<HTMLButtonElement>,id:string)=>{if(e.button!==0)return;const node=positions.current.get(id);const rect=e.currentTarget.getBoundingClientRect(),parent=container.current?.getBoundingClientRect();if(node&&parent){node.x=rect.left+rect.width/2-parent.left;node.y=rect.top+rect.height/2-parent.top;}e.currentTarget.getAnimations().forEach(a=>a.cancel());draw.current();e.currentTarget.setPointerCapture(e.pointerId);drag.current={id,x:e.clientX,y:e.clientY,moved:false};};
 const move=(e:React.PointerEvent<HTMLButtonElement>)=>{const d=drag.current;if(!d)return;const node=positions.current.get(d.id);const rect=container.current?.getBoundingClientRect();if(!node||!rect)return;if(Math.hypot(e.clientX-d.x,e.clientY-d.y)>4)d.moved=true;if(!d.moved)return;node.fx=e.clientX-rect.left;node.fy=e.clientY-rect.top;node.x=node.fx;node.y=node.fy;draw.current();};
 const up=(e:React.PointerEvent<HTMLButtonElement>)=>{const d=drag.current;if(d){const node=positions.current.get(d.id);if(node){node.fx=null;node.fy=null;}if(!d.moved)onSelect(d.id);drag.current=null;}if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);};
 return <div className="graph" ref={container} style={{height:size.h}} aria-label="Interactive job graph"><details className="graph-guide"><summary>Color guide</summary><section className="graph-color-key" aria-label="Graph color legend"><div className="color-key-heading"><span>Broad skill groups, not relevance scores.</span></div><ul>{palette.map(item=><li key={item.label}><i style={{background:item.color}} aria-hidden="true"/>{item.label}</li>)}<li><i className="key-focus" aria-hidden="true"/>Cyan ring · Hovered or selected</li><li><i className="key-jewel" aria-hidden="true"/>Amber halo · Potential jewel</li></ul><p>Potential jewels have evidence that fits your preferences. Lines connect shared companies or skills.</p></section></details>
  <div className="graph-grid"/><canvas ref={canvas} style={{width:size.w,height:size.h}} aria-hidden="true"/>
  {jobs.map((j,i)=>{const raised=raisedIds.has(j.id);const radius=(query.trim()&&!raised?12:14+(i%4)*3)*Math.max(.6,Math.min(1,size.w/700));return <button key={j.id} ref={el=>{if(el)elements.current.set(j.id,el);else elements.current.delete(j.id);}} data-raised={raised} className={`bubble ${query.trim()&&!raised?'settled':''} ${selected===j.id?'selected':''} ${jewel(j,preferences)?'jewel':''}`} style={{width:radius*2,height:radius*2,'--bubble-color':palette[group(j)].color} as React.CSSProperties} aria-label={`${j.title} at ${j.company.name} · ${palette[group(j)].label}`} aria-pressed={selected===j.id} onPointerDown={e=>down(e,j.id)} onPointerMove={move} onPointerUp={up} onPointerCancel={()=>{const n=drag.current&&positions.current.get(drag.current.id);if(n){n.fx=null;n.fy=null;}drag.current=null;}} onClick={e=>{if(e.detail===0)onSelect(j.id);}} onMouseEnter={()=>setHover(j.id)} onMouseLeave={()=>setHover(null)} onFocus={()=>setHover(j.id)} onBlur={()=>setHover(null)}><span>{j.company.name.split(' ').map(w=>w[0]).slice(0,2).join('')}</span></button>;})}
  {picked&&<div className="graph-tooltip" role="status"><strong>{picked.title}</strong><span>{picked.company.name}</span><small>{palette[group(picked)].label}</small>{relations.map(r=><small key={r.job.id}>{r.reason} · {r.job.company.name}</small>)}</div>}
  {!jobs.length&&<div className="graph-empty">No matching jobs in this view.<span>Try a broader search or adjust your requirements.</span></div>}
  <div className="graph-bottom"><span><i/> {query.trim()?`${raisedIds.size} matches risen · ${jobs.length-raisedIds.size} settled`:`${jobs.length} opportunities · Search to bring matches up`}</span><span>{reduced?'Reduced motion on':'Drag to explore'} · Tab to navigate · Select for details</span></div>
 </div>;
}
