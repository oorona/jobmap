import { NextRequest, NextResponse } from 'next/server';
export function proxy(request: NextRequest) {
 const nonce=btoa(crypto.randomUUID());
 const csp=`default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${process.env.NODE_ENV==='development'?" 'unsafe-eval'":''}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`;
 const headers=new Headers(request.headers);headers.set('x-nonce',nonce);headers.set('Content-Security-Policy',csp);
 const res=NextResponse.next({request:{headers}});
 for(const [k,v] of Object.entries({'Content-Security-Policy':csp,'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Strict-Transport-Security':'max-age=31536000; includeSubDomains'}))res.headers.set(k,v);
 if(process.env.SOURCE_MODE!=='live')res.headers.set('X-Robots-Tag','noindex, nofollow');
 return res;
}
export const config={matcher:['/((?!_next/static|_next/image|favicon.ico).*)']};
