"""Checkpointed analyze → direct → draft → critique → revise → export workflow."""
from copy import deepcopy
import json
from pathlib import Path
import time
import zipfile

from . import analysis, core, director, render_v2, runtime, source_media, source_cache
from .contracts import ClipEditPlan, DraftReview, REVIEW_WEIGHTS
from .source_policy import strategy


def calibration_text(index_duration, segments, attention_hint=0,visual=None):
    windows = [(0,min(index_duration,240))]
    if attention_hint > 240:
        windows.append((max(0,attention_hint-120),min(index_duration,attention_hint+120)))
    return json.dumps({"source_duration":index_duration,"allowed_windows":windows,"visual_observations":visual,
                       "segments":[s for a,b in windows for s in analysis.compact_speech(segments,a,b)
                                   if a<=s['start']<s['end']<=b]},ensure_ascii=False,separators=(',',':'))


def review_context(candidate,index,segments):
    return {"candidate":{k:candidate.get(k) for k in ("title","setup","payoff","reason","start","end")},
            "close_visual_observations":candidate.get("fine_evidence"),
            "neighboring_speech":[{k:s[k] for k in ("start","end","text")} for s in segments
                                  if s["end"]>candidate["start"]-8 and s["start"]<candidate["end"]+8],
            "source_mode":index["mode"]}


def combined_review(visual,story,technical):
    metrics=deepcopy(visual["metrics"])
    for key in ("hook","clarity","payoff","pacing"):
        value=float(story[key])
        if not 1<=value<=5:
            raise ValueError("The story critic returned an invalid score")
        metrics[key]=min(metrics[key],value) if key=="pacing" else value
    return {**visual,"metrics":metrics,"score":round(sum(metrics[k]*REVIEW_WEIGHTS[k] for k in metrics)*20),
            "reject":bool(visual["reject"] or story["reject"] or not technical["passed"] or
                          not visual.get('structure_passed',True) or not story.get('structure_passed',True)),
            "reason":str(story["reason"])[:900]+" "+str(visual["reason"])[:900],
            "weakness":str(story["weakness"])[:500]+" "+str(visual["weakness"])[:500],
            "story_critic":story,"technical":technical}


def package(studio,job,folder,states,index):
    used={}
    for clip in job['clips']:
        path=folder/(Path(clip['video']).stem+'.assets.json')
        if path.exists():
            for asset in json.loads(path.read_text()).get('assets',[]):
                used[asset['id']]=asset
    report={"pipeline_version":2,"source":job.get("source_metadata",job["source"]),"config":{k:v for k,v in job["config"].items() if k!="youtube_auth"},
            "measured_stage_seconds":job.get('stage_seconds',{}),"analysis_reused_from":job.get('analysis_reused_from'),
            "processing_strategy":job.get('processing_strategy'),"scout_progress":job.get('scout_progress'),
            "resource_metrics":job.get('resource_metrics'),
            "models":runtime.profile(studio.data),"rubric_weights":REVIEW_WEIGHTS,
            "score_note":"Editorial quality out of 100. Future views are uncertain.",
            "originality":{"declared_source_origin":job["config"].get("source_origin","unknown"),
                "creator_rewards_eligibility":"not_verified",
                "note":"Editing, captions, music and reframing do not establish ownership or originality. This report does not certify TikTok Creator Rewards eligibility."},
            "coverage":{"duration":index["duration"],"frames":index["frames_analyzed"],"fps":index["frame_sampling_fps"],"blocks":len(index["blocks"]),
                        "complete":index.get('coverage_complete',True),"failed_scouts":index.get('failed_scouts',[]),
                        "note":index.get('observation_note')},
            "candidates":states,"clips":job["clips"],"validation_scope":job.get('validation_scope'),"failure_summary":job.get('failure_summary'),"inference":job.get("inference",[]),
            "licensed_finishing_assets":list(used.values()),
            "transcript_provenance":json.loads((folder/'transcript-provenance.json').read_text()) if (folder/'transcript-provenance.json').exists() else {'preferred_text':'whisper'},
            "timeline_normalization":json.loads((folder/'normalization.json').read_text()) if (folder/'normalization.json').exists() else {'original_container_start':0}}
    runtime.atomic_json(folder/"analysis.json",report)
    temporary=folder/"clips.partial.zip"
    with zipfile.ZipFile(temporary,"w",zipfile.ZIP_STORED) as archive:
        for clip in job["clips"]:
            prefix=f"{clip['rank']:02}-"+clip["id"][:8]
            for key,extension in [("video","mp4"),("thumbnail","jpg"),("subtitles","srt"),("editable_captions","ass")]:
                source=folder/Path(clip[key]).name
                if source.exists():
                    archive.write(source,prefix+"."+extension)
            archive.writestr(prefix+"-post.txt",clip.get("post_caption","")+"\n")
            archive.writestr(prefix+"-edit.json",json.dumps(clip["edit_plan"],ensure_ascii=False,indent=2))
        archive.write(folder/"analysis.json","analysis.json")
        archive.writestr('assets-used.json',json.dumps(list(used.values()),ensure_ascii=False,indent=2))
        licenses=set()
        for item in used.values():
            if item.get('license_file'):
                path=(studio.root/'assets/audio'/item['license_file']).resolve()
                if path.is_relative_to((studio.root/'assets/audio').resolve()) and path.is_file():
                    licenses.add(path)
        licenses.update((studio.root/'static/fonts').glob('*/OFL.txt'))
        for number,path in enumerate(sorted(licenses)):
            archive.write(path,f'licenses/{number:02}-{path.parent.name}-{path.name}')
    temporary.replace(folder/"clips.zip")
    studio.update(job,archive=f"/files/{job['id']}/clips.zip",report=f"/files/{job['id']}/analysis.json")


def evaluate(studio,job,source,plan,aligned,index,metadata,folder,revision,candidate,original_segments,final=False,story_reuse=None):
    record=render_v2.render(studio,job,source,plan,aligned,index,metadata,folder,revision,final)
    preview={'video':f"/files/{job['id']}/{record['path'].name}",'title':plan.get('title','Current edit'),
             'duration':plan['duration'],'revision':revision,'candidate_id':plan.get('id'),'final':final,'reviewing':True}
    if studio is not None:
        studio.update(job,latest_draft=preview,stage='Reviewing export' if final else 'Reviewing draft')
        studio.event(job, 'Video rendered. Checking audio, framing and story: ' + plan.get('title', 'Current edit'))
    width=job["config"]["resolution"] if final else 720
    technical=render_v2.technical_qc(studio,job,record["path"],plan["duration"],width)
    cache=folder/(record["path"].stem+".review.json")
    if cache.exists():
        review=json.loads(cache.read_text())
        review['technical']=technical
        review['reject']=bool(review['reject'] or not technical['passed'])
    else:
        spoken=analysis.compact_speech(record['mapped'],0,plan['duration'])
        context=review_context(candidate,index,original_segments)
        visual_path=folder/(record['path'].stem+'.visual-review.json')
        story_path=folder/(record['path'].stem+'.story-review.json')
        if visual_path.exists():
            visual=json.loads(visual_path.read_text())
        else:
            images=render_v2.review_images(studio,job,record["path"],folder,record["path"].stem,plan["duration"],plan=plan)
            visual=retry_review(studio,job,lambda:director.critique(studio,job,plan,images,spoken,technical,context))
            runtime.atomic_json(visual_path,visual)
        reusable=bool(story_reuse and story_reuse['mapped']==record['mapped'] and story_reuse.get('plan')==plan)
        if reusable:
            story=deepcopy(story_reuse['story'])
        elif story_path.exists():
            story=json.loads(story_path.read_text())
        else:
            story=retry_review(studio,job,lambda:director.story_review(studio,job,plan,spoken,context))
        runtime.atomic_json(story_path,story)
        review=combined_review(visual,story,technical)
        review['story_review_reused']=reusable
        runtime.atomic_json(cache,review)
    if studio is not None:studio.update(job,latest_draft={**preview,'reviewing':False,'score':review['score'],'rejected':review['reject'],'needs_revision':not qualified(review,job['config'])})
    return record,review


def retry_review(studio,job,operation):
    for attempt in range(2):
        try:
            return operation()
        except runtime.vllm_backend.IncompleteResponse:
            if attempt:
                raise
            if studio is not None:
                studio.event(job,'The AI review was interrupted. Retrying only this review; the rendered video is saved.')


def same_render(first,second):
    fields=('spans','layout','focus','facecam','music_mood','music_gain','caption_style',
            'caption_position','overlays','zooms','sfx','screen_hook')
    return {k:first.get(k) for k in fields} == {k:second.get(k) for k in fields}


def qualified(review,config):
    return not review["reject"] and review["score"]>=max(70,config["min_score"]) and review["technical"]["passed"]


def checkpoint_candidate(folder,ident,state):
    path=folder/"candidate-progress.json"
    states=json.loads(path.read_text()) if path.exists() else {}
    states[ident]=state
    runtime.atomic_json(path,states)


def recover_invalid_plans(states):
    """Retry technical planning failures once after a planner fix, not critic rejects."""
    recovered = 0
    for state in states.values():
        if (state.get('status') == 'rejected' and not state.get('revisions')
                and str(state.get('error', '')).startswith('Director could not produce')
                and state.get('plan_recovery_version', 0) < director.PLAN_RECOVERY_VERSION):
            state.setdefault('planning_failures', []).append(state.pop('error'))
            state.update(status='pending', plan_recovery_version=director.PLAN_RECOVERY_VERSION)
            recovered += 1
    return recovered


def failure_summary(states):
    unfinished = sum(s.get('status') in {'review_error','task_error'} for s in states.values())
    if unfinished:
        return {'stage':'review','unfinished_reviews':unfinished,
                'message':f'{unfinished} clip tasks did not finish. Their completed checkpoints and any rendered drafts are saved. '
                          'Resume run retries the unfinished tasks. Other rejected edits remain in the editing report.'}
    planned = sum(bool(s.get('revisions')) for s in states.values())
    invalid = [s for s in states.values() if s.get('error') and not s.get('revisions')]
    if not planned and invalid:
        reasons = list(dict.fromkeys(s['error'].removeprefix('Director could not produce a safe, valid timeline: ') for s in invalid))
        return {'stage': 'planning', 'invalid_plans': len(invalid), 'reviewed_candidates': 0,
                'message': f"The editor could not create valid edit plans for {len(invalid)} candidates. "
                           "No videos reached rendering or quality review. " + ' '.join(reasons[:2]) +
                           ". The source and analysis are saved; this is an editing-plan failure, not a quality-score rejection."}
    return {'stage': 'review', 'invalid_plans': len(invalid), 'reviewed_candidates': planned,
            'message': f"No candidates passed the quality cutoff after reviewing {planned} rendered candidates. "
                       "The editing report and saved drafts contain the specific reasons."}


def prepare_initial_pool(studio,job,source,candidates,index,segments,metadata,folder,states):
    """Keep the vision model resident, then the director, for the initial pool.

    Per-clip review/refinement still uses its normal checkpoints. Backfill can
    prepare additional candidates on demand rather than editing all forty.
    """
    needed=max(0,job['config']['count']-len(job['clips']))
    # Get a playable first draft before planning a larger batch.
    needed=min(3 if job.get('latest_draft') else 1,needed)
    chosen=[]
    for candidate in candidates:
        state=states.setdefault(candidate['id'],{'candidate':candidate,'status':'pending','revisions':[]})
        if state['status'] in {'qualified','rejected','duplicate'}:continue
        chosen.append((candidate,state))
        if len(chosen)>=needed:break
    if not chosen or not needed:return
    studio.update(job,stage='Inspecting selected moments')
    for candidate,state in chosen:
        studio.check_cancel(job['id'])
        if job.get('processing_strategy',{}).get('mode')=='long_stream' and not candidate.get('speech_verified'):
            from .longform import verified_speech
            verified_speech(studio,job,source,folder,segments,candidate,metadata,index['language'])
        analysis.densify_regions(studio,job,folder,candidate,index)
        candidate['fine_evidence']=state.get('candidate',{}).get('fine_evidence') or candidate.get('fine_evidence')
        if not candidate['fine_evidence']:
            studio.event(job,'Inspecting the event before editing: '+candidate['title'])
            candidate['fine_evidence']=analysis.inspect_candidate(studio,job,source,candidate,index,folder)
        state['candidate']=candidate
        runtime.atomic_json(folder/'candidate-progress.json',states)
    runtime.unload()
    studio.update(job,stage='Directing selected edits')
    for candidate,state in chosen:
        studio.check_cancel(job['id'])
        path=folder/f"plan-{candidate['id']}-r0.json"
        if path.exists():continue
        audio_source=source if job.get('processing_strategy',{}).get('mode')=='long_stream' else folder/'speech.wav'
        aligned=analysis.align_candidate(studio,job,folder,audio_source,segments,candidate,index['language'])
        try:
            plan=director.make_plan(studio,job,candidate,index,aligned,previous=state.get('latest_plan'))
            runtime.atomic_json(path,plan)
            state['latest_plan']=plan
        except RuntimeError as exc:
            if not str(exc).startswith('Director could not produce'):raise
            state.update(status='rejected',error=str(exc))
            studio.event(job,str(exc))
        runtime.atomic_json(folder/'candidate-progress.json',states)
    runtime.unload()


def work_candidate(studio,job,source,candidate,index,segments,metadata,folder,state,user_notes=None,starting_revision=0):
    ident=candidate["id"]
    analysis.densify_regions(studio,job,folder,candidate,index)
    if not candidate.get("fine_evidence"):
        studio.event(job,"Inspecting the reveal and reaction more closely: "+candidate["title"])
        candidate["fine_evidence"]=analysis.inspect_candidate(studio,job,source,candidate,index,folder)
    state["candidate"]=candidate
    plan_path=folder/f"plan-{ident}-r{starting_revision}.json"
    if plan_path.exists():
        plan=json.loads(plan_path.read_text())
    else:
        studio.event(job,"Directing the edit: "+candidate["title"])
        prior=state.get("latest_plan")
        plan=director.make_plan(studio,job,candidate,index,segments,previous=prior,feedback=user_notes)
        runtime.atomic_json(plan_path,plan)
    runtime.unload()
    studio.event(job,"Aligning speech precisely for "+candidate["title"])
    audio_source=source if job.get('processing_strategy',{}).get('mode')=='long_stream' else folder/'speech.wav'
    aligned=analysis.align_candidate(studio,job,folder,audio_source,segments,candidate,index["language"])
    history=state.setdefault("revisions",[])
    for offset in range(3):
        revision=starting_revision+offset
        studio.check_cancel(job["id"])
        studio.update(job,stage="Editing & reviewing",active_candidate=candidate["title"],active_revision=offset)
        path=folder/f"plan-{ident}-r{revision}.json"
        if path.exists():
            plan=json.loads(path.read_text())
        else:
            runtime.atomic_json(path,plan)
        state["latest_plan"]=plan
        checkpoint_candidate(folder,ident,state)
        studio.event(job,f"Rendering and reviewing draft {offset+1}/3: {candidate['title']}")
        runtime.unload()
        draft,review=evaluate(studio,job,source,plan,aligned,index,metadata,folder,revision,candidate,segments)
        if not any(h["revision"]==revision for h in history):
            history.append({"revision":revision,"plan":plan,"review":review,"draft":f"/files/{job['id']}/{draft['path'].name}"})
        checkpoint_candidate(folder,ident,state)
        if qualified(review,job["config"]):
            studio.event(job,"Draft passed. Rendering the full-resolution export: "+plan["title"])
            runtime.unload()
            final,final_review=evaluate(studio,job,source,plan,aligned,index,metadata,folder,revision,candidate,segments,final=True,
                story_reuse={'mapped':draft['mapped'],'story':review['story_critic'],'plan':deepcopy(plan)})
            if qualified(final_review,job["config"]):
                cover=folder/(final["path"].stem+".jpg")
                if not cover.exists():
                    render_v2.create_cover(studio,job,final["path"],plan["title"],cover)
                clip={"id":ident,"rank":len(job["clips"])+1,"title":plan["title"],"start":plan["start"],"end":plan["end"],"duration":plan["duration"],
                      "score":final_review["score"],"metrics":final_review["metrics"],"judge_reason":final_review["reason"],"weakness":final_review["weakness"],
                      "post_caption":plan["post_caption"],"edit_plan":plan,"review":final_review,"versions":history,"revision":revision,
                      "transcript":" ".join(s["text"] for s in final["mapped"]),
                      "video":f"/files/{job['id']}/{final['path'].name}","thumbnail":f"/files/{job['id']}/{cover.name}",
                      "subtitles":f"/files/{job['id']}/{final['srt'].name}","editable_captions":f"/files/{job['id']}/{final['ass'].name}"}
                state.update(status="qualified",review=final_review,latest_plan=plan)
                checkpoint_candidate(folder,ident,state)
                return clip
            review=final_review
        state["review"]=review
        if offset==2:
            break
        studio.event(job,f"Critic scored {review['score']}/100. Revising specific weaknesses before the next draft.")
        actions={p["action"] for p in review["problems"]}-{"none"}
        if (folder/f"plan-{ident}-r{revision+1}.json").exists():
            # Resume the saved next edit instead of paying for a discarded new
            # plan which the next iteration would immediately overwrite.
            continue
        previous_plan=deepcopy(plan)
        if actions & {"tighten","more_context"} or review["reject"] or review["metrics"]["hook"]<3 or review["metrics"]["clarity"]<3 or review["metrics"]["payoff"]<3 or not actions:
            plan=director.make_plan(studio,job,candidate,index,segments,previous=plan,
                                    feedback={"review":review,"user_notes":user_notes})
        plan=director.apply_revision_actions(plan,review)
        if same_render(previous_plan,plan):
            state.update(status='rejected',latest_plan=plan,rejection_reason='The proposed revision did not change the rendered edit.')
            studio.event(job,'The editor returned an unchanged edit. Moving to a different moment instead of repeating the same video.')
            return None
    state.update(status="rejected",latest_plan=plan)
    return None


def process_candidate(studio,job,source,candidate,index,segments,metadata,folder,states):
    """One child's entire lifecycle; callers isolate and retry this unit."""
    state=states[candidate['id']]
    if not (folder/f"plan-{candidate['id']}-r0.json").exists():
        prepare_initial_pool(studio,job,source,[candidate],index,segments,metadata,folder,states)
        if state['status']=='rejected':return None
    planned=json.loads((folder/f"plan-{candidate['id']}-r0.json").read_text())
    if any(core.overlap_fraction(planned,clip)>.20 for clip in job['clips']):
        state['status']='duplicate'
        checkpoint_candidate(folder,candidate['id'],state)
        return None
    return work_candidate(studio,job,source,candidate,index,segments,metadata,folder,state)


def pipeline(studio,job):
    folder=studio.jobs_dir/job["id"]
    studio.update(job,stage="Importing",progress=2)
    source=source_media.import_source(studio,job)
    job['imported_file']=str(source)
    source=analysis.normalize_source(studio,job,source,folder)
    job["source_file"]=str(source)
    metadata=analysis.inspect_source(source,lambda args:studio.run(job,args))
    processing=strategy(metadata['duration'])
    previous=job.get('processing_strategy')
    studio.update(job,processing_strategy=processing)
    long=processing['mode']=='long_stream'
    if long:
        from . import longform
        identity=source_cache.fingerprint(source)
        if job.get('analysis_source_fingerprint') not in (None,identity):
            raise ValueError('The source file changed since analysis. Start a new project; the previous exports remain available.')
        studio.update(job,analysis_source_fingerprint=identity)
        longform_store = longform.store(job,source,folder)
        longform_store.recover_running()
        from .resources import Governor
        if job['id'] not in studio.governors:
            studio.governors[job['id']]=Governor(studio,job)
        if previous!=processing:
            studio.event(job,f"Long-stream mode enabled automatically: {processing['scout_count']} half-hour scouts. Heavy work runs one task at a time.")
    if metadata['duration']<job['config']['min_duration']:
        raise ValueError('The source is shorter than the chosen minimum clip length. Choose a shorter duration or a longer source; short events are not padded.')
    studio.update(job,metadata=metadata,progress=7,stage="Transcribing")
    if not long:source_cache.restore(studio,job,source,metadata,folder)
    runtime.unload()
    if long:
        from . import longform
        segments,language=longform.prepare_speech(studio,job,source,folder,metadata)
    else:
        segments,language=analysis.transcribe(studio,job,source,folder,metadata)
    studio.update(job,language=language,progress=14)
    chosen=runtime.profile(studio.data)
    if not chosen.get("verified"):
        studio.update(job,stage="Calibrating larger models")
        studio.event(job,"First-run calibration measures sustained GPU and memory behavior before choosing the director. This can take ten minutes per profile.")
        visual=None
        if not segments:
            visual=analysis.calibration_visual(studio,job,source,folder,metadata)
            runtime.unload()
        chosen=runtime.calibrate(studio.data,calibration_text(metadata["duration"],segments,job["source"].get("attention_hint",0),visual),
                                 lambda message:studio.event(job,message),
                                 cancelled=lambda:studio.cancel_flags[job["id"]].is_set(),key=job["id"])
    job["config"].update(model=chosen["director"],judge_model=runtime.VISION_MODEL)
    job['config'].setdefault('video_encoder','auto')
    studio.update(job,stage="Analyzing full video",progress=18)
    index=(longform.build_index if long else analysis.build_index)(studio,job,source,folder,metadata,segments,language)
    if job["config"].get("content_mode")!="auto":
        index["mode"]=job["config"]["content_mode"]
    studio.update(job,stage="Finding complete moments",progress=40)
    candidates=director.propose(studio,job,index,segments,folder)
    states_path=folder/"candidate-progress.json"
    states=json.loads(states_path.read_text()) if states_path.exists() else {}
    if recover_invalid_plans(states):
        runtime.atomic_json(states_path, states)
        studio.event(job, 'Retrying invalid edit plans with the corrected planner. Saved import, transcript and scene analysis are reused.')
    tasks=longform.store(job,source,folder) if long else None
    if tasks:
        for candidate in candidates:
            ident='clip-'+candidate['id'];tasks.ensure(ident,'clip')
            recovered=tasks.get(ident)
            if recovered['status']=='complete' and recovered['result'] and not any(c['id']==candidate['id'] for c in job['clips']):
                job['clips'].append(recovered['result'])
                studio.event(job,'Recovered a completed clip export from its durable task checkpoint.')
    studio.update(job,candidate_count=len(candidates),stage="Editing & reviewing",progress=50)
    for position,candidate in enumerate(candidates):
        studio.check_cancel(job["id"])
        studio.update(job, progress=min(95, 50+round(45*position/len(candidates))), reviewed_candidates=position)
        if len(job["clips"])>=job["config"]["count"]:
            break
        state=states.setdefault(candidate["id"],{"candidate":candidate,"status":"pending","revisions":[]})
        if state["status"] in {"qualified","rejected","duplicate"}:
            continue
        try:
            # Planning, ASR, rendering and review all belong to this child.
            # A child failure must not prevent another candidate from running.
            operation=lambda:process_candidate(studio,job,source,candidate,index,segments,metadata,folder,states)
            clip=tasks.run(studio,job,'clip-'+candidate['id'],'clip',operation) if tasks else operation()
            if clip:
                job["clips"].append(clip)
                studio.event(job,f"Qualified clip {len(job['clips'])}/{job['config']['count']}: {clip['title']} ({clip['score']}/100).")
            else:
                studio.event(job,"This candidate did not pass after two revisions. Trying the next complete event.")
        except (ValueError,KeyError) as exc:
            state.update(status="rejected",error=str(exc))
            studio.event(job,"Rejected an invalid edit plan: "+str(exc)[:500])
        except Exception as exc:
            studio.check_cancel(job['id'])
            from .resources import ResourcePause
            if isinstance(exc,ResourcePause):raise
            if isinstance(exc,runtime.vllm_backend.IncompleteResponse):
                state.update(status='review_error',error='The AI review did not finish after its automatic retry. The rendered draft is saved.')
                studio.event(job,'A draft is saved for review recovery. Continuing with the next candidate.')
            elif str(exc).startswith("Director could not produce"):
                state.update(status="rejected",error=str(exc))
                studio.event(job,str(exc))
            else:
                state.update(status='task_error',error=str(exc)[-1200:])
                studio.event(job,'This clip task failed; its saved drafts are preserved. Continuing with the next independent candidate. '+str(exc)[-250:])
                runtime.unload()
        runtime.atomic_json(states_path,states)
        studio.update(job,progress=min(97,50+round(45*(position+1)/len(candidates))),reviewed_candidates=position+1)
    if not job["clips"]:
        summary = failure_summary(states)
        studio.update(job, failure_summary=summary)
        package(studio,job,folder,states,index)
        raise RuntimeError(summary['message'])
    studio.update(job,stage="Packaging",progress=98)
    retryable=any(s.get('status') in {'task_error','review_error'} for s in states.values()) or bool(index.get('failed_scouts') or index.get('failed_speech_chunks'))
    studio.update(job,has_retryable_tasks=retryable and len(job['clips'])<job['config']['count'])
    package(studio,job,folder,states,index)
    if len(job["clips"])<job["config"]["count"]:
        note=' Some tasks need attention; Resume unfinished tasks retries them.' if job.get('has_retryable_tasks') else ' No weaker repeats were added.'
        studio.event(job,f"{len(job['clips'])} distinct clips passed out of {job['config']['count']} requested."+note)
    runtime.unload()
    studio.event(job,"Finished: reviewed MP4s, covers, captions, post text and the complete editing report are ready.")


def refine(studio,job):
    request=job["pending_refine"]
    folder=studio.jobs_dir/job["id"]
    old=next(c for c in job["clips"] if c["id"]==request["clip_id"])
    states=json.loads((folder/"candidate-progress.json").read_text())
    state=states[old["id"]]
    source=Path(job["source_file"])
    index=json.loads((folder/"scene-index.json").read_text())
    segments=json.loads((folder/"segments.json").read_text())
    previous=deepcopy(old)
    state["latest_plan"]=old["edit_plan"]
    saved_revisions=[h["revision"] for h in state.get("revisions",[])]
    saved_revisions += [int(p.stem.rsplit("-r",1)[1]) for p in folder.glob(f"plan-{old['id']}-r*.json")]
    revision=max(saved_revisions+[old.get("revision",0)])+1
    studio.event(job,"Refining the clip with your notes. The previous export remains available.")
    new=work_candidate(studio,job,source,state["candidate"],index,segments,job["metadata"],folder,state,
                       user_notes=request["notes"],starting_revision=revision)
    if new:
        new["rank"]=old["rank"]
        new.setdefault("prior_exports",[]).extend(old.get("prior_exports",[])+[{k:previous.get(k) for k in ("video","thumbnail","score","revision","edit_plan")}])
        job["clips"][job["clips"].index(old)]=new
        studio.event(job,"Refinement passed review. The previous export is preserved in version history.")
    else:
        state["status"]="qualified"
        studio.event(job,"The refinement did not meet the cutoff. Your previous qualified export was retained.")
    runtime.atomic_json(folder/"candidate-progress.json",states)
    job.pop("pending_refine",None)
    package(studio,job,folder,states,index)
    runtime.unload()
