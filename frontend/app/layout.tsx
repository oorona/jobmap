import type { Metadata } from 'next';
import './globals.css';
// Per-request CSP nonces require request-time HTML.
export const dynamic = 'force-dynamic';
export const metadata:Metadata={metadataBase:new URL(process.env.SITE_URL??'https://jobmap.home.iktdts.com'),title:'JobMap · Find your next chapter',robots:process.env.SOURCE_MODE==='live'?{index:true,follow:true}:{index:false,follow:false},description:'Explore evidence-backed opportunities from Hacker News Who is hiring. Discover roles, compare skills, and keep your search on your device.',alternates:{canonical:'/'},openGraph:{title:'JobMap',description:'A clearer view of the Hacker News hiring market.'}};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>;}
