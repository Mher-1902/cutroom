from copy import deepcopy
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

from cutroom import scene_layouts,render_v2
from cutroom.contracts import ClipEditPlan,remap_words


def plan():
    return ClipEditPlan.parse({'id':'test','spans':[{'start':0,'end':8,'kind':'normal'}],
        'layout':'crop','focus':[.35,0,.3,1],'music_mood':'none','caption_style':'none',
        'overlays':[],'zooms':[{'at':3,'duration':1,'scale':1.1}],'sfx':[]},10,5,15).to_dict()


def index():
    return {'mode':'gameplay','duration':10,'cuts':[2,5], 'blocks':[{'start':0,'end':10,'events':[],
        'regions':[{'at':1,'faces':[],'texts':[]},{'at':3,'faces':[],
        'texts':[{'text':'Important source text across the screen','rect':[.05,.65,.90,.08],'confidence':.95}]},
        {'at':6,'faces':[],'texts':[]}]}]}


META={'width':1920,'height':1080,'has_audio':True}


class SceneLayoutTests(unittest.TestCase):
    def test_framing_changes_only_on_the_scene_with_at_risk_text(self):
        original=plan();result=scene_layouts.compile_plan(original,index(),META,{})
        self.assertEqual([s['layout'] for s in result['render_spans']],['crop','fit','crop'])
        self.assertEqual(result['spans'],original['spans'])
        self.assertNotIn('render_spans',original)
        self.assertEqual(sum(s['duration'] for s in result['render_spans']),original['duration'])
        self.assertEqual(result['zooms'],[])
        self.assertEqual([(r['start'],r['end']) for r in result['layout_ranges']],[(0,2),(2,5),(5,8)])

    def test_word_timing_stays_identical_through_speed_changes_and_replays(self):
        original=ClipEditPlan.parse({'spans':[{'start':0,'end':4,'kind':'normal','speed':1.25},
             {'start':2,'end':3,'kind':'replay'},{'start':4,'end':8,'kind':'normal'}]},10,5,15).to_dict()
        speech=[{'start':2,'end':3,'text':'payoff','words':[{'start':2,'end':3,'text':'payoff'}]}]
        result=scene_layouts.compile_plan(original,index(),META,{})
        self.assertEqual(result['mapping'],original['mapping'])
        self.assertEqual(remap_words(speech,result),remap_words(speech,original))
        self.assertEqual(sum(s['duration'] for s in result['render_spans']),original['duration'])
        replay=[r for r in result['layout_ranges'] if 3.2<=r['start']<4.2]
        self.assertTrue(replay)

    def test_portrait_source_keeps_full_height_and_no_facecam_split(self):
        original=plan();original['layout']='split';original['facecam']=[0,0,.3,.3]
        result=scene_layouts.compile_plan(original,index(),{'width':1080,'height':1920},{})
        self.assertTrue(all(s['layout']=='fit' for s in result['render_spans']))
        self.assertEqual(result['layout_ranges'][0]['content'],[0,0,1,1])

    def test_wide_graphics_use_the_background_instead_of_covering_the_picture(self):
        result=scene_layouts.compile_plan(plan(),index(),META,{})
        r=result['layout_ranges'][1]
        for kind in ('title','caption'):
            y=scene_layouts.graphic_y(result,3,1,kind)/1920
            self.assertFalse(r['content'][1]<y<r['content'][1]+r['content'][3])

    def test_text_logo_is_not_automatically_treated_as_wide_subtitles(self):
        self.assertFalse(scene_layouts.important_text({'text':'CHANNEL','rect':[.02,.02,.2,.04],'confidence':.95}))
        self.assertTrue(scene_layouts.important_text({'text':'A real explanation','rect':[.1,.7,.8,.04],'confidence':.95}))

    def test_explicit_style_crop_is_preserved_and_stale_derived_shots_rebuild(self):
        compiled=scene_layouts.compile_plan(plan(),index(),META,{})
        compiled['framing_override']=True
        again=scene_layouts.compile_plan(compiled,index(),META,{})
        self.assertTrue(all(s['layout']=='crop' for s in again['render_spans']))
        again['layout']='fit'
        rebuilt=scene_layouts.compile_plan(again,index(),META,{})
        self.assertTrue(all(s['layout']=='fit' for s in rebuilt['render_spans']))
        self.assertEqual(scene_layouts.compile_plan(rebuilt,index(),META,{}),rebuilt)

    def test_split_hook_avoids_the_creator_camera_panel(self):
        edit=plan();edit.update(layout='split',facecam=[0,0,.2,.25],overlays=[])
        compiled=scene_layouts.compile_plan(edit,index(),META,{})
        y=scene_layouts.graphic_y(compiled,0,2,'title',190)/1920
        self.assertGreater(y-190/1920/2,.32)

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg is required')
    def test_real_multiscene_cut_keeps_output_clock_and_playable_audio(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=640x360:r=30:d=10',
                '-f','lavfi','-i','sine=f=440:r=48000:d=10','-c:v','libx264','-threads','1','-preset','ultrafast',
                '-c:a','aac',str(source)],check=True,capture_output=True)
            class Studio:
                root=Path(__file__).resolve().parents[1]
                data=folder
                def run(self,job,args):
                    try:return subprocess.check_output(args,text=True,stderr=subprocess.PIPE)
                    except subprocess.CalledProcessError as exc:raise RuntimeError(exc.stderr) from exc
                def event(self,*args):pass
            metadata={'width':640,'height':360,'has_audio':True}
            edit=plan();edit['spans']=[{'start':0,'end':4,'speed':1.1}, {'start':4,'end':6},
                                      {'start':1,'end':2,'kind':'replay'}, {'start':6,'end':6,'kind':'freeze','duration':.5}]
            edit=ClipEditPlan.parse(edit,10,5,15).to_dict()
            idx=index();idx['cuts']=[1.017,3.254,6.178]
            compiled=scene_layouts.compile_plan(edit,idx,metadata,{})
            result=render_v2.render(Studio(),{'id':'test','config':{'resolution':360,'style':'none','video_encoder':'libx264'}},
                                    source,compiled,[],idx,metadata,folder)
            probed=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(result['path'])]))
            self.assertLess(abs(float(probed['format']['duration'])-edit['duration']),.12)
            self.assertEqual({s['codec_type'] for s in probed['streams']},{'video','audio'})
            video=next(s for s in probed['streams'] if s['codec_type']=='video')
            self.assertEqual((video['width'],video['height']),(720,1280))


if __name__=='__main__':unittest.main()
