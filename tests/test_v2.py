import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

from cutroom import analysis, core, director, pipeline_v2, render_v2, runtime, source_media, source_captions
from cutroom.contracts import ClipEditPlan, DraftReview, REVIEW_WEIGHTS, SceneIndex, remap_words


def plan(spans=None):
    return ClipEditPlan.parse({'id':'a'*32,'spans':spans or [{'start':10,'end':50}],
                              'focus':[0,0,1,1],'music_mood':'none','layout':'fit'},100,minimum=30).to_dict()

class TimelineTests(unittest.TestCase):
    def test_automatic_treatment_can_differ_for_conversation_and_challenge(self):
        base={'spans':[{'start':10,'end':80}],'layout':'crop','focus':[.3,0,.3,1]}
        talk=ClipEditPlan.parse({**base,'caption_style':'clean','music_mood':'none',
            'editing_strategy':{'content_type':'conversation','pacing':'patient','reason':'Preserve the complete explanation.'}},100).to_dict()
        challenge=ClipEditPlan.parse({**base,'caption_style':'kinetic','music_mood':'tension',
            'editing_strategy':{'content_type':'challenge','pacing':'varied','reason':'Keep the attempt and outcome.'}},100).to_dict()
        speech=[{'start':12,'end':14,'text':'one careful step','words':[{'start':12,'end':12.5,'text':'one'},
            {'start':12.5,'end':13,'text':'careful'},{'start':13,'end':14,'text':'step'}]}]
        quiet=render_v2.make_ass(talk,speech,{'blocks':[]},style='auto')[0]
        animated=render_v2.make_ass(challenge,speech,{'blocks':[]},style='auto')[0]
        self.assertNotIn('\\fscx96',quiet);self.assertIn('\\fscx96',animated)
        with self.assertRaises(ValueError):ClipEditPlan.parse({**base,'editing_strategy':{'content_type':'invented','pacing':'brisk'}},100)

    def test_framing_repair_keeps_unaffected_portrait_shots(self):
        edit=plan([{'start':10,'end':30,'layout':'crop','focus':[.3,0,.3,1]},
                   {'start':30,'end':50,'layout':'crop','focus':[.2,0,.3,1]}])
        fixed=director.apply_revision_actions(edit,{'problems':[{'action':'fit_frame','at':25}]})
        self.assertEqual(fixed['spans'][0]['layout'],'crop');self.assertEqual(fixed['spans'][1]['layout'],'fit')
        self.assertEqual(fixed['mapping'],edit['mapping'])

    def test_shot_framing_is_bounded_and_reviewer_can_restore_wide_action(self):
        edit=plan([{'start':10,'end':30,'layout':'crop','focus':[.3,0,.3,1]},
                   {'start':30,'end':50,'layout':'fit'}])
        self.assertEqual(edit['spans'][0]['focus'],[.3,0,.3,1])
        self.assertEqual(edit['mapping'][0]['out_end'],20)
        crop=render_v2.layout_filter('[in]','[out]',edit,720,1280,{'mode':'challenge','blocks':[]},edit['spans'][0],{'width':1920,'height':1080})
        wide=render_v2.layout_filter('[in]','[out]',edit,720,1280,{'mode':'challenge','blocks':[]},edit['spans'][1],{'width':1920,'height':1080})
        self.assertNotIn('boxblur',crop);self.assertIn('boxblur',wide)
        fixed=director.apply_revision_actions(edit,{'problems':[{'action':'fit_frame'}]})
        self.assertTrue(all('layout' not in s and 'focus' not in s for s in fixed['spans']))
        for bad in ({'layout':'split'},{'focus':[.8,0,.5,1]}):
            with self.assertRaises(ValueError):plan([{'start':10,'end':50,**bad}])

    def test_cut_speed_freeze_replay_captions(self):
        edit=plan([{'start':10,'end':30,'speed':1.25},
                   {'kind':'freeze','start':30,'end':30,'duration':1},
                   {'kind':'replay','start':28,'end':30},
                   {'start':35,'end':55,'speed':.8}])
        segments=[{'start':9,'end':12,'text':'REMOVED retained', 'words':[{'start':9,'end':9.8,'text':'REMOVED'}, {'start':10,'end':12,'text':'retained'}]},
                  {'start':28,'end':30,'text':'payoff','words':[{'start':28,'end':30,'text':'payoff'}]},
                  {'start':35,'end':37,'text':'end','words':[{'start':35,'end':37,'text':'end'}]}]
        mapped=remap_words(segments,edit)
        self.assertEqual([m['text'] for m in mapped],['retained','payoff','payoff','end'])
        self.assertEqual(mapped[0]['words'][0]['start'],0)
        self.assertAlmostEqual(mapped[0]['end'],1.6)
        self.assertEqual(mapped[2]['start'],17)
        self.assertEqual(mapped[3]['start'],19)
        self.assertEqual(mapped[3]['end'],21.5)
        self.assertNotIn('REMOVED',render_v2.srt(mapped))

    def test_unaligned_trim_does_not_invent_removed_words(self):
        segment={'start':0,'end':20,'text':'setup and payoff','words':[]}
        self.assertEqual(remap_words([segment],plan()),[])
        whole={'start':12,'end':14,'text':'whole phrase','words':[]}
        self.assertEqual(remap_words([whole],plan())[0]['text'],'whole phrase')

    def test_reject_bad_and_out_of_order_timeline(self):
        for spans in ([{'start':20,'end':50},{'start':10,'end':30}], [{'start':float('nan'),'end':50}], [{'start':10,'end':20}]):
            with self.assertRaises(ValueError):plan(spans)
        with self.assertRaises(ValueError):
            ClipEditPlan.parse({'spans':[{'start':0,'end':40}]},100,bounds=(10,60))

    def test_scene_index_must_cover_complete_video(self):
        SceneIndex(24,[{'start':0,'end':12},{'start':12,'end':24}],[],[]).validate()
        with self.assertRaises(ValueError):
            SceneIndex(24,[{'start':0,'end':12},{'start':17,'end':24}],[],[]).validate()

    def test_review_sampling_keeps_the_payoff_when_many_cues_exist(self):
        edit={'zooms':[{'at':i*2,'duration':1} for i in range(59)],'overlays':[],'spans':[]}
        positions=render_v2.review_positions(480,4,edit)
        self.assertLessEqual(len(positions),48)
        self.assertEqual(positions[0],0)
        self.assertEqual(positions[-1],479)
        self.assertIn(round(116.35*4),positions)

    def test_watermark_is_escaped_and_does_not_change_transcript(self):
        edit=plan()
        settings=core.settings({'watermark_text':'Source: @creator {\\pos(0,0)}','watermark_opacity':.25,'watermark_position':'top-right'})
        ass,mapped,_=render_v2.make_ass(edit,[],{'blocks':[]},watermark=settings)
        self.assertIn('Source: @creator',ass)
        self.assertIn('\\alpha&HBF&',ass)
        self.assertNotIn('{\\pos(0,0)}',ass)
        self.assertEqual(mapped,[])
        with self.assertRaises(ValueError):core.settings({'watermark_opacity':float('nan')})

    def test_review_and_technical_gates(self):
        raw={k:4 for k in REVIEW_WEIGHTS};raw.update(reason='clear',weakness='slow',reject=False,problems=[])
        review=DraftReview.parse(raw,40).to_dict();self.assertEqual(review['score'],80)
        review['technical']={'passed':True};self.assertTrue(pipeline_v2.qualified(review,{'min_score':70}))
        review['technical']['passed']=False;self.assertFalse(pipeline_v2.qualified(review,{'min_score':70}))

    def test_existing_source_captions_suppress_generated_group(self):
        edit=plan();segments=[{'start':12,'end':13,'text':'hello','words':[{'start':12,'end':13,'text':'hello'}]}]
        index={'blocks':[{'existing_captions':True,'regions':[{'at':12,'texts':[{'rect':[.1,.7,.7,.1],'text':'hello there','confidence':.95}]}]}]}
        ass,_,preserved=render_v2.make_ass(edit,segments,index)
        self.assertGreater(preserved,0);self.assertNotIn('hello',ass)
        self.assertIn('hello',render_v2.srt(remap_words(segments,edit)))

class ImportTests(unittest.TestCase):
    def test_short_duration_presets_survive_planning_and_export_checks(self):
        for low,high,length in [(15,29,25),(30,59,45),(61,120,72)]:
            with self.subTest(low=low):
                config=core.settings({'min_duration':low,'max_duration':high})
                edit=ClipEditPlan.parse({'spans':[{'start':0,'end':length}]},180,low,high).to_dict()
                self.assertEqual(edit['duration'],length)
                class Studio:
                    def run(self,job,args,**kwargs):
                        if '-show_format' in args:
                            return json.dumps({'format':{'duration':length},'streams':[{'codec_type':'video','width':720,'height':1280},{'codec_type':'audio'}]})
                        return '{"input_i":"-16","input_tp":"-2"}'
                with patch('cutroom.render_v2.local_models.binary',return_value='tool'):
                    qc=render_v2.technical_qc(Studio(),{'config':config},Path('clip.mp4'),length,720)
                    wrong=render_v2.technical_qc(Studio(),{'config':{**config,'min_duration':100,'max_duration':120}},Path('clip.mp4'),length,720)
                self.assertTrue(qc['passed'],qc)
                self.assertFalse(wrong['passed'])

    def test_timestamp_hint_never_trims_source(self):
        url,hint=source_media.normalize_url('https://www.youtube.com/watch?v=_c2e1NcI3Sc&t=20m21s')
        self.assertEqual(url,'https://www.youtube.com/watch?v=_c2e1NcI3Sc');self.assertEqual(hint,1221)
        self.assertEqual(source_media.auth_arguments({}),[])

    def test_browser_requires_explicit_consent(self):
        for auth in ({'browser':'chrome'},{'browser':'chrome','consent':'true'},{'browser':'curl','consent':True}):
            with self.assertRaises(ValueError):source_media.auth_arguments({'youtube_auth':auth})
        self.assertEqual(source_media.auth_arguments({'youtube_auth':{'browser':'safari','consent':True}}),['--cookies-from-browser','safari'])

    def test_original_audio_over_dub(self):
        formats=[{'format_id':'dub','vcodec':'none','acodec':'aac','language':'es','abr':256},
                 {'format_id':'original','vcodec':'none','acodec':'aac','language':'en','format_note':'English original','abr':128}]
        self.assertEqual(source_media.select_audio({'language':'en','formats':formats}),'original')

    def test_ten_defaults_and_no_silent_small_model(self):
        self.assertEqual(core.settings({})['count'],10)
        self.assertGreater(core.settings({})['min_duration'],60)
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(runtime.profile(d)['verified'])
            self.assertNotRegex(runtime.profile(d)['director'],r'(?i)(?:^|[-:/])4b(?:[-:/]|$)')
            self.assertRegex(runtime.profile(d)['director'],r'(?i)14b')

class CaptionImportTests(unittest.TestCase):
    def test_duplicate_styling_and_zero_width_characters_are_removed(self):
        event={'tStartMs':1000,'dDurationMs':2000,'segs':[{'utf8':'\u200bHello ','tOffsetMs':0},{'utf8':'world','tOffsetMs':1000}]}
        result=source_captions.parse_json3({'events':[event,event]},10)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['text'],'Hello world')
        self.assertEqual(result[0]['words'][1]['start'],2)
        self.assertEqual(result[0]['words'][1]['end'],3)
    def test_unrelated_captions_do_not_replace_asr(self):
        self.assertLess(source_captions.agreement([{'text':'unrelated source'}],[{'text':'the original spoken sentence'}]),.6)

class RecoveryTests(unittest.TestCase):
    def test_truncated_audio_is_rebuilt_and_asr_committed_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            def wav(path,duration):
                with wave.open(str(path),'wb') as f:
                    f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*int(duration*16000))
            wav(folder/'speech.wav',2)
            class Studio:
                data=folder
                calls=[]
                def run(self,job,args):
                    self.calls.append(args)
                    if Path(args[0]).name=='ffmpeg':wav(Path(args[-1]),40)
                    else:
                        prefix=args[args.index('-of')+1]
                        Path(prefix+'.json').write_text(json.dumps({'transcription':[], 'result':{'language':'en'}}))
                    return ''
            studio=Studio();job={'config':{'language':'auto'},'source':{}}
            with patch('cutroom.local_models.binary',side_effect=lambda n:n):
                analysis.transcribe(studio,job,folder/'source.mp4',folder,{'has_audio':True,'duration':40})
                count=len(studio.calls)
                analysis.transcribe(studio,job,folder/'source.mp4',folder,{'has_audio':True,'duration':40})
            self.assertEqual(len(studio.calls),count)
            self.assertTrue((folder/'transcript-turbo.complete.json').exists())
            with wave.open(str(folder/'speech.wav')) as f:self.assertEqual(f.getnframes()/f.getframerate(),40)

    def test_refinement_allocates_after_failed_history(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);ident='b'*32
            old={'id':ident,'versions':[{'revision':0}],'revision':0,'edit_plan':{},'rank':1}
            state={'candidate':{'id':ident},'revisions':[{'revision':0},{'revision':4}],'status':'qualified'}
            (folder/'candidate-progress.json').write_text(json.dumps({ident:state}))
            (folder/f'plan-{ident}-r5.json').write_text('{}')
            (folder/'scene-index.json').write_text('{}');(folder/'segments.json').write_text('[]')
            class Studio:
                jobs_dir=folder.parent
                data=folder
                def event(self,*a):pass
            job={'id':folder.name,'pending_refine':{'clip_id':ident,'notes':'new notes'},'clips':[old],'source_file':str(folder/'source.mp4'),'metadata':{}}
            with patch('cutroom.pipeline_v2.work_candidate',return_value=None) as work, patch('cutroom.pipeline_v2.package'),patch('cutroom.pipeline_v2.runtime.unload'):
                pipeline_v2.refine(Studio(),job)
            self.assertEqual(work.call_args.kwargs['starting_revision'],6)
            self.assertEqual(work.call_args.kwargs['user_notes'],'new notes')

if __name__=='__main__':unittest.main()
