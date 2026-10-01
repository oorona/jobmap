'use client';
import {useQuery} from '@tanstack/react-query';
import {api} from '@/lib/api';

type Period={spent:number;reserved:number;committed:number;remaining:number;limit:number;charged_calls:number;pending_reservations:number;resets_at:string};
type UsageData={currency:string;timezone:string;scope:string;as_of:string;daily:Period;monthly:Period;refinement_available:boolean;status:string};
const amount=(value:number)=>`$${value.toFixed(6)}`;
export default function Usage(){
 const {data,error,isPending,refetch,isFetching}=useQuery({queryKey:['usage'],queryFn:()=>api<UsageData>('usage'),refetchInterval:30000,retry:1});
 return <section className="usage-panel" aria-label="Jev costs"><div className="usage-heading"><h2>Jev costs <small>USD · Shared across all visitors</small></h2><div>{data&&<span className={data.refinement_available?'usage-available':'muted'}>{data.status}</span>}<button onClick={()=>void refetch()} disabled={isFetching} aria-label="Refresh costs">Refresh ↻</button></div></div>
 {isPending?<p className="muted">Loading recorded costs…</p>:error?<p role="alert">Costs are temporarily unavailable. Use Refresh to try again.</p>:data&&<><div className="usage-periods">{([['Today',data.daily],['This month',data.monthly]] as const).map(([label,period])=><div className="usage-period" key={label}><h3>{label} <small>UTC</small></h3><p><strong>{amount(period.spent)}</strong><span> spent / ${period.limit.toFixed(2)} budget</span></p><progress value={period.committed} max={period.limit} aria-label={`${label} budget used`}/><p className="usage-detail">{amount(period.remaining)} remaining · {period.charged_calls} charged calls</p>{period.pending_reservations>0&&<p className="usage-reserved">{amount(period.reserved)} reserved · {period.pending_reservations} pending or uncertain calls</p>}</div>)}</div><p className="fine-print">JobMap search refinement only. Feed ingestion has a separate budget; its spending is not included here. Reservations reduce the remaining budget until billing is confirmed. Updates every 30 seconds and after search refinement.</p></>}
 </section>;
}
