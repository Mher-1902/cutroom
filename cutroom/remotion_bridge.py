"""Compile safe edit records to editable Remotion projects and real MP4 exports."""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import atexit
import socket

_studios={}


@atexit.register
def stop_studios():
    for process in _studios.values():
        if process.poll() is None:process.terminate()


def open_studio(studio, job):
    """Queued preparation reuses analysis and preserves existing qualified MP4s."""
    from .clip_style import speech
    request=job['pending_remotion']
    clip=next(c for c in job['clips'] if c['id']==request['clip_id'])
    folder=studio.jobs_dir/job['id']
    plan=clip['edit_plan']
    revision=clip.get('revision',0)
    workspace=folder/'remotion'/f"{clip['id']}-r{revision}-final"
    if not available(studio.root):raise ValueError('Install Remotion first: cd remotion && npm ci')
    if not (workspace/'index.tsx').exists():
        studio.update(job,stage='Preparing Remotion Studio',progress=75)
        prepare(studio,job,Path(job['source_file']),plan,speech(studio,job,clip),
                json.loads((folder/'scene-index.json').read_text()),job['metadata'],folder,revision,True)
    key=str(workspace)
    process=_studios.get(key)
    if process is None or process.poll() is not None:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        tool=studio.root/'remotion'
        log=workspace/'studio.log'
        with log.open('a') as output:
            process=subprocess.Popen([shutil.which('node'),'-r',str(tool/'loopback.cjs'),
                str(tool/'node_modules/@remotion/cli/remotion-cli.js'),'studio',str(workspace/'index.tsx'),
                '--port='+str(port),'--no-open','--ipv4','--config='+str(tool/'remotion.config.ts')],
                cwd=workspace,stdout=output,stderr=output,start_new_session=True)
        _studios[key]=process
        from urllib.request import urlopen
        for _ in range(120):
            studio.check_cancel(job['id'])
            if process.poll() is not None:raise RuntimeError('Remotion Studio could not open: '+log.read_text()[-1500:])
            try:
                with urlopen(f'http://127.0.0.1:{port}',timeout=.5) as response:
                    if response.status==200:break
            except OSError:time.sleep(.25)
        else:
            process.terminate();raise RuntimeError('Remotion Studio did not become ready. Retry Open Remotion Studio.')
        clip['remotion_studio']={'url':f'http://127.0.0.1:{port}/Cutroom','revision':revision,
                                'note':'Studio edits are saved locally. Studio renders are separate exports; Cutroom refinements rebuild from its edit plan.'}
    job.pop('pending_remotion',None)
    studio.save(job)
    studio.event(job,'Remotion Studio is ready. Your saved MP4 is preserved. Preview, edit layers, and render in Studio.')

from . import caption_styles, core, runtime
from .remotion_knowledge import RUNTIME_VERSION


def available(root):
    root=Path(root)/'remotion'
    return shutil.which('node') is not None and (root/'node_modules/@remotion/cli/remotion-cli.js').is_file()


def js(value):
    # JSON string literals cannot become JSX, imports or executable code.
    return json.dumps(value,ensure_ascii=True,allow_nan=False)


def attributes(**props):
    return ' '.join(name+'={'+js(value)+'}' for name,value in props.items())


def captions_for(words, start, end, origin, upper=False):
    return [{'text':(' ' if i else '')+(w['text'].upper() if upper else w['text']),
             'startMs':round((max(start,w['start'])-origin)*1000),
             'endMs':round((min(end,w['end'])-origin)*1000),'timestampMs':None,'confidence':None}
            for i,w in enumerate(words) if w['start']<end and w['end']>start]


def compile_project(root, workspace, plan, mapped, suppressed, config, base):
    """One authored JSX node per editable layer; no transcript-generated code."""
    workspace=Path(workspace)
    public=workspace/'public'
    public.mkdir(parents=True,exist_ok=True)
    # Only the prepared short and OFL fonts are exposed to Studio, not the source library.
    media=public/'prepared.mp4'
    if not media.exists() or media.stat().st_ino!=base.stat().st_ino:
        media.unlink(missing_ok=True)
        try: os.link(base,media)
        except OSError: shutil.copy2(base,media)
    for file in (Path(root)/'static/fonts/captions').iterdir():
        if file.suffix in {'.ttf','.txt'}:shutil.copy2(file,public/file.name)
    modules=workspace/'node_modules'
    if not modules.exists():modules.symlink_to(Path(root)/'remotion/node_modules',target_is_directory=True)
    (workspace/'package.json').write_text(js({'name':'cutroom-private-edit','private':True,'version':'1.0.0'}))
    shared=Path(root)/'remotion/src/Cutroom'
    prefs=caption_styles.settings(plan.get('caption_settings',config.get('caption_settings')))
    y={'lower':1450,'middle':1130,'upper':570}.get(prefs['position'],1400 if plan['layout']=='fit' else 1330)
    width=int(config.get('resolution',1080))
    height=round(width*16/9/2)*2
    total=math.ceil(plan['duration']*30)
    nodes=[]
    words=caption_styles.words(mapped)
    mode=config.get('style','auto')
    if mode=='auto':mode=plan.get('caption_style','kinetic')
    for i,span in enumerate(plan['spans']):
        a=round(span['out_start']*30)
        b=total if i==len(plan['spans'])-1 else min(total,round(span['out_end']*30))
        if b<=a:continue
        nodes.append(f'<Sequence name="Scene {i+1}" from={{{a}}} trimBefore={{{a}}} durationInFrames={{{b-a}}} premountFor={{fps}}>')
        nodes.append('<Video src={staticFile("prepared.mp4")} premountFor={fps} style={{width:1080,height:1920,objectFit:"fill"}} />')
        if plan.get('caption_enabled',mode!='none'):
            current=[];groups=[]
            measure=caption_styles.font_measure(prefs['font'],prefs['size'])
            for word in words:
                if not span['out_start']<=word['start']<span['out_end']:continue
                if any(word['start']<end and word['end']>start for start,end in suppressed):continue
                if current and (len(current)>=prefs['max_words'] or word['start']-current[-1]['end']>.4 or
                                measure(' '.join(w['text'] for w in current+[word]))>850):
                    groups.append(current);current=[]
                current.append(word)
            if current:groups.append(current)
            for group in groups:
                start=max(a,round(group[0]['start']*30));end=min(b,math.ceil(group[-1]['end']*30))
                if end<=start:continue
                caps=captions_for(group,start/30,end/30,start/30,prefs['case']=='uppercase')
                props={'from':start,'durationInFrames':end-start,'captions':caps,
                       'accent':prefs['accent'],'size':prefs['size'],'font':caption_styles.FONTS[prefs['font']],
                       'y':y,'animation':prefs['animation']}
                nodes.append('<CutroomCaptions premountFor={fps} '+attributes(**props)+' />')
        nodes.append('</Sequence>')
    motion='fade' if plan.get('music_mood') in {'relaxed','tension'} else 'pop'
    for cue in plan.get('overlays',[]):
        start=max(0,round(cue['at']*30));end=min(total,round((cue['at']+cue['duration'])*30))
        if end<=start:continue
        size=72 if cue['kind']=='hook' else 62
        while len(caption_styles.wrap(cue['text'],prefs['font'],size))>3 and size>48:size-=4
        title_y=1530 if prefs['position']=='upper' else (370 if plan['layout']!='fit' else 340)
        nodes.append('<CutroomTitle '+attributes(**{'from':start,'durationInFrames':end-start,'premountFor':30,
            'text':cue['text'],'accent':prefs['accent'],'y':title_y,'size':size,'motion':motion})+' />')
    for span in plan['spans']:
        if span['kind']=='replay':
            nodes.append(f'<Sequence name="Replay label" from={{{round(span["out_start"]*30)}}} durationInFrames={{{max(1,round(span["duration"]*30))}}} premountFor={{30}}><div style={{{{position:"absolute",top:180,left:85,fontFamily:"Cutroom Sans",fontSize:36,color:"white",textShadow:"0 2px 4px black"}}}}>REPLAY</div></Sequence>')
    if config.get('watermark_text'):
        position=config.get('watermark_position','top-right')
        style={'position':'absolute','fontFamily':'Cutroom Studio','fontSize':28,'color':'white',
               'opacity':config.get('watermark_opacity',.2),'textShadow':'0 2px 3px black',
               'top' if position.startswith('top') else 'bottom':115 if position.startswith('top') else 200,
               'left' if position.endswith('left') else 'right':65}
        nodes.append('<div style={'+js(style)+'}>{'+js(config['watermark_text'])+'}</div>')
    code='''import React from 'react';
import {AbsoluteFill,Composition,Sequence,registerRoot,staticFile,useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';
import {CutroomCaptions,CutroomTitle} from SHARED;
const Edit=()=> {const {fps}=useVideoConfig();return <AbsoluteFill style={{backgroundColor:'black'}}><div style={{position:'absolute',width:1080,height:1920,transform:'scale(SCALE)',transformOrigin:'top left'}}>
NODES
</div></AbsoluteFill>;};
const Root=()=> <Composition id="Cutroom" component={Edit} durationInFrames={TOTAL} fps={30} width={WIDTH} height={HEIGHT}/>;
registerRoot(Root);
'''.replace('SHARED',js(str(shared))).replace('SCALE',str(width/1080)).replace('TOTAL',str(total)).replace('WIDTH',str(width)).replace('HEIGHT',str(height)).replace('NODES','\n'.join(nodes))
    (workspace/'index.tsx').write_text(code)
    runtime.atomic_json(workspace/'edit-plan.json',plan)
    runtime.atomic_json(workspace/'manifest.json',{'version':1,'runtime':RUNTIME_VERSION,'duration':plan['duration'],
                                                'width':width,'height':height,'frames':total,'fps':30})
    return workspace


def prepare(studio,job,source,plan,segments,index,metadata,folder,revision=0,final=False):
    from . import render_v2
    workspace=folder/'remotion'/f"{plan['id']}-r{revision}-{'final' if final else 'draft'}"
    basefolder=workspace/'media'
    basefolder.mkdir(parents=True,exist_ok=True)
    clean=deepcopy(job)
    clean['config'].update(render_engine='ffmpeg',_clean_graphics=True)
    record=render_v2.render(studio,clean,source,plan,segments,index,metadata,basefolder,revision,final)
    _,mapped,preserved=render_v2.make_ass(plan,segments,index,job['config'].get('style','auto'),job['config'])
    config={**job['config'],'resolution':job['config'].get('resolution',1080) if final else 720}
    compile_project(studio.root,workspace,plan,mapped,render_v2.source_caption_intervals(index,plan),config,record['path'])
    return workspace,record,mapped,preserved


def render(studio,job,source,plan,segments,index,metadata,folder,revision=0,final=False):
    if not available(studio.root):
        raise RuntimeError('Remotion is not installed. Run npm ci inside the remotion folder, or choose Classic finishing in Make it yours. Your analysis is saved.')
    from . import render_v2
    started=time.monotonic()
    stem=f"c-{plan['id']}-r{revision}-{'final' if final else 'draft'}"
    target=folder/(stem+'.mp4');marker=folder/(stem+'.complete.json')
    fingerprint=hashlib.sha256(json.dumps({'remotion':RUNTIME_VERSION,'bridge':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'plan':plan,'config':job['config'],
        'index':index,'segments':segments,'source':[str(source),source.stat().st_size,source.stat().st_mtime_ns],
        'component':(studio.root/'remotion/src/Cutroom.tsx').read_text(),
        'renderer':(studio.root/'remotion/render.mjs').read_text()},sort_keys=True).encode()).hexdigest()
    previous=json.loads(marker.read_text()) if marker.exists() else {}
    ass,mapped,preserved=render_v2.make_ass(plan,segments,index,job['config'].get('style','auto'),job['config'])
    ass_path=folder/(stem+'.ass');srt_path=folder/(stem+'.srt')
    ass_path.write_text(ass);srt_path.write_text(render_v2.srt(mapped))
    if target.exists() and previous.get('fingerprint')==fingerprint and previous.get('bytes')==target.stat().st_size:
        return {'path':target,'ass':ass_path,'srt':srt_path,'mapped':mapped,'preserved_caption_intervals':preserved,
                'render_seconds':0,'cache_hit':True,'encoder':'Remotion / H.264','assets':previous.get('assets',[])}
    marker.unlink(missing_ok=True)
    for suffix in ('.review.json','.visual-review.json','.story-review.json'):
        (folder/(stem+suffix)).unlink(missing_ok=True)
    workspace,base,mapped,preserved=prepare(studio,job,source,plan,segments,index,metadata,folder,revision,final)
    temporary=folder/(stem+'.partial.mp4')
    tool=studio.root/'remotion'
    studio.event(job,'Remotion is composing word highlights, animated story titles and watermark from the saved edit plan.')
    try:
        studio.run(job,[shutil.which('node'),'-r',str(tool/'loopback.cjs'),str(tool/'render.mjs'),str(workspace),str(temporary)],timeout=1800)
        from . import local_models
        probe=json.loads(studio.run(job,[local_models.binary('ffprobe'),'-v','error','-show_format','-of','json',str(temporary)]))
        if abs(float(probe['format']['duration'])-plan['duration'])>.25:raise RuntimeError('Incomplete Remotion render. Resume retries this edit.')
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    seconds=round(time.monotonic()-started,2)
    runtime.atomic_json(marker,{'fingerprint':fingerprint,'bytes':target.stat().st_size,'encoder':'Remotion / H.264',
                               'render_seconds':seconds,'assets':base.get('assets',[])})
    runtime.atomic_json(folder/(stem+'.assets.json'),{'assets':base.get('assets',[]),'caption_intervals_preserved':preserved,
                                                   'renderer':'Remotion','runtime':RUNTIME_VERSION})
    return {'path':target,'ass':ass_path,'srt':srt_path,'mapped':mapped,'assets':base.get('assets',[]),
            'preserved_caption_intervals':preserved,'render_seconds':seconds,'cache_hit':False,'encoder':'Remotion / H.264'}
