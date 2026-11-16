"""Bounded native audio scanning. Peaks propose inspection; they never qualify edits."""
from bisect import bisect_left, insort
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import re

from . import local_models, runtime, source_cache
from .render_v2 import filter_path

VERSION=2


def parse_stats(text,offset=0):
    rows=[];current=None
    for line in text.splitlines():
        found=re.search(r'pts_time:([-+0-9.eE]+)',line)
        if found:
            if current and 'rms_db' in current and 'peak_db' in current:rows.append(current)
            current={'at':offset+float(found[1])+.25}
        elif current is not None:
            for label,key in [('RMS_level','rms_db'),('Peak_level','peak_db')]:
                if line.startswith('lavfi.astats.Overall.'+label+'='):
                    value=float(line.split('=',1)[1]);current[key]=max(-100,min(0,value)) if math.isfinite(value) else -100
    if current and 'rms_db' in current and 'peak_db' in current:rows.append(current)
    return rows


def peaks(rows,limit=384):
    """Relative changes plus loud sustained regions, with time/section diversity."""
    history=deque();ordered=[];scored=[]
    for row in rows:
        if ordered:
            baseline=ordered[len(ordered)//2]
            lift=row['rms_db']-baseline
            if len(history)>=8 and row['rms_db']>-40 and (lift>=4 or row['rms_db']>=-12):
                # A clipped game impact alone is not proof of a human reaction.
                score=max(0,lift)*.3+max(0,row['rms_db']+40)*.7
                scored.append({**row,'lift_db':round(lift,2),'proposal_score':round(score,2)})
        history.append(row['rms_db']);insort(ordered,row['rms_db'])
        if len(history)>120:ordered.pop(bisect_left(ordered,history.popleft()))
    selected=[]
    for section in sorted({int(r['at']//1800) for r in scored}):
        group=[r for r in scored if int(r['at']//1800)==section]
        for key in ('rms_db','lift_db'):
            added=0
            for row in sorted(group,key=lambda r:r[key],reverse=True):
                if any(abs(row['at']-r['at'])<18 for r in selected):continue
                selected.append(row);added+=1
                if added==6:break
    return sorted(selected,key=lambda r:r['proposal_score'],reverse=True)[:limit]


def caption_cues(segments,maximum=144):
    cues=[];seen=set()
    for item in segments:
        text=item['text'].lower();words=re.findall(r"[a-z']+",text)
        # Rolling captions often repeat an earlier line: deduplicate before
        # counting intensity. These remain proposals, not proof of excitement.
        fingerprint=(round(item['start']/3),' '.join(words))
        if fingerprint in seen:continue
        seen.add(fingerprint)
        repeated=max((len(list(g)) for _,g in __import__('itertools').groupby(words)),default=0)
        score=6*len(re.findall(r'\b(?:a+h+|o+h+|no+|ye+s+|wo+w+){1}\b',text)) if re.search(r'([a-z])\1{3,}',text) else 0
        score+=sum(text.count(phrase)*weight for phrase,weight in
                   [('oh my god',5),('no way',5),("let's go",4),('what the fuck',3),('what the hell',3),('laugh',6),('scream',6),('shout',5)])
        score+=max(0,repeated-2)*4
        if score>=4:cues.append({'at':item['start']+.5,'proposal_score':score,'cue_source':'transcript','cue_text':item['text'][:200]})
    selected=[];sections={}
    for cue in sorted(cues,key=lambda c:c['proposal_score'],reverse=True):
        section=int(cue['at']//1800)
        if sections.get(section,0)>=6 or any(abs(cue['at']-c['at'])<15 for c in selected):continue
        selected.append(cue);sections[section]=sections.get(section,0)+1
        if len(selected)>=maximum:break
    return selected


def scan(studio,job,source,folder,duration):
    directory=folder/'highlight-audio';directory.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(json.dumps({'source':source_cache.fingerprint(source),'version':VERSION},sort_keys=True).encode()).hexdigest()
    rows=[];count=math.ceil(duration/1800)
    for n in range(count):
        studio.check_cancel(job['id'])
        target=directory/f'energy-{n:03}.json'
        cached=json.loads(target.read_text()) if target.exists() else {}
        if cached.get('identity')==identity:
            rows.extend(cached['rows']);continue
        start=n*1800;length=min(1800,duration-start)
        stats=directory/f'energy-{n:03}.txt'
        studio.event(job,f'Listening for reaction bursts: audio section {n+1}/{count}. No full-stream PCM is stored.')
        studio.run(job,[local_models.binary('ffmpeg'),'-hide_banner','-loglevel','error','-nostdin','-y',
            '-ss',str(start),'-t',str(length),'-i',str(source),'-vn','-ac','1','-ar','8000',
            '-af','aresample=8000,asetnsamples=n=4000:p=0,astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=RMS_level+Peak_level,'
                  +"ametadata=mode=print:file='"+filter_path(stats)+"'",'-threads','2','-f','null','-'],timeout=600)
        result=parse_stats(stats.read_text(),start)
        if abs(len(result)-math.ceil(length*2))>3:raise RuntimeError('The audio reaction scan did not cover its section at the expected half-second sample rate. Resume reuses completed sections.')
        runtime.atomic_json(target,{'identity':identity,'rows':result})
        stats.unlink(missing_ok=True);rows.extend(result)
    result={'version':VERSION,'identity':identity,'duration':duration,'covered_seconds':min(duration,len(rows)*.5),
            'complete':abs(len(rows)-math.ceil(duration*2))<=count*3,'proposals':peaks(rows)}
    runtime.atomic_json(directory/'energy-summary.json',result)
    return result
