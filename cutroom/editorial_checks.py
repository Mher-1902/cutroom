"""Small source-grounding checks for observed editorial failures."""
import json
import re

DANGLING={'a','an','the','and','but','because','how','that','to','their','your','with','if','when','although','whether','which','of','for','each'}
GAME=re.compile(r'\b(?:GTA|Grand Theft Auto)\s*(VI|IV|V|6|5|4)\b',re.I)
VERSIONS={'vi':'6','v':'5','iv':'4','6':'6','5':'5','4':'4'}


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


def review_problems(plan,mapped,job,source_segments,language):
    problems=[]
    issue=copy_issue(plan,source_identity(job,source_segments))
    if issue:problems.append({'at':0,'issue':issue,'action':'more_context'})
    if language=='en' and mapped:
        last=max(mapped,key=lambda s:s['end'])
        if plan['duration']-last['end']<1 and dangling(last['text']):
            problems.append({'at':max(0,plan['duration']-2),'issue':'The edit cuts the final spoken sentence off mid-thought. End after a complete source sentence or takeaway.','action':'tighten'})
    return problems
