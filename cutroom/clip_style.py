"""Restyle a saved edit from its original media without loading an LLM."""
from copy import deepcopy
import json
import math
from pathlib import Path

from . import caption_styles, render_v2, runtime
from .contracts import remap_words


def speech(studio, job, clip):
    folder=studio.jobs_dir/job['id']
    path=folder/f"aligned-{clip['id']}.json"
    if not path.exists():
        path=folder/'segments.json'
    return json.loads(path.read_text())


def editor(studio,job,clip_id):
    clip=next((c for c in job['clips'] if c['id']==clip_id),None)
    if not clip:
        raise ValueError('Clip not found.')
    plan=clip['edit_plan']
    mapped=remap_words(speech(studio,job,clip),plan)
    mapped=caption_styles.corrections(mapped,plan.get('caption_edits',{}))
    return {'clip_id':clip_id,'revision':clip.get('revision',0),
            'caption_settings':caption_styles.settings(plan.get('caption_settings',job['config'].get('caption_settings'))),
            'words':caption_styles.words(mapped),'layout':plan['layout'],
            'caption_enabled':plan.get('caption_enabled',job['config'].get('style')!='none'),
            'focus_x':plan['focus'][0]+plan['focus'][2]/2,'video':clip['video'],
            'hook_text':next((o['text'] for o in plan['overlays'] if o.get('story_role')=='hook' or o['kind']=='hook'),plan.get('hook',''))}


def validate_request(studio,job,clip,raw):
    if not isinstance(raw,dict) or set(raw)-{'caption_settings','caption_edits','layout','focus_x','revision','hook_text','caption_enabled'}:
        raise ValueError('Unknown style setting.')
    if raw.get('revision')!=clip.get('revision',0):
        raise ValueError('This clip has changed. Reopen Style & captions before saving.')
    prefs=caption_styles.settings(raw.get('caption_settings'))
    enabled=raw.get('caption_enabled',clip['edit_plan'].get('caption_enabled',job['config'].get('style')!='none'))
    if type(enabled) is not bool:
        raise ValueError('Caption visibility must be on or off.')
    edits=raw.get('caption_edits',{})
    mapped=remap_words(speech(studio,job,clip),clip['edit_plan'])
    caption_styles.corrections(mapped,edits)
    layout=raw.get('layout','keep')
    if layout not in {'keep','fit','crop'}:
        raise ValueError('Choose the current framing, full frame or portrait crop.')
    x=raw.get('focus_x',.5)
    if type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1:
        raise ValueError('Choose a framing center between 0 and 1.')
    hook=raw.get('hook_text')
    if hook is not None and (not isinstance(hook,str) or not 1<=len(hook.strip())<=75 or any(ord(c)<32 for c in hook)):
        raise ValueError('Keep the opening title on one line, between 1 and 75 characters.')
    return {'caption_settings':prefs,'caption_edits':edits,'layout':layout,'focus_x':x,'revision':raw['revision'],'hook_text':hook,'caption_enabled':enabled}


def restyle(studio,job):
    request=job['pending_style']
    folder=studio.jobs_dir/job['id']
    old=next(c for c in job['clips'] if c['id']==request['clip_id'])
    source=Path(job['source_file'])
    if not source.is_file():
        raise ValueError('The original media is missing. Restore it to render the new style; your saved export is preserved.')
    plan=deepcopy(old['edit_plan'])
    plan['caption_settings']=request['caption_settings']
    plan['caption_enabled']=request.get('caption_enabled',True)
    plan['caption_edits']={**plan.get('caption_edits',{}),**request['caption_edits']}
    if request.get('hook_text'):
        hook=request['hook_text'].strip()
        plan['hook']=hook
        plan.setdefault('screen_hook',{}).update(enabled=True,text=hook)
        for beat in plan.get('story_structure',[]):
            if beat['key']=='hook':beat['intent']=hook
        hooks=[o for o in plan['overlays'] if o.get('story_role')=='hook' or o['kind']=='hook']
        if hooks:
            for overlay in hooks:overlay['text']=hook
        else:
            plan['overlays'].append({'at':0,'duration':min(3,plan['duration']*.1),'kind':'hook','story_role':'hook','text':hook})
    if request['layout']!='keep':
        plan['layout']=request['layout']
        fraction=min(1,(9/16)/(job['metadata']['width']/job['metadata']['height']))
        x=max(0,min(1-fraction,request['focus_x']-fraction/2))
        plan['focus']=[x,0,fraction,1] if plan['layout']=='crop' else [0,0,1,1]
        for span in plan['spans']:
            span.pop('layout',None)
            span.pop('focus',None)
    index=json.loads((folder/'scene-index.json').read_text())
    aligned=speech(studio,job,old)
    revisions=[old.get('revision',0)]+[int(p.stem.rsplit('-r',1)[1]) for p in folder.glob(f"plan-{old['id']}-r*.json")]
    # Reuse this revision if a restyle render was interrupted; fingerprints
    # distinguish complete output from a partial or changed request.
    revision=request.setdefault('render_revision',max(revisions)+1)
    studio.update(job,stage='Rendering style & captions',progress=75)
    runtime.atomic_json(folder/f"plan-{old['id']}-r{revision}.json",plan)
    studio.event(job,'Rendering your caption style from the original media. AI analysis is reused; no model is loaded.')
    record=render_v2.render(studio,job,source,plan,aligned,index,job['metadata'],folder,revision,final=True)
    studio.update(job,stage='Checking styled export',progress=95)
    technical=render_v2.technical_qc(studio,job,record['path'],plan['duration'],job['config'].get('resolution',1080))
    if not technical['passed']:
        raise RuntimeError('The new style failed the export checks. Your previous video remains available. '+str(technical.get('failures',[])))
    cover=record['path'].with_suffix('.jpg')
    render_v2.create_cover(studio,job,record['path'],plan['title'],cover)
    new=deepcopy(old)
    new.update(edit_plan=plan,revision=revision,
               video=f"/files/{job['id']}/{record['path'].name}",thumbnail=f"/files/{job['id']}/{cover.name}",
               subtitles=f"/files/{job['id']}/{record['srt'].name}",editable_captions=f"/files/{job['id']}/{record['ass'].name}",
               transcript=' '.join(s['text'] for s in record['mapped']),
               style_review={'technical':technical,'requires_visual_preview':True,
                             'note':'Style updated. Watch the new preview; the score belongs to the previous AI-reviewed edit.'})
    new.setdefault('prior_exports',[]).append({k:old.get(k) for k in ('video','thumbnail','score','revision','edit_plan','style_review')})
    job['clips'][job['clips'].index(old)]=new
    job.pop('latest_draft',None)
    states_path=folder/'candidate-progress.json'
    states=json.loads(states_path.read_text()) if states_path.exists() else {}
    if old['id'] in states:
        states[old['id']]['latest_plan']=plan
        runtime.atomic_json(states_path,states)
    if job.get('processing_strategy',{}).get('mode')=='long_stream':
        from .longform import store
        tasks=store(job,source,folder)
        ident='clip-'+old['id']
        if tasks.get(ident):tasks.set(ident,'complete',result=new)
    job.pop('pending_style',None)
    from .pipeline_v2 import package
    package(studio,job,folder,states,index)
    studio.event(job,'New style is ready to watch. MP4, subtitles, cover and ZIP updated; previous export preserved.')
