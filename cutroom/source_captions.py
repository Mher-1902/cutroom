"""Optional uploader-provided text; automatic captions never override local ASR."""
from collections import Counter
import json
from pathlib import Path
import re

from . import local_models,runtime
from .source_media import auth_arguments


def clean(text):
    return re.sub(r'\s+',' ',re.sub('[\u200b\u200e\u200f\ufeff]','',text)).strip()


def parse_json3(payload,duration):
    result=[];seen=set()
    for event in payload.get('events',[]):
        a=float(event.get('tStartMs',0))/1000
        b=min(duration,a+float(event.get('dDurationMs',0))/1000)
        if not 0<=a<b<=duration:
            continue
        chunks=[]
        for part in event.get('segs',[]):
            text=clean(part.get('utf8',''))
            if text:
                chunks.append((min(b,a+float(part.get('tOffsetMs',0))/1000),text))
        text=clean(' '.join(t for _,t in chunks))
        key=(round(a,3),round(b,3),text)
        if not text or key in seen:
            continue
        seen.add(key);words=[]
        for i,(at,phrase) in enumerate(chunks):
            end=chunks[i+1][0] if i+1<len(chunks) else b
            tokens=phrase.split()
            if end<=at:
                continue
            weights=[max(1,len(w)) for w in tokens];total=sum(weights);cursor=at
            for token,weight in zip(tokens,weights):
                right=cursor+(end-at)*weight/total
                words.append({'text':token,'start':cursor,'end':min(b,right),'confidence':None})
                cursor=right
        result.append({'start':a,'end':b,'text':text,'words':words,'text_source':'uploader_captions'})
    result.sort(key=lambda s:(s['start'],s['end']))
    for ident,item in enumerate(result):item['id']=ident
    return result


def agreement(reference,asr):
    def tokens(items):
        return Counter(re.findall(r'\w+',' '.join(s['text'] for s in items).lower()))
    left,right=tokens(reference),tokens(asr)
    return 2*sum((left&right).values())/max(1,sum(left.values())+sum(right.values()))


def fetch(studio,job,source,language):
    if 'url' not in job['source'] or language=='auto':
        return None
    cache=Path(job.get('imported_file',source)).parent
    record=cache/'source.json'
    metadata=json.loads(record.read_text()) if record.exists() else {}
    existing=metadata.get('human_caption_file')
    if existing and (cache/existing).is_file():
        return cache/existing
    if metadata.get('human_captions_checked'):
        return None
    base=[local_models.binary('yt-dlp'),'--ignore-config','--no-playlist','--no-progress',*auth_arguments(job['config'])]
    try:
        raw=json.loads(studio.run(job,base+['--skip-download','--dump-single-json','--',metadata.get('url',job['source']['url'])]))
        choices=[code for code in raw.get('subtitles',{}) if code.split('-')[0]==language.split('-')[0]]
        if choices:
            code=language if language in choices else choices[0]
            studio.event(job,'Importing matching uploader-provided captions to cross-check the local transcript.')
            studio.run(job,base+['--skip-download','--write-subs','--sub-langs',code,'--sub-format','json3',
                                '-o',str(cache/'captions'),'--',metadata.get('url',job['source']['url'])])
            target=cache/f'captions.{code}.json3'
            json.loads(target.read_text())
            metadata['human_caption_file']=target.name
        metadata['human_captions_checked']=True
        runtime.atomic_json(record,metadata)
        studio.update(job,source_metadata=metadata)
        return cache/metadata['human_caption_file'] if metadata.get('human_caption_file') else None
    except (RuntimeError,OSError,ValueError) as exc:
        studio.check_cancel(job['id'])
        studio.event(job,'Uploader captions unavailable; continuing with local Whisper and excerpt alignment. '+str(exc)[-120:])
        return None


def prefer(studio,job,source,folder,segments,language,duration):
    path=fetch(studio,job,source,language)
    provenance={'transcription':'whisper.cpp large-v3-turbo','preferred_text':'whisper','uploader_agreement':None}
    if path:
        human=parse_json3(json.loads(path.read_text()),duration)
        similarity=agreement(human,segments)
        provenance['uploader_agreement']=round(similarity,3)
        if len(human)>=2 and similarity>=.60:
            provenance.update(preferred_text='uploader_human_captions',caption_file=path.name,
                              note='Matching uploader text; selected excerpts still receive local audio forced alignment.')
            studio.event(job,f'Using uploader text after a {similarity:.0%} word-overlap cross-check; selected excerpts will be aligned to their actual audio.')
            segments=human
        else:
            studio.event(job,'Uploader text did not match the original audio transcript closely enough; retaining local ASR.')
    runtime.atomic_json(folder/'transcript-provenance.json',provenance)
    return segments


def discovery(studio,job,source,language,duration):
    """Optional human/automatic captions for scouting, never trusted final text."""
    if 'url' not in job['source']:
        return None
    from .resources import ResourcePause
    cache=Path(job.get('imported_file',source)).parent
    marker=cache/'discovery-captions.json'
    if marker.exists():
        saved=json.loads(marker.read_text())
        if saved.get('requested_language')==language and (cache/saved['file']).is_file():
            items=parse_json3(json.loads((cache/saved['file']).read_text()),duration)
            if items:return items,saved['language'],saved['origin']
    base=[local_models.binary('yt-dlp'),'--ignore-config','--no-playlist','--no-progress',*auth_arguments(job['config'])]
    try:
        raw=json.loads(studio.run(job,base+['--skip-download','--dump-single-json','--',job['source']['url']]))
        native=language if language!='auto' else str(raw.get('language') or '').split('-')[0]
        for field,flag,origin in [('subtitles','--write-subs','uploader_captions_discovery'),
                                  ('automatic_captions','--write-auto-subs','automatic_captions_discovery')]:
            available=raw.get(field,{})
            codes=[code for code in available if code!='live_chat' and native and code.split('-')[0]==native]
            if not codes:continue
            code=native if native in codes else codes[0]
            # Only a source-language track; never substitute a translated dub.
            studio.run(job,base+['--skip-download',flag,'--sub-langs',code,'--sub-format','json3',
                                '-o',str(cache/'discovery'),'--',job['source']['url']])
            target=cache/f'discovery.{code}.json3'
            items=parse_json3(json.loads(target.read_text()),duration)
            if items:
                runtime.atomic_json(marker,{'requested_language':language,'language':code.split('-')[0],
                                            'file':target.name,'origin':origin})
                return items,code.split('-')[0],origin
    except (OSError,ValueError,RuntimeError) as exc:
        if isinstance(exc,ResourcePause):raise
        studio.check_cancel(job['id'])
        studio.event(job,'Discovery captions unavailable; using checkpointed local transcription. '+str(exc)[-100:])
    return None
