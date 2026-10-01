"""Generate the established Charon narration; keep credentials out of artifacts."""
from pathlib import Path
import urllib.request, urllib.error, json, base64, wave, concurrent.futures, hashlib
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'artifacts/jobmap-demo-work'
SCENES=json.loads((ROOT/'scripts/demos/jobmap/scenes.json').read_text())
KEY=Path('/home/iktdts/apps/website/latent/secrets/gemini_api_key.txt').read_text().strip()
MODEL='gemini-3.1-flash-tts-preview'
OUT.mkdir(parents=True,exist_ok=True)
def generate(scene):
    dest=OUT/(scene['id']+'.wav');meta=dest.with_suffix('.json')
    digest=hashlib.sha256(scene['text'].encode()).hexdigest()
    if dest.exists() and meta.exists() and json.loads(meta.read_text()).get('text_sha256')==digest:return json.loads(meta.read_text())
    assert not any(c in scene['text'] for c in ('—','–',' -- '))
    prompt='Read the following narration exactly as written, in conversational English. Use a clear, warm, measured documentary voice, about 145 words per minute. Keep technical terms natural. Pronounce Jev as jehv. Do not read these instructions.\n\n'+scene['text']
    body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseModalities':['AUDIO'],'speechConfig':{'voiceConfig':{'prebuiltVoiceConfig':{'voiceName':'Charon'}}}}}
    request=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','x-goog-api-key':KEY})
    try:
        with urllib.request.urlopen(request,timeout=180) as response:result=json.load(response)
    except urllib.error.HTTPError as exc:raise RuntimeError(f'Speech generation HTTP {exc.code}') from None
    chunks=[p['inlineData'] for p in result.get('candidates',[{}])[0].get('content',{}).get('parts',[]) if 'inlineData' in p]
    if not chunks or not all('audio/l16' in p['mimeType'].lower() or 'audio/pcm' in p['mimeType'].lower() for p in chunks):raise RuntimeError('No PCM narration returned')
    pcm=b''.join(base64.b64decode(p['data']) for p in chunks)
    with wave.open(str(dest),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(24000);out.writeframes(pcm)
    info={'id':scene['id'],'model':MODEL,'voice':'Charon','seconds':len(pcm)/48000,'usage':result.get('usageMetadata',{}),'text_sha256':digest}
    meta.write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps({'scene':scene['id'],'seconds':info['seconds'],'usage':info['usage']}),flush=True)
    return info
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(generate,SCENES))
(OUT/'narration-usage.json').write_text(json.dumps(results,indent=2)+'\n')
print('Narration complete',sum(s['seconds'] for s in results),'seconds',flush=True)
