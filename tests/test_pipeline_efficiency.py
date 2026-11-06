from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cutroom import analysis, director, pipeline_v2
from cutroom.contracts import REVIEW_WEIGHTS


class EfficiencyTests(unittest.TestCase):
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
