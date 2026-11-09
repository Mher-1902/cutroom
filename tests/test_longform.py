import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from cutroom import analysis, director, longform, pipeline_v2, resources, source_policy
from cutroom.contracts import ClipEditPlan, REVIEW_WEIGHTS
from cutroom.engine import Cancelled
from cutroom.post_copy import caption
from cutroom.story_structure import STAGES
from cutroom.task_store import TaskStore
from cutroom.uploads import UploadStore


class Studio:
    def __init__(self,folder):
        self.root=folder;self.data=folder/'data';self.jobs_dir=folder
        self.cancel_flags={'test':threading.Event()};self.governors={};self.events=[]
    def update(self,job,**values):job.update(values)
    def event(self,job,message):self.events.append(message)
    def check_cancel(self,ident,resources=True):
        if self.cancel_flags[ident].is_set():raise Cancelled()
    def model_cancelled(self,ident):self.check_cancel(ident);return False
    def run(self,job,args,**options):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE)


def brief():
    return dict(zip(STAGES,['How does he escape?','The door has locked.','He tries the handle.',
        'Will the window open?','The window finally opens.','Can he reach the ladder?',
        'He reaches the ladder safely.','Would you try that escape?']))


class RoutingTests(unittest.TestCase):
    def test_exact_three_hour_boundary_and_scaled_scout_count(self):
        self.assertEqual(source_policy.strategy(10800)['mode'],'standard')
        for duration,count in [(10800.01,7),(14400,8),(36000,20),(43200,24)]:
            result=source_policy.strategy(duration)
            self.assertEqual(result['mode'],'long_stream');self.assertEqual(result['scout_count'],count)
            self.assertEqual(result['concurrent_heavy_tasks'],1)
        for duration in (float('nan'),float('inf'),-1,5,43200.01):
            with self.assertRaises(ValueError):source_policy.strategy(duration)

    def test_chunks_cover_whole_source_and_preserve_boundary_context(self):
        chunks=source_policy.scout_chunks(36000)
        self.assertEqual(len(chunks),20)
        self.assertEqual(chunks[0]['start'],0);self.assertEqual(chunks[-1]['end'],36000)
        for left,right in zip(chunks,chunks[1:]):
            self.assertEqual(left['end'],right['start'])
            self.assertEqual(left['context_end']-right['context_start'],60)
        final=source_policy.scout_chunks(10801)[-1]
        windows=longform.packet_windows(final,[],60,90)
        self.assertTrue(windows)
        self.assertTrue(all(0<=a<b<=10801 and b-a>=60 for a,b in windows.values()))

    def test_real_pipeline_dispatches_before_full_transcription_or_frame_indexing(self):
        class Selected(Exception):pass
        for duration,long in [(10800,False),(10801,True),(36000,True)]:
            with self.subTest(duration=duration),tempfile.TemporaryDirectory() as name:
                root=Path(name);folder=root/'test';folder.mkdir();source=root/'source.mp4';source.write_bytes(b'source')
                studio=Studio(root)
                job={'id':'test','source':{},'config':{'min_duration':60,'max_duration':90,'content_mode':'auto'},'clips':[]}
                metadata={'duration':duration,'has_audio':True}
                with patch.object(pipeline_v2.source_media,'import_source',return_value=source), \
                     patch.object(analysis,'normalize_source',return_value=source), \
                     patch.object(analysis,'inspect_source',return_value=metadata), \
                     patch.object(pipeline_v2.source_cache,'restore'), \
                     patch.object(resources,'Governor'),patch.object(pipeline_v2.runtime,'unload'), \
                     patch.object(pipeline_v2.runtime,'profile',return_value={'verified':True,'director':'test'}), \
                     patch.object(analysis,'transcribe',return_value=([],'en')) as normal_speech, \
                     patch.object(longform,'prepare_speech',return_value=([],'en')) as long_speech, \
                     patch.object(analysis,'build_index',return_value={}) as normal_index, \
                     patch.object(longform,'build_index',return_value={}) as long_index, \
                     patch.object(director,'propose',side_effect=Selected):
                    with self.assertRaises(Selected):pipeline_v2.pipeline(studio,job)
                self.assertEqual(long_speech.call_count,int(long));self.assertEqual(long_index.call_count,int(long))
                self.assertEqual(normal_speech.call_count,int(not long));self.assertEqual(normal_index.call_count,int(not long))

    def test_tournament_judge_bounds_context_and_keeps_all_distinct_backups(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);studio=Studio(folder);job={'id':'test','config':{'count':5}}
            candidates=[{'id':f'{i:032x}','start':i*400,'end':i*400+180,'title':'文'*120,
                         'setup':'文'*120,'payoff':'文'*120,'event_key':str(i),'tone':'funny','score':4} for i in range(72)]
            def rank(studio,job,system,prompt,schema,**kwargs):
                ids=schema['properties']['ordered_ids']['items']['enum']
                self.assertLessEqual(len(ids),16)
                self.assertLess(len(prompt),7500)
                return {'ordered_ids':ids,'duplicate_ids':[],'reason':'Distinct source outcomes.'}
            with patch.object(director,'call',side_effect=rank) as judge:
                result=longform.propose(studio,job,{'scout_candidates':candidates},folder)
            self.assertEqual(judge.call_count,9)
            self.assertEqual(len(result),72);self.assertEqual(len({c['id'] for c in result}),72)
            with patch.object(director,'call',side_effect=AssertionError):
                self.assertEqual(longform.propose(studio,job,{'scout_candidates':candidates},folder),result)


class TaskTests(unittest.TestCase):
    def test_ten_hour_speech_is_bounded_and_one_failed_section_does_not_stop_others(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'source.mp4';source.write_bytes(b'source')
            studio=Studio(folder);job={'id':'test','config':{'language':'en'},'source':{}}
            def speech(studio,job,source,folder,a,b,language):
                self.assertLessEqual(b-a,300)
                if a==5100:raise RuntimeError('one damaged section')
                return {'segments':[{'start':a,'end':a+1,'text':'actual speech','words':[]}],'language':'en'}
            with patch('cutroom.source_captions.discovery',return_value=None),patch.object(longform.runtime,'unload'), \
                 patch.object(longform,'transcribe_excerpt',side_effect=speech) as transcribe:
                segments,_=longform.prepare_speech(studio,job,source,folder,{'duration':36000,'has_audio':True})
            self.assertEqual(transcribe.call_count,121);self.assertEqual(len(segments),119)
            self.assertEqual(job['failed_speech_chunks'],['speech-0017'])
            repaired={'segments':[{'start':5100,'end':5101,'text':'recovered speech','words':[]}],'language':'en'}
            with patch('cutroom.source_captions.discovery',return_value=None),patch.object(longform.runtime,'unload'), \
                 patch.object(longform,'transcribe_excerpt',return_value=repaired) as transcribe:
                segments,_=longform.prepare_speech(studio,job,source,folder,{'duration':36000,'has_audio':True})
            self.assertEqual(transcribe.call_count,1);self.assertEqual(len(segments),120)
            self.assertEqual(job['failed_speech_chunks'],[])

    def test_task_retry_recovery_and_source_isolation(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);studio=Studio(folder);job={'id':'test'};store=TaskStore(folder,{'source':'one'})
            operation=Mock(side_effect=[RuntimeError('temporary'),{'result':'saved'}])
            self.assertEqual(store.run(studio,job,'scout-1','scout',operation),{'result':'saved'})
            self.assertEqual(operation.call_count,2)
            recovered=TaskStore(folder,{'source':'one'})
            self.assertEqual(recovered.run(studio,job,'scout-1','scout',Mock(side_effect=AssertionError)),{'result':'saved'})
            failed=Mock(side_effect=RuntimeError('broken'))
            with self.assertRaisesRegex(RuntimeError,'broken'):store.run(studio,job,'scout-2','scout',failed)
            self.assertEqual(failed.call_count,2)
            self.assertEqual(store.run(studio,job,'scout-3','scout',lambda:'independent'),'independent')
            self.assertEqual(store.get('scout-1')['status'],'complete')
            self.assertIsNone(TaskStore(folder,{'source':'different'}).get('scout-1'))
            store.ensure('interrupted','clip');store.set('interrupted','running');store.recover_running()
            self.assertEqual(store.get('interrupted')['status'],'pending')
            self.assertEqual(store.get('scout-1')['status'],'complete')

    def test_cooling_is_not_a_failed_scout_or_consumed_retry(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);studio=Studio(folder);store=TaskStore(folder,{})
            operation=Mock(side_effect=resources.ResourcePause('cool'))
            with self.assertRaises(resources.ResourcePause):store.run(studio,{'id':'test'},'one','scout',operation)
            self.assertEqual(operation.call_count,1);self.assertEqual(store.get('one')['status'],'pending')
            studio.cancel_flags['test'].set()
            with self.assertRaises(Cancelled):store.run(studio,{'id':'test'},'two','scout',lambda:None)

    def test_one_failed_scout_does_not_discard_nineteen_successes_and_resume_retries_only_failure(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'source.mp4';source.write_bytes(b'same source')
            studio=Studio(folder);job={'id':'test','config':{},'source':{}}
            metadata={'duration':36000}
            def scout(*args):
                chunk=args[-2]
                if chunk['id']=='scout-005':raise RuntimeError('worker stopped')
                return {'block':{**{k:chunk[k] for k in ('start','end')},'mode':'reaction','events':[],
                         'summary':'observed','analysis_failed':False,'frame_count':2},'candidates':[]}
            with patch.object(longform,'semantic_retrieval',return_value=[]),patch.object(longform,'scout_one',side_effect=scout) as run:
                index=longform.build_index(studio,job,source,folder,metadata,[],'en')
            self.assertEqual(run.call_count,21);self.assertEqual(index['failed_scouts'],['scout-005'])
            self.assertEqual(job['scout_progress'],{'complete':19,'failed':1,'total':20})
            self.assertFalse(index['coverage_complete']);self.assertEqual(len(index['blocks']),20)
            def repaired(*args):
                chunk=args[-2]
                return {'block':{'start':chunk['start'],'end':chunk['end'],'mode':'reaction','events':[],
                         'summary':'recovered','analysis_failed':False,'frame_count':2},'candidates':[]}
            with patch.object(longform,'semantic_retrieval',return_value=[]),patch.object(longform,'scout_one',side_effect=repaired) as run:
                index=longform.build_index(studio,job,source,folder,metadata,[],'en')
            self.assertEqual(run.call_count,1);self.assertTrue(index['coverage_complete'])
            self.assertEqual(job['scout_progress']['complete'],20)

    def test_a_clip_render_failure_does_not_stop_the_next_clip(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);folder=root/'test';folder.mkdir();source=root/'source.mp4';source.touch()
            studio=Studio(root);job={'id':'test','config':{'min_duration':60,'max_duration':90,'content_mode':'auto','count':2},'source':{},'clips':[]}
            index={'duration':300};candidates=[{'id':'a'},{'id':'b'}]
            with patch.object(pipeline_v2.source_media,'import_source',return_value=source), \
                 patch.object(analysis,'normalize_source',return_value=source),patch.object(analysis,'inspect_source',return_value={'duration':300}), \
                 patch.object(pipeline_v2.source_cache,'restore'),patch.object(analysis,'transcribe',return_value=([],'en')), \
                 patch.object(pipeline_v2.runtime,'unload'),patch.object(pipeline_v2.runtime,'profile',return_value={'verified':True,'director':'test'}), \
                 patch.object(analysis,'build_index',return_value=index),patch.object(director,'propose',return_value=candidates), \
                 patch.object(pipeline_v2,'process_candidate',side_effect=[RuntimeError('encoder crashed'),{'id':'b','title':'Independent event','score':80}]) as run, \
                 patch.object(pipeline_v2,'package'):
                pipeline_v2.pipeline(studio,job)
            self.assertEqual(run.call_count,2);self.assertEqual([c['id'] for c in job['clips']],['b'])
            self.assertTrue(job['has_retryable_tasks'])
            states=json.loads((folder/'candidate-progress.json').read_text())
            self.assertEqual(states['a']['status'],'task_error')


class StoryTests(unittest.TestCase):
    def test_all_eight_beats_are_ordered_gapless_and_rendered_for_every_supported_length(self):
        for duration in (15,29,30,59,60,61,90,120,180):
            with self.subTest(duration=duration):
                raw={'spans':[{'start':100,'end':100+duration}],'story_brief':brief()}
                plan=ClipEditPlan.parse(raw,500,15,180).to_dict()
                self.assertEqual(tuple(b['key'] for b in plan['story_structure']),STAGES)
                self.assertEqual(plan['story_structure'][0]['start'],0)
                self.assertEqual(plan['story_structure'][-1]['end'],duration)
                for first,second in zip(plan['story_structure'],plan['story_structure'][1:]):self.assertEqual(first['end'],second['start'])
                self.assertTrue(all(b['source_sections'] for b in plan['story_structure']))
                self.assertEqual(len([o for o in plan['overlays'] if o.get('story_role')]),4)
                rebuilt=ClipEditPlan.parse(plan,500,15,180).to_dict()
                self.assertEqual(rebuilt['overlays'],plan['overlays'])
                self.assertEqual(rebuilt['story_structure'],plan['story_structure'])
                reduced=director.apply_revision_actions(plan,{'problems':[{'action':'less_overlays'}]})
                self.assertEqual(len(reduced['overlays']),4)
        invalid=brief();invalid.pop('body_2')
        with self.assertRaisesRegex(ValueError,'eight story beats'):ClipEditPlan.parse({'spans':[{'start':0,'end':70}],'story_brief':invalid},100)

    def test_story_rejection_cannot_be_overridden_by_a_high_score(self):
        visual={'metrics':{k:5 for k in REVIEW_WEIGHTS},'reason':'a','weakness':'b','reject':False,'problems':[],'structure_passed':False}
        story={k:5 for k in ('hook','clarity','payoff','pacing')};story.update(reason='a',weakness='b',reject=False,structure_passed=True)
        review=pipeline_v2.combined_review(visual,story,{'passed':True})
        self.assertEqual(review['score'],100);self.assertFalse(pipeline_v2.qualified(review,{'min_score':70}))

    def test_post_copy_strictly_below_160_characters_including_emoji(self):
        self.assertEqual(len(caption('😀'*159)),159)
        self.assertEqual(caption('  one\n two  '),'one two')
        self.assertEqual(caption('e\u0301'),'é')
        for value in ('a'*160,'😀'*160):
            with self.assertRaises(ValueError):caption(value)
        from cutroom.post_copy import title
        self.assertEqual(title(': LeBron challenge'),'LeBron challenge')

    def test_measured_editor_uses_only_real_window_and_beat_ids(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);studio=Studio(root);(root/'test').mkdir()
            candidate={'id':'a'*32,'start':0,'end':180,'title':'A real escape'}
            result={'title':'The escape nobody expected','hook':'How does he escape?','post_caption':'The door locks. His next move is wild. Would you try it?',
                    'reason':'He reaches the ladder.','window_id':'W001','complete':True,'cold_open':False,'framing':'fit',
                    'screen_hook':{'enabled':True,'text':'How does he escape?','style':'hype'},'audience_angle':'surprise',
                    'caption_style':'kinetic','music_mood':'tension','editing_strategy':{'content_type':'reaction','tone':'suspenseful','pacing':'varied','reason':'Preserve tension.'},
                    'callouts':[],'punch_ins':['B01'],'sound_cues':[],'story_brief':brief(),
                    'start':999999,'end':999999}
            job={'id':'test','config':{'min_duration':60,'max_duration':90},'processing_strategy':{'mode':'long_stream'}}
            with patch.object(director,'call',return_value=result):
                plan=director.make_plan(studio,job,candidate,{'duration':36000,'mode':'reaction','blocks':[],'audio_events':[]},[])
            self.assertTrue(60<=plan['duration']<=90)
            self.assertLess(plan['end'],200);self.assertEqual(len(plan['story_structure']),8)
            self.assertEqual(plan['planning_method'],'measured-window-and-cue-ids')
            self.assertEqual(plan['editing_strategy']['tone'],'suspenseful')

    def test_creative_pass_cannot_borrow_speech_from_neighboring_event(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);studio=Studio(root);(root/'test').mkdir()
            candidate={'id':'a'*32,'start':0,'end':180,'title':'unverified suggestion'}
            segments=[{'start':0,'end':5,'text':'EARLY_EVENT_CLAIM','words':[]},
                      {'start':110,'end':115,'text':'LATER_EVENT_SETUP','words':[]},
                      {'start':170,'end':175,'text':'LATER_EVENT_PAYOFF','words':[]}]
            payload={'title':'A complete later event','hook':'What happens next?','post_caption':'A source-grounded teaser about the later event.',
                'reason':'The later event resolves.','complete':True,'cold_open':False,'framing':'fit',
                'screen_hook':{'enabled':True,'text':'What happens next?','style':'clean'},'audience_angle':'story',
                'caption_style':'clean','music_mood':'none','editing_strategy':{'content_type':'story','tone':'dramatic','pacing':'balanced','reason':'Preserve payoff.'},
                'callouts':[],'punch_ins':[],'sound_cues':[],'story_brief':brief()}
            selected=[]
            def model(studio,job,system,prompt,schema,**options):
                if 'start_id' in schema['properties']:
                    ids=schema['properties']['start_id']['enum'];selected.append('EVENT')
                    return {'start_id':ids[1],'end_id':ids[-1],'complete':True,'reason':'A complete later event.'}
                ids=schema['properties'].get('window_id',{}).get('enum')
                if ids and len(ids)>1:
                    selected.append(ids[-1]);return {'window_id':ids[-1],'complete':True,'reason':'A complete later event.'}
                if ids:self.assertEqual(ids,selected)
                self.assertNotIn('EARLY_EVENT_CLAIM',prompt)
                self.assertIn('LATER_EVENT_PAYOFF',prompt)
                return {**payload,'window_id':selected[0]}
            job={'id':'test','config':{'min_duration':60,'max_duration':90},'processing_strategy':{'mode':'long_stream'}}
            with patch.object(director,'call',side_effect=model):
                result=director.make_plan(studio,job,candidate,{'duration':36000,'mode':'story','blocks':[],'audio_events':[]},segments)
            self.assertGreaterEqual(result['start'],90)

    def test_critic_context_excludes_a_neighboring_challenge(self):
        candidate={'start':0,'end':180,'fine_evidence':{'summary':'Wrong neighboring outcome',
                    'events':[{'at':10,'end':20,'description':'neighbor'},{'at':130,'end':140,'description':'retained'}]}}
        speech=[{'start':10,'end':20,'text':'OTHER CHALLENGE'}, {'start':130,'end':140,'text':'ACTUAL CHALLENGE'}]
        context=pipeline_v2.review_context(candidate,{'mode':'challenge'},speech,{'start':100,'end':180})
        self.assertEqual([s['text'] for s in context['neighboring_speech']],['ACTUAL CHALLENGE'])
        self.assertNotIn('summary',context['close_visual_observations'])
        self.assertEqual(len(context['close_visual_observations']['events']),1)


class UploadTests(unittest.TestCase):
    def test_interrupted_and_repeated_chunks_resume_without_duplicates(self):
        with tempfile.TemporaryDirectory() as name:
            store=UploadStore(name)
            with patch('cutroom.uploads.shutil.disk_usage',return_value=Mock(free=100*1024**3)):
                value=store.create('movie.mp4',12);ident=value['id']
                with self.assertRaisesRegex(ValueError,'interrupted'):store.append(ident,0,8,io.BytesIO(b'123'))
                self.assertEqual(store.status(ident)['offset'],3)
                value,consumed=store.append(ident,0,8,io.BytesIO(b'12345678'))
                self.assertFalse(consumed);self.assertEqual(value['offset'],3)
                value,consumed=store.append(ident,3,9,io.BytesIO(b'456789abc'))
                self.assertTrue(consumed);self.assertTrue(value['complete'])
                self.assertEqual((Path(name)/(ident+'.mp4')).read_bytes(),b'123456789abc')
                from cutroom.engine import Studio as EngineStudio
                holder=Mock(uploads=Path(name))
                self.assertEqual(EngineStudio.uploaded(holder,ident).suffix,'.mp4')
                with self.assertRaises(ValueError):store.create('file.exe',12)
            with patch('cutroom.uploads.shutil.disk_usage',return_value=Mock(free=100)):
                with self.assertRaisesRegex(ValueError,'disk space'):store.create('large.mp4',12)


class ResourceTests(unittest.TestCase):
    def test_serious_and_critical_thermal_states_pause_but_fair_does_not(self):
        self.assertIsNone(resources.Governor.reason({'thermal_state':1}))
        for state in (2,3):self.assertIn('cooling',resources.Governor.reason({'thermal_state':state}))
        self.assertIn('memory',resources.Governor.reason({'pressure':4}))
        self.assertIn('memory',resources.Governor.reason({'physical_footprint_bytes':20*1024**3}))

    def test_cooldown_releases_models_and_resumes_after_thirty_stable_seconds(self):
        guard=resources.Governor.__new__(resources.Governor)
        guard.job={'id':'test'};guard.last_reason='Cooling';guard.studio=Mock()
        guard.studio.cancel_flags={'test':Mock()}
        guard.sample=Mock(side_effect=[{'thermal_state':2},{'thermal_state':0},{'thermal_state':0}])
        with patch.object(resources.runtime,'unload') as unload,patch.object(resources.time,'monotonic',side_effect=[0,31,32]):
            guard.cool_down()
        unload.assert_called_once()
        self.assertEqual(guard.job['resource_metrics']['cooldowns'],1)
        self.assertEqual(guard.studio.update.call_args.kwargs,{'resource_pause':None})


@unittest.skipUnless(analysis.local_models.binary('ffmpeg'),'FFmpeg unavailable')
class LongMediaTests(unittest.TestCase):
    def test_actual_ten_hour_container_is_accepted_and_only_requested_late_frames_are_decoded(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'ten-hours.mp4';studio=Studio(folder)
            studio.run({},[analysis.local_models.binary('ffmpeg'),'-hide_banner','-loglevel','error','-y',
                '-f','lavfi','-i','color=c=navy:s=64x36:r=1:d=36000','-an','-c:v','libx264','-preset','ultrafast','-threads','1','-g','1',str(source)])
            metadata=analysis.inspect_source(source,lambda args:studio.run({},args))
            self.assertEqual(metadata['duration'],36000)
            job={'id':'test','processing_strategy':source_policy.strategy(metadata['duration'])}
            paths=analysis.source_frames(studio,job,source,folder,[0,18000,35999],metadata['duration'])
            self.assertTrue(all(p.stat().st_size>0 for p in paths))
            self.assertEqual(len(list((folder/'sparse-frames').glob('*.jpg'))),3)
            self.assertEqual(job['processing_strategy']['scout_count'],20)
            self.assertFalse((folder/'frames').exists())
