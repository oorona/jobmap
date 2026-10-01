export const dynamic = 'force-dynamic';
import type {MetadataRoute} from 'next';
export default async function sitemap():Promise<MetadataRoute.Sitemap>{
 if(process.env.SOURCE_MODE!=='live')return [];
 const base=process.env.SITE_URL??'https://jobmap.home.iktdts.com';
 try {const res=await fetch(`${process.env.INTERNAL_API_URL??'http://127.0.0.1:8000'}/api/catalog`,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!res.ok)return [{url:base}];const data=await res.json();return [{url:base},...data.jobs.map((j:{id:string;updated_at:string})=>({url:`${base}/jobs/${j.id}`,lastModified:j.updated_at}))];}catch{return [{url:base}];}
}
