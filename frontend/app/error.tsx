'use client';
export default function ErrorPage({reset}:{reset:()=>void}){return <main className="public-job"><a href="/">← Back to discovery</a><h1>We couldn’t load this view.</h1><p>The source may be temporarily unavailable. Your saved preferences are still on this device.</p><button className="primary" onClick={reset}>Try again</button></main>;}
