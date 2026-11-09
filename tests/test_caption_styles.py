from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from cutroom import caption_styles, clip_style, render_v2
from cutroom.contracts import ClipEditPlan, remap_words
from cutroom.engine import Studio


def edit():
    return ClipEditPlan.parse({'id':'a'*32,'spans':[{'start':10,'end':28},
        {'kind':'freeze','start':28,'end':28,'duration':1},
        {'kind':'replay','start':26,'end':28},{'start':30,'end':48,'speed':1.2}],
        'layout':'fit','focus':[0,0,1,1],'screen_hook':{'enabled':True,'text':'Can he make it?'}},100,30,60).to_dict()


SPEECH=[{'start':26,'end':28,'text':'yes Lebron', 'words':[
    {'start':26,'end':27,'text':'yes'},{'start':27,'end':28,'text':'Lebron'}]},
    {'start':30,'end':32,'text':'next attempt','words':[
        {'start':30,'end':31,'text':'next'},{'start':31,'end':32,'text':'attempt'}]}]


class CaptionStyleTests(unittest.TestCase):
    def test_word_corrections_keep_cut_replay_and_speed_timing(self):
        plan=edit();mapped=remap_words(SPEECH,plan)
        corrected=caption_styles.corrections(mapped,{'w1':'LeBron','w3':'LEBRON'})
        self.assertEqual([w['text'] for w in caption_styles.words(corrected)],['yes','LeBron','yes','LEBRON','next','attempt'])
        self.assertEqual([(w['start'],w['end']) for w in caption_styles.words(mapped)],
                         [(w['start'],w['end']) for w in caption_styles.words(corrected)])
        self.assertEqual(mapped[0]['text'],'yes Lebron')
        self.assertIn('yes LeBron',render_v2.srt(corrected))
        self.assertAlmostEqual(caption_styles.words(corrected)[-1]['end'],21+2/1.2)

    def test_unsupported_settings_and_caption_ids_fail(self):
        for raw in ({'font':'Arial,0,0'}, {'accent':'#fff;'}, {'size':float('nan')},
                    {'max_words':True},{'size':True},{'position':'outside'},{'preset':'unknown'}):
            with self.assertRaises(ValueError):caption_styles.settings(raw)
        mapped=remap_words(SPEECH,edit())
        for changes in ({'w99':'new'},{'w1':''},{'w1':'two\nlines'}):
            with self.assertRaises(ValueError):caption_styles.corrections(mapped,changes)

    def test_modern_output_uses_bundled_type_and_no_caption_boxes(self):
        plan=edit();plan['caption_settings']={'preset':'focus'};plan['caption_edits']={'w1':'LeBron'}
        ass,mapped,_=render_v2.make_ass(plan,SPEECH,{'blocks':[]},watermark={'watermark_text':'@test {\\pos(0,0)}'})
        self.assertIn('Cutroom Sans',ass);self.assertNotIn('Anton',ass);self.assertNotIn('Barlow',ass)
        self.assertIn('LeBron',ass);self.assertIn('Can he make it?',ass)
        self.assertNotIn('{\\pos(0,0)}',ass)
        self.assertIn('REPLAY',ass)
        for line in ass.splitlines():
            if line.startswith('Style:'):
                self.assertEqual(line.split(',')[15],'1')  # outline, no opaque rectangles
        self.assertEqual(mapped[0]['words'][0]['start'],16)
        self.assertTrue(all(float(w['end'])<=plan['duration'] for w in caption_styles.words(mapped)))

    def test_off_and_original_burned_caption_regions_are_respected(self):
        plan=edit();plan['caption_settings']={'preset':'focus'}
        mapped=remap_words(SPEECH,plan)
        ass=caption_styles.make_ass(plan,mapped,[(0,plan['duration'])],{},'auto')
        self.assertFalse(any(line.startswith('Dialogue: 0,') for line in ass.splitlines()))
        self.assertIn('Can he make it?',ass)
        plan['caption_enabled']=False
        ass,_,_=render_v2.make_ass(plan,SPEECH,{'blocks':[]})
        self.assertFalse(any(line.startswith('Dialogue: 0,') for line in ass.splitlines()))
        plan['caption_enabled']=True
        ass,_,_=render_v2.make_ass(plan,SPEECH,{'blocks':[]},style='none')
        self.assertTrue(any(line.startswith('Dialogue: 0,') for line in ass.splitlines()))

    def test_presets_and_source_text_cannot_inject_ass(self):
        plan=edit();mapped=remap_words(SPEECH,plan)
        mapped=caption_styles.corrections(mapped,{'w1':'LeBron {\\pos(0,0)}'})
        for preset in caption_styles.PRESETS:
            plan['caption_settings']={'preset':preset}
            ass=caption_styles.make_ass(plan,mapped,[],{})
            self.assertNotIn('{\\pos(0,0)}',ass)
            self.assertIn(caption_styles.FONTS[caption_styles.PRESETS[preset]['font']],ass)

    def test_bundled_modern_assets_match_manifest(self):
        root=Path(__file__).resolve().parents[1]/'static/fonts'
        records=json.loads((root/'manifest.json').read_text())['assets']
        for name in ('captions/CutroomSans-ExtraBold.ttf','captions/CutroomStudio-Bold.ttf','montserrat/OFL.txt'):
            record=next(a for a in records if a['path']==name)
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),record['sha256'])
            self.assertEqual(record['license'],'OFL-1.1')


class RestyleTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.studio=Studio.__new__(Studio);self.studio.root=self.root;self.studio.data=self.root/'data'
        self.studio.jobs_dir=self.root/'data/jobs';self.studio.jobs_dir.mkdir(parents=True)
        self.studio.lock=threading.RLock();self.studio.queue=queue.Queue();self.studio.cancel_flags={}
        self.studio.governors={};self.studio.processes={}
        self.folder=self.studio.jobs_dir/('b'*32);self.folder.mkdir()
        self.source=self.root/'source.mp4';self.source.write_bytes(b'media')
        self.clip={'id':'a'*32,'revision':0,'edit_plan':edit(),'video':'/files/old.mp4','thumbnail':'/files/old.jpg','score':85,'rank':1}
        self.job={'id':'b'*32,'pipeline_version':2,'source_file':str(self.source),'config':{'resolution':720,'style':'none'},
                  'status':'complete','events':[],'clips':[self.clip],'metadata':{'width':1920,'height':1080}}
        self.studio.jobs={self.job['id']:self.job}
        (self.folder/f"aligned-{self.clip['id']}.json").write_text(json.dumps(SPEECH))
        (self.folder/'scene-index.json').write_text(json.dumps({'blocks':[]}))

    def test_restyle_queues_without_requiring_a_model_server(self):
        with patch('cutroom.runtime.health',side_effect=AssertionError('No LLM needed')):
            saved=self.studio.restyle(self.job['id'],self.clip['id'],{'revision':0,'caption_settings':{'preset':'clean'}})
        self.assertEqual(saved['status'],'queued')
        self.assertEqual(self.studio.queue.get_nowait(),self.job['id'])
        self.assertEqual(saved['clips'][0]['video'],'/files/old.mp4')
        with self.assertRaises(ValueError):self.studio.restyle(self.job['id'],self.clip['id'],{'revision':0})

    def test_stale_revision_cannot_overwrite_a_new_export(self):
        with self.assertRaisesRegex(ValueError,'has changed'):
            clip_style.validate_request(self.studio,self.job,self.clip,{'revision':1})

    def test_editor_has_output_word_ids_and_original_visible_setting(self):
        result=self.studio.editor(self.job['id'],self.clip['id'])
        self.assertEqual([w['id'] for w in result['words']],['w0','w1','w2','w3','w4','w5'])
        self.assertFalse(result['caption_enabled'])
        self.assertEqual(result['hook_text'],'Can he make it?')

    def test_failed_export_keeps_previous_video(self):
        request=clip_style.validate_request(self.studio,self.job,self.clip,{'revision':0})
        self.job['pending_style']={'clip_id':self.clip['id'],**request}
        before=deepcopy(self.clip)
        with patch('cutroom.render_v2.render',return_value={'path':self.folder/'new.mp4'}), \
             patch('cutroom.render_v2.technical_qc',return_value={'passed':False,'failures':['duration']}):
            with self.assertRaisesRegex(RuntimeError,'previous video remains'):
                clip_style.restyle(self.studio,self.job)
        self.assertEqual(self.job['clips'][0],before)

    def test_success_preserves_history_and_marks_visual_review_as_pending(self):
        self.job['pending_style']={'clip_id':self.clip['id'],**clip_style.validate_request(self.studio,self.job,self.clip,
            {'revision':0,'layout':'crop','focus_x':.8,'caption_edits':{'w1':'LeBron'},'hook_text':'Will he make the shot?','caption_enabled':True})}
        path=self.folder/f"c-{self.clip['id']}-r1-final.mp4"
        record={'path':path,'srt':path.with_suffix('.srt'),'ass':path.with_suffix('.ass'),'mapped':remap_words(SPEECH,edit())}
        with patch('cutroom.render_v2.render',return_value=record) as render, \
             patch('cutroom.render_v2.technical_qc',return_value={'passed':True}), \
             patch('cutroom.render_v2.create_cover'),patch('cutroom.pipeline_v2.package'):
            clip_style.restyle(self.studio,self.job)
        new=self.job['clips'][0]
        self.assertEqual(new['prior_exports'][0]['video'],'/files/old.mp4')
        self.assertTrue(new['style_review']['requires_visual_preview'])
        self.assertEqual(new['edit_plan']['hook'],'Will he make the shot?')
        self.assertTrue(new['edit_plan']['caption_enabled'])
        self.assertEqual(new['edit_plan']['mapping'],self.clip['edit_plan']['mapping'])
        self.assertEqual(new['edit_plan']['layout'],'crop')
        self.assertNotIn('pending_style',self.job)
        self.assertEqual(render.call_count,1)
