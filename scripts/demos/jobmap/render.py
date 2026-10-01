"""Render the real browser capture with scene-aligned Charon narration."""
from pathlib import Path
import json,subprocess,hashlib,re,shutil
root=Path(__file__).resolve().parents[3];work=root/'artifacts/jobmap-demo-work';dest=root/'artifacts/jobmap-demo';dest.mkdir(exist_ok=True)
capture=json.loads((work/'capture.json').read_text());assert len(capture['marks'])==6 and not capture['errors']
chapters=[];transcript=['Jobmap: finding work building AI agents','English AI narration: Gemini Charon',''];vtt=['WEBVTT',''];clock=0

def timestamp(seconds):
 millis=round(seconds*1000);h,millis=divmod(millis,3600000);m,millis=divmod(millis,60000);s,ms=divmod(millis,1000)
 return f'{h:02}:{m:02}:{s:02}.{ms:03}'
for scene in capture['marks']:
 duration=scene['end']-scene['start'];name=scene['id']
 assert duration>=scene['audioSeconds']+.5
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(scene['start']),'-i',str(work/'raw.webm'),'-i',str(work/(name+'.wav')),'-t',str(duration),'-map','0:v:0','-map','1:a:0','-vf','fps=30,setsar=1','-af','loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,adelay=500:all=1,apad','-c:v','libx264','-threads','4','-preset','medium','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(work/(name+'.mp4'))],check=True)
 chapters.append({'id':name,'start':round(clock,3),'end':round(clock+duration,3),'text':scene['text']})
 transcript.append(f'{timestamp(clock)} {name}\n{scene["text"]}\n')
 words=scene['text'].split()
 for start in range(0,len(words),12):
  end=min(start+12,len(words));a=clock+.5+scene['audioSeconds']*start/len(words);b=clock+.5+scene['audioSeconds']*end/len(words)
  vtt.extend([f'{timestamp(a)} --> {timestamp(b)}',' '.join(words[start:end]),''])
 clock+=duration
(work/'concat.txt').write_text('\n'.join("file '"+s['id']+".mp4'" for s in capture['marks'])+'\n')
video=dest/'jobmap-ai-agents-narrated.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(work/'concat.txt'),'-c','copy','-movflags','+faststart',str(video)],check=True)
(dest/'jobmap-ai-agents-transcript.txt').write_text('\n'.join(transcript))
(dest/'jobmap-ai-agents-en.vtt').write_text('\n'.join(vtt))
capture.update({'chapters':chapters,'durationSeconds':clock,'narration':{'provider':'Gemini','model':'gemini-3.1-flash-tts-preview','voice':'Charon','language':'en'},'captions':'Sentence-order captions timed proportionally within each narration scene; not word-level forced alignment','sha256':hashlib.sha256(video.read_bytes()).hexdigest()})
(dest/'capture.json').write_text(json.dumps(capture,indent=2)+'\n')
shutil.copy2(work/'narration-usage.json',dest/'narration-usage.json')
print(json.dumps({'video':str(video),'seconds':clock,'sha256':capture['sha256']}))
