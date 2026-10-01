import { NextRequest } from 'next/server';
const allowed = /^(catalog|status|usage|market|market\/jobs|jobs\/[a-zA-Z0-9_-]+|search|search\/(refine|vector|compare|models))$/;
async function proxy(request: NextRequest, context: {params: Promise<{path:string[]}>}) {
  const {path} = await context.params;
  const route = path.join('/');
  if (!allowed.test(route) || (request.method==='POST' && !['search/refine','search/vector','search/compare'].includes(route))) return new Response(null,{status:404});
  if (request.method==='POST' && Number(request.headers.get('content-length') ?? 0)>8192) return new Response(null,{status:413});
  const reader = request.body?.getReader(); let body: Uint8Array | undefined;
  if (request.method==='POST' && reader) {
    const chunks: Uint8Array[]=[]; let size=0;
    while (true) {const r=await reader.read();if(r.done)break;size+=r.value.byteLength;if(size>8192){await reader.cancel();return new Response(null,{status:413});}chunks.push(r.value);}
    body=new Uint8Array(size);let pos=0;for(const c of chunks){body.set(c,pos);pos+=c.length;}
  }
  const headers = new Headers();
  for (const name of ['cookie','content-type','origin','x-requested-with','if-none-match']) {const value=request.headers.get(name);if(value)headers.set(name,value);}
  headers.set('x-jev-peer',request.headers.get('x-real-ip') ?? 'unknown');
  try {
    const res = await fetch(`${process.env.INTERNAL_API_URL ?? 'http://127.0.0.1:8000'}/api/${route}${request.nextUrl.search}`,{method:request.method,headers,body:body as BodyInit|undefined,cache:'no-store',signal:AbortSignal.timeout(route==='search/compare'?35000:30000)});
    const out = new Headers({'Content-Type':'application/json','Cache-Control':'private, no-store'});
    for(const key of ['set-cookie','etag','retry-after']) {const val=res.headers.get(key);if(val)out.set(key,val);}
    let responseBody=res.body;
    const acceptsGzip=(request.headers.get('accept-encoding')??'').split(',').some(part=>{const [encoding,...params]=part.trim().toLowerCase().split(';');return encoding==='gzip'&&!params.some(p=>/^q=0(?:\.0*)?$/.test(p.trim()));});
    out.set('Vary','Accept-Encoding');
    if(responseBody && res.status!==304 && acceptsGzip){
      responseBody=responseBody.pipeThrough(new CompressionStream('gzip'));
      out.set('Content-Encoding','gzip');out.set('Vary','Accept-Encoding');
    }
    return new Response(responseBody,{status:res.status,headers:out});
  } catch {return Response.json({detail:'Service temporarily unavailable'},{status:503});}
}
export {proxy as GET,proxy as POST};
