import Explorer from '@/components/Explorer';
import type {Catalog} from '@/lib/types';
import {headers} from 'next/headers';
export default async function Page(){
 let initialCatalog:Catalog|undefined;
 try{const response=await fetch(`${process.env.INTERNAL_API_URL??'http://127.0.0.1:8000'}/api/catalog`,{cache:'no-store',headers:{'x-jev-peer':(await headers()).get('x-real-ip')??'unknown'},signal:AbortSignal.timeout(15000)});if(response.ok)initialCatalog=await response.json();}catch{/* Client shows a retriable feed error; never substitute fixtures. */}
 return <Explorer initialCatalog={initialCatalog}/>;
}
