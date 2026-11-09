from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from cutroom import analysis, director, pipeline_v2
from cutroom.contracts import REVIEW_WEIGHTS


class EfficiencyTests(unittest.TestCase):
    def test_fractional_container_end_never_requests_a_nonexistent_vision_frame(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);frames=folder/'frames';frames.mkdir()
            for i in range(200):(frames/f'frame-{i+1:06}.jpg').touch()
            index={'duration':200.434,'blocks':[{'start':0,'end':200.434,'regions':[]}]}
            def regions(studio,job,paths,out):
                self.assertTrue(all(path.is_file() for path in paths))
                return [{'faces':[],'texts':[]} for _ in paths]
            with patch.object(analysis,'native_regions',side_effect=regions) as detect:
                analysis.densify_regions(None,{},folder,{'id':'last','start':180,'end':200.434},index)
            self.assertGreater(detect.call_count,0)
            self.assertEqual(max(r['at'] for r in index['blocks'][0]['regions']),199)
            self.assertFalse((frames/'frame-000201.jpg').exists())

    def test_missing_frame_is_reported_before_invoking_vision(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(RuntimeError,'source frame is missing'):
                analysis.source_frames(None,{},None,Path(name),[0],1.4)

    def test_visual_editor_receives_source_storyboard_motion_and_separate_style_reference(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);frames=folder/'frames';frames.mkdir()
            for number in range(130):(frames/f'frame-{number+1:06}.jpg').touch()
            (folder/'segments.json').write_text('[]')
            reference=folder/'style-references/hype-reference.jpg';reference.parent.mkdir();reference.touch()
            class Studio:
                data=folder;cancel_flags={'test':threading.Event()}
                def event(self,*args):pass
                def run(self,job,args):
                    for number in range(1,13):Path(args[-1].replace('%03d',f'{number:03}')).touch()
            def sheet(paths,times,out,**kwargs):out.touch();return out
            raw={'summary':'a visible reveal','mode':'reaction','events':[], 'focus':[60,70,80,90],
                 'facecam':[],'existing_captions':False,'visual_brief':{'opening_frame_id':'F01',
                 'opening_why':'a visible expression','audience_angle':'surprise','suggested_hook':'WAIT… WHAT?!',
                 'shot_suggestions':[{'frame_id':'F01','framing':'portrait_right','reason':'one visible face'}],
                 'keep_visible':['the actual reveal']}}
            with patch.object(analysis,'contact_sheet',side_effect=sheet),patch.object(analysis.runtime,'chat',return_value=raw) as vision:
                result=analysis.inspect_candidate(Studio(),{'id':'test'},Path('source.mp4'),
                    {'id':'event','start':60,'end':120},{'blocks':[{'events':[],
                    'regions':[{'at':60,'faces':[[.35,.25,.1,.2]],'texts':[]}]}]},folder)
            images=vision.call_args.args[4]
            self.assertEqual(len(images),4)
            self.assertEqual(images[0].name,'storyboard.jpg')
            self.assertEqual(images[-1],reference)
            self.assertIn('NOT source evidence',vision.call_args.args[2])
            self.assertEqual(result['visual_brief']['opening_source_time'],60.5)
            self.assertAlmostEqual(result['visual_brief']['shot_suggestions'][0]['focus'][0],.25)
            self.assertEqual(result['focus'],[0,0,1,1])

    def test_review_retries_once_without_accepting_a_truncated_answer(self):
        fail=pipeline_v2.runtime.vllm_backend.IncompleteResponse('output limit')
        with patch('builtins.print'):
            operation=unittest.mock.Mock(side_effect=[fail,{'score':80}])
            self.assertEqual(pipeline_v2.retry_review(None,{},operation),{'score':80})
            self.assertEqual(operation.call_count,2)
            operation=unittest.mock.Mock(side_effect=fail)
            with self.assertRaises(type(fail)):pipeline_v2.retry_review(None,{},operation)
            self.assertEqual(operation.call_count,2)

    def test_rewriting_only_the_reason_is_not_an_edit_revision(self):
        first={'spans':[{'start':10,'end':80}],'reason':'old reason','title':'Old title','overlays':[]}
        second={**first,'reason':'new explanation','title':'New title'}
        self.assertTrue(pipeline_v2.same_render(first,second))
        second['overlays']=[{'at':0,'duration':3,'kind':'hook','text':'Who takes the job?'}]
        self.assertFalse(pipeline_v2.same_render(first,second))
    def test_optional_framing_and_source_clock_cues_do_not_discard_valid_story(self):
        raw={'spans':[{'start':480,'end':550,'focus':[.5,.5,1,1]}],
             'layout':'fit','focus':[.5,.5,1,1],
             'overlays':[{'at':500,'duration':2,'text':'Source clock','kind':'callout'},
                         {'at':1,'duration':2,'text':'Valid output cue','kind':'hook'}],
             'zooms':[{'at':5,'duration':1,'scale':1.2}], 'sfx':[{'at':500,'kind':'impact'}]}
        fixed=director.validate_plan(raw,900,61,120,(472,558))
        self.assertEqual(fixed['duration'],70)
        self.assertEqual(fixed['focus'],[0,0,1,1])
        self.assertEqual(fixed['spans'][0]['start'],480)
        self.assertEqual(fixed['spans'][0]['end'],550)
        self.assertEqual([o['text'] for o in fixed['overlays']],['Source clock','Valid output cue'])
        self.assertEqual(fixed['overlays'][0]['at'],20)
        self.assertEqual(fixed['zooms'],[]);self.assertEqual(fixed['sfx'],[{'at':20,'kind':'impact'}])
        self.assertTrue(fixed['validation_adjustments'])
        self.assertEqual(raw['focus'],[.5,.5,1,1])

    def test_recovery_never_pads_short_edits_or_moves_source_bounds(self):
        for spans in ([{'start':480,'end':520}], [{'start':450,'end':550}],
                      [{'start':520,'end':550},{'start':480,'end':520}]):
            with self.subTest(spans=spans),self.assertRaises(ValueError):
                director.validate_plan({'spans':spans,'focus':[.5,.5,1,1]},900,61,120,(472,558))

    def test_source_clock_cues_map_only_when_the_retained_shot_is_unambiguous(self):
        raw={'spans':[{'start':480,'end':550}], 'focus':[0,0,1,1],
             'overlays':[{'at':500,'duration':2,'text':'A retained moment','kind':'callout'}],
             'sfx':[{'at':800,'kind':'impact'}]}
        edit=director.validate_plan(raw,900,61,120,(472,558))
        self.assertEqual(edit['overlays'][0]['at'],20)
        self.assertEqual(edit['sfx'],[])
        raw['spans'].append({'start':499,'end':501,'kind':'replay'})
        edit=director.validate_plan(raw,900,61,120,(472,558))
        self.assertEqual(edit['overlays'],[])

    def test_generation_schema_bounds_graphics_and_uses_valid_focus_rectangles(self):
        props=director.bounded_plan_schema(29)['properties']
        self.assertLess(props['sfx']['items']['properties']['at']['maximum'],29)
        self.assertEqual(props['zooms']['items']['properties']['scale']['maximum'],1.18)
        for x,y,w,h in props['focus']['enum']:
            self.assertLessEqual(x+w,1);self.assertLessEqual(y+h,1)

    def test_saved_valid_story_is_recovered_without_another_model_call(self):
        class Studio:
            def event(self,*args):pass
        with tempfile.TemporaryDirectory() as name:
            studio=Studio();studio.jobs_dir=Path(name)
            folder=studio.jobs_dir/'test';folder.mkdir()
            (folder/'director-raw-event-1.json').write_text(json.dumps({
                'spans':[{'start':480,'end':550}], 'focus':[.5,.5,1,1], 'layout':'fit'}))
            with patch.object(director,'call') as model:
                edit=director.make_plan(studio,{'id':'test','config':{'min_duration':61,'max_duration':120}},
                    {'id':'event','title':'Saved event','start':480,'end':550},{'duration':900},[])
            model.assert_not_called();self.assertEqual(edit['duration'],70)

    def test_resume_retries_technical_failures_once_and_preserves_critic_rejections(self):
        states={'bad':{'status':'rejected','error':'Director could not produce a safe, valid timeline: Region lies outside the frame','revisions':[]},
                'reviewed':{'status':'rejected','error':'critic rejected','revisions':[{'revision':0}]}}
        self.assertEqual(pipeline_v2.recover_invalid_plans(states),1)
        self.assertEqual(states['bad']['status'],'pending')
        self.assertEqual(states['reviewed']['status'],'rejected')
        states['bad'].update(status='rejected',error='Director could not produce a safe, valid timeline: too short')
        self.assertEqual(pipeline_v2.recover_invalid_plans(states),0)

    def test_planning_failure_is_not_misreported_as_a_critic_rejection(self):
        states={'bad':{'status':'rejected','error':'Director could not produce a safe, valid timeline: too short','revisions':[]}}
        summary=pipeline_v2.failure_summary(states)
        self.assertEqual(summary['stage'],'planning')
        self.assertEqual(summary['reviewed_candidates'],0)
        self.assertIn('No videos reached rendering',summary['message'])

    def test_duration_repair_uses_measured_bounds_and_keeps_critic_gate(self):
        class Studio:
            def event(self,*args):pass
        job={'id':'test','config':{'min_duration':61,'max_duration':120}}
        index={'duration':900,'blocks':[],'audio_events':[]}
        result={'window_id':'W001','complete':True,'title':'A real decision','hook':'Who accepts the offer?',
                'post_caption':'A real decision.','reason':'The retained ending answers who accepts.',
                'caption_style':'clean','music_mood':'none'}
        with patch.object(director,'call',return_value=result):
            edit=director.repair_duration(Studio(),job,{'id':'a','focus':[0,0,1,1]},
                {'title':'A real decision'},index,[],(480,720),None,'finished clip duration')
        self.assertTrue(61<=edit['duration']<=120)
        self.assertEqual(edit['spans'][0]['speed'],1)
        self.assertEqual(edit['spans'][0]['kind'],'normal')
        self.assertEqual(edit['duration'],edit['end']-edit['start'])
        self.assertEqual(edit['planning_method'],'measured-window-repair')
        review={'reject':False,'score':69,'technical':{'passed':True}}
        self.assertFalse(pipeline_v2.qualified(review,{'min_score':70}))
        for patch_result in ({**result,'complete':False},{**result,'window_id':'invented'}):
            with patch.object(director,'call',return_value=patch_result),self.assertRaisesRegex(RuntimeError,'no complete event'):
                director.repair_duration(Studio(),job,{}, {'title':'A real decision'},index,[],(480,720),None,'finished clip duration')

    def test_selector_uses_real_window_bounds_instead_of_generated_timecodes(self):
        class Studio:
            def check_cancel(self,*args):pass
            def event(self,*args):pass
            def update(self,job,**values):job.update(values)
        selection={'clips':[{'window_id':'W001','complete':True,'start':1,'end':2,
            'title':'A complete event','setup':'a real goal','payoff':'a real outcome','reason':'clear story','event_key':'event','score':4},
            {'window_id':'invented','complete':True}]}
        job={'id':'test','config':{'min_duration':61,'max_duration':120},'source':{}}
        index={'duration':210,'mode':'challenge','language':'en','blocks':[],'audio_events':[]}
        with tempfile.TemporaryDirectory() as name,patch.object(director,'call',side_effect=[selection,
                {'ordered_ids':['C001'],'duplicate_ids':[],'reason':'one complete event'}]):
            selected=director.propose(Studio(),job,index,[],Path(name))
        self.assertEqual([(x['start'],x['end']) for x in selected],[(0,210)])
        for start,end in director.candidate_windows(900,1347,[]).values():
            self.assertTrue(900<=start<end<=1347)
            self.assertTrue(61<=end-start<=180)

    def test_final_story_is_reused_only_when_the_spoken_timeline_is_identical(self):
        mapped=[{'start':0,'end':2,'text':'a complete point'}]
        story={k:4 for k in ('hook','clarity','payoff','pacing')}
        story.update(reason='clear point',weakness='mild opening',reject=False)
        visual={'metrics':{k:4 for k in REVIEW_WEIGHTS},'reason':'readable','weakness':'quiet','reject':False,'problems':[]}
        for cached,expected_calls in [(mapped,0),([],1)]:
            with self.subTest(expected_calls=expected_calls),tempfile.TemporaryDirectory() as name:
                folder=Path(name);record={'path':folder/'clip.mp4','mapped':mapped}
                with patch.object(pipeline_v2.render_v2,'render',return_value=record), \
                     patch.object(pipeline_v2.render_v2,'technical_qc',return_value={'passed':True}) as qc, \
                     patch.object(pipeline_v2.render_v2,'review_images',return_value=[]), \
                     patch.object(pipeline_v2.director,'critique',return_value=visual) as vision, \
                     patch.object(pipeline_v2.director,'story_review',return_value=story) as critic:
                    _,review=pipeline_v2.evaluate(None,{'id':'test','config':{'resolution':1080}},Path('source'),
                        {'duration':70},[],{'mode':'conversation'},{},folder,0,{'start':0,'end':70},[],
                        final=True,story_reuse={'mapped':cached,'story':story,'plan':{'duration':70}})
                self.assertEqual(critic.call_count,expected_calls)
                qc.assert_called_once();vision.assert_called_once()
                self.assertEqual(review['story_review_reused'],expected_calls==0)

    def test_resume_keeps_completed_visual_review_when_story_request_fails(self):
        story={k:4 for k in ('hook','clarity','payoff','pacing')}
        story.update(reason='clear point',weakness='mild opening',reject=False)
        visual={'metrics':{k:4 for k in REVIEW_WEIGHTS},'reason':'readable','weakness':'quiet','reject':False,'problems':[]}
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);record={'path':folder/'clip.mp4','mapped':[]}
            with patch.object(pipeline_v2.render_v2,'render',return_value=record), \
                 patch.object(pipeline_v2.render_v2,'technical_qc',return_value={'passed':True}), \
                 patch.object(pipeline_v2.render_v2,'review_images',return_value=[]), \
                 patch.object(pipeline_v2.director,'critique',return_value=visual) as vision, \
                 patch.object(pipeline_v2.director,'story_review',side_effect=[RuntimeError('output limit'),story]) as critic:
                args=(None,{'id':'test','config':{}},Path('source'),{'duration':70},[],{'mode':'conversation'},{},folder,0,{'start':0,'end':70},[])
                with self.assertRaisesRegex(RuntimeError,'output limit'):pipeline_v2.evaluate(*args)
                _,review=pipeline_v2.evaluate(*args)
            self.assertEqual(vision.call_count,1)
            self.assertEqual(critic.call_count,2)
            self.assertEqual(review['score'],80)

    def test_selected_events_get_dense_regions_without_reanalyzing_the_whole_source(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);frames=folder/'frames';frames.mkdir()
            for i in range(200):(frames/f'frame-{i+1:06}.jpg').touch()
            index={'duration':200,'blocks':[{'start':i,'end':min(200,i+60),'regions':[]} for i in range(0,200,60)]}
            def regions(studio,job,paths,out):return [{'faces':[],'texts':[]} for _ in paths]
            with patch.object(analysis,'native_regions',side_effect=regions) as detect:
                analysis.densify_regions(None,{},folder,{'id':'x','start':60,'end':125},index)
                count=detect.call_count
                analysis.densify_regions(None,{},folder,{'id':'x','start':60,'end':125},index)
            self.assertEqual(detect.call_count,count)
            times=sorted(r['at'] for b in index['blocks'] for r in b['regions'])
            self.assertEqual(times,list(range(52,133)))
            self.assertLess(len(times),200)
