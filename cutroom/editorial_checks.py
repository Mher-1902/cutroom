"""Small source-grounding checks for observed editorial failures."""
import json
import re

DANGLING={'a','an','the','and','but','because','how','that','to','their','your','with','if','when','although','whether','which','of','for','each'}
GAME=re.compile(r'\b(?:GTA|Grand Theft Auto)\s*(VI|IV|V|6|5|4)\b',re.I)
VERSIONS={'vi':'6','v':'5','iv':'4','6':'6','5':'5','4':'4'}
SENTENCE_END=re.compile(r'[.!?。！？][\s\"\'”’)]*$')


def game_versions(text):
    return {VERSIONS[m.group(1).lower()] for m in GAME.finditer(text)}


def source_identity(job,segments):
    title=job.get('source_metadata',{}).get('title') or job.get('source',{}).get('name','')
    text=title+'\n'+' '.join(s.get('text','') for s in segments)
    return {'source_title':title,'supported_gta_versions':sorted(game_versions(text))}


def copy_issue(copy,identity):
    # Only visible copy is checked; an editor's internal intentions are not UI.
    texts=[copy.get('title',''),copy.get('post_caption',''),copy.get('hook','')]
    texts.append((copy.get('screen_hook') or {}).get('text',''))
    texts.extend(o.get('text','') for o in (copy.get('overlays') or []))
    if copy.get('story_brief'):texts.append(json.dumps(copy['story_brief'],ensure_ascii=False))
    unsupported=game_versions(' '.join(texts))-set(identity['supported_gta_versions'])
    if unsupported:
        return 'Generated copy adds an unsupported GTA game version. Use only versions stated in the source title or speech; otherwise use a generic title and hook.'
    return None


def dangling(text):
    if re.search(r'[.!?。！？][\s\"\'”’)]*$',text.strip()):return False
    words=re.findall(r"[A-Za-z']+",text.lower())
    return bool(words and words[-1] in DANGLING)


def interval_tail(segments,start,end):
    words=[w for s in segments for w in s.get('words',[]) if start<=w['start']<w['end']<=end+.01]
    if words:return ' '.join(w['text'] for w in sorted(words,key=lambda w:w['start'])[-12:])
    rows=[s for s in segments if start<=s['start']<s['end']<=end+.01]
    return max(rows,key=lambda s:s['end'])['text'] if rows else ''


def sentence_rows(segments):
    """Measured complete speech units, independent of ASR's phrase chunks."""
    words=sorted((word for segment in segments for word in segment.get('words',[]) or [
        {k:segment[k] for k in ('start','end','text')}]),key=lambda w:w['start'])
    rows=[];current=[]
    for word in words:
        current.append(word)
        text=word['text'].strip()
        if SENTENCE_END.search(text) and text.lower() not in {'mr.','mrs.','dr.','ms.','vs.','e.g.','i.e.'}:
            rows.append({'start':current[0]['start'],'end':current[-1]['end'],
                         'text':' '.join(w['text'] for w in current),'words':current})
            current=[]
    return rows


def sentence_windows(segments,start,end,minimum,maximum,limit=32):
    rows=[r for r in sentence_rows(segments) if start<=r['start']<r['end']<=end]
    pairs=[[a['start'],b['end']] for a in rows for b in rows
           if minimum<=b['end']-a['start']<=maximum]
    # Preserve a spread of measured starts and lengths; the editor ranks them.
    if len(pairs)>limit:pairs=[pairs[round(i*(len(pairs)-1)/(limit-1))] for i in range(limit)]
    return {f'SENTENCE{i+1:03}':pair for i,pair in enumerate(pairs)}


def boundary_problems(plan,segments,language,source_mode):
    normal=[s for s in plan.get('spans',[]) if s['kind']=='normal' and not s.get('mute')]
    words=[w for s in segments for w in s.get('words',[]) if w.get('confidence') is None or w.get('confidence',1)>=.35]
    problems=[]
    for span in normal:
        for key,out,action in (('start',span['out_start'],'more_context'),('end',span['out_end'],'tighten')):
            if any(w['start']+.055<span[key]<w['end']-.075 for w in words):
                problems.append({'at':max(0,min(plan['duration'],out)),
                    'issue':f'The source cut at {span[key]:.3f}s falls inside an aligned spoken word. Use a real word boundary.',
                    'action':action})
    if normal and language=='en' and source_mode in {'tutorial','story'}:
        rows=sentence_rows(segments)
        first,last=normal[0],normal[-1]
        for row in rows:
            if row['start']+.15<first['start']<row['end']-.15:
                problems.append({'at':first['out_start'],'issue':'The narrated opening starts partway through a source sentence. Retain the complete setup sentence.','action':'more_context'})
            if row['start']+.15<last['end']<row['end']-.15:
                problems.append({'at':max(0,last['out_end']-1),'issue':'The narrated ending omits the rest of its source sentence. Retain the complete takeaway.','action':'tighten'})
    return problems


def review_problems(plan,mapped,job,source_segments,language,aligned=None,source_mode=None):
    problems=[]
    issue=copy_issue(plan,source_identity(job,source_segments))
    if issue:problems.append({'at':0,'issue':issue,'action':'more_context'})
    problems.extend(boundary_problems(plan,aligned if aligned is not None else source_segments,language,source_mode))
    if language=='en' and mapped:
        last=max(mapped,key=lambda s:s['end'])
        if plan['duration']-last['end']<1 and dangling(last['text']):
            problems.append({'at':max(0,plan['duration']-2),'issue':'The edit cuts the final spoken sentence off mid-thought. End after a complete source sentence or takeaway.','action':'tighten'})
    return problems
