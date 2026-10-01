'use client';
import {useEffect,useState} from 'react';
import type {Job} from './types';
// Schedule the next actual expiry, rather than restarting a settled graph on a polling clock.
export function useExpiry(jobs:Job[]|undefined){
 const [clock,setClock]=useState(()=>Date.now());
 useEffect(()=>{const current=Date.now();const next=Math.min(...(jobs??[]).map(j=>Date.parse(j.expires_at)).filter(t=>t>current));if(!Number.isFinite(next))return;const timer=setTimeout(()=>setClock(Date.now()),Math.min(2147483647,Math.max(1,next-current+1)));return()=>clearTimeout(timer);},[jobs,clock]);
 return clock;
}
