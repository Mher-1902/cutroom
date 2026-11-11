from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cutroom import highlights,highlight_audio,pipeline_v2
from cutroom.contracts import DraftReview,REVIEW_WEIGHTS


class HighlightTests(unittest.TestCase):
    def test_creator_highlights_are_separate_from_informative_guides(self):
        job={'config':{'content_mode':'auto'},'processing_strategy':{'mode':'long_stream'},
             'source_metadata':{'title':'PLAYING EVERY GTA UNTIL I BEAT IT'}}
        self.assertEqual(highlights.resolve(job),'creator_highlights')
        job['source_metadata']['title']='A long GTA guide explained'
        self.assertEqual(highlights.resolve(job),'balanced')
        job['config']['moment_preference']='creator_highlights'
        self.assertEqual(highlights.resolve(job),'creator_highlights')

    def test_a_polished_npc_cutscene_cannot_pass_the_creator_gate(self):
        verdict={'passes':True,'routine_or_cutscene':False,'interesting_without_edits':True,
                 'standalone':True,'actor':'game_character','creator_visible':True,'creator_change_visible':True,
                 'physical_reaction':'open_mouth_screaming',
                 'emotion':5,'unexpectedness':5,'gameplay_skill':5,'kind':'rage'}
        self.assertFalse(highlights.gate_passes(verdict,{'human_reaction_score':.9}))
        verdict['actor']='creator';verdict['creator_change_visible']=False
        self.assertFalse(highlights.gate_passes(verdict,{'human_reaction_score':.9}))
        verdict['creator_change_visible']=True
        self.assertTrue(highlights.gate_passes(verdict,{'human_reaction_score':.9,'labels':[{'label':'Screaming','score':.9}]}))
        verdict['routine_or_cutscene']=True
        self.assertFalse(highlights.gate_passes(verdict,{'human_reaction_score':.9}))

    def test_a_gasp_cannot_corroborate_invented_uncontrollable_laughter(self):
        verdict={'passes':True,'routine_or_cutscene':False,'interesting_without_edits':True,
                 'actor':'creator','creator_visible':True,'creator_change_visible':True,
                 'physical_reaction':'uncontrollable_laughter','emotion':5,'kind':'laugh'}
        audio={'human_reaction_score':.15,'labels':[{'label':'Speech','score':.8},{'label':'Gasp','score':.15}]}
        self.assertFalse(highlights.gate_passes(verdict,audio))
        audio['reaction_labels']=[{'label':'Laughter','score':.07}]
        self.assertTrue(highlights.gate_passes(verdict,audio))

    def test_camera_panel_can_locate_a_face_away_from_the_image_edge(self):
        regions=[{'faces':[[.3,.35,.08,.04]]} for _ in range(6)]
        self.assertEqual(highlights.facecam_region(regions),[])
        self.assertTrue(highlights.facecam_region(regions,within_camera=True))

    def test_exceptional_gameplay_requires_an_actual_unusual_outcome(self):
        verdict={'passes':True,'routine_or_cutscene':False,'interesting_without_edits':True,
                 'actor':'player_gameplay','unexpectedness':5,'kind':'unexpected_fail'}
        self.assertFalse(highlights.gate_passes(verdict,{}))
        verdict['unusual_gameplay_outcome_visible']=True
        self.assertTrue(highlights.gate_passes(verdict,{}))

    def test_old_eighty_point_review_does_not_prove_entertainment(self):
        review={'score':85,'reject':False,'technical':{'passed':True}}
        self.assertTrue(pipeline_v2.qualified(review,{'min_score':70}))
        self.assertFalse(pipeline_v2.qualified(review,{'min_score':70,'selection_profile':'creator_highlights'}))
        raw={k:5 for k in REVIEW_WEIGHTS};raw.update(reason='Good typography.',weakness='Ordinary conversation.',reject=False,
             problems=[],entertainment_score=2,raw_source_has_standout=False)
        assessed=DraftReview.parse(raw,90).to_dict();assessed['technical']={'passed':True}
        self.assertEqual(assessed['score'],100)
        self.assertFalse(pipeline_v2.qualified(assessed,{'min_score':70,'selection_profile':'creator_highlights'}))

    def test_peak_must_be_in_normal_audible_footage_not_only_a_teaser(self):
        candidate={'highlight_peak':{'start':50,'end':53}}
        plan={'spans':[{'start':50,'end':53,'kind':'teaser','mute':True},
                       {'start':0,'end':40,'kind':'normal'}]}
        self.assertFalse(highlights.retains_peak(plan,candidate))
        plan['spans'].append({'start':48,'end':55,'kind':'normal'})
        self.assertTrue(highlights.retains_peak(plan,candidate))
        self.assertFalse(highlights.interval_contains_peak(0,52,candidate))

    def test_previous_exports_are_archived_without_counting_as_new_highlights(self):
        job={'config':{'selection_profile':'creator_highlights'},'clips':[{'id':'old','video':'/old.mp4','review':{'score':80}}]}
        self.assertEqual(highlights.archive_old_qualifications(job),1)
        self.assertEqual(job['clips'],[])
        self.assertEqual(job['archived_clips'][0]['video'],'/old.mp4')

    def test_native_audio_metadata_keeps_absolute_half_second_times(self):
        text='frame:0 pts:0 pts_time:0\nlavfi.astats.Overall.RMS_level=-20\nlavfi.astats.Overall.Peak_level=-2\nframe:1 pts:4000 pts_time:0.5\nlavfi.astats.Overall.RMS_level=-inf\nlavfi.astats.Overall.Peak_level=-inf\n'
        rows=highlight_audio.parse_stats(text,1800)
        self.assertEqual([r['at'] for r in rows],[1800.25,1800.75])
        self.assertEqual(rows[1]['rms_db'],-100)

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg is required for the real audio-clock check')
    def test_44100_hz_audio_is_resampled_before_half_second_statistics(self):
        class Local:
            def check_cancel(self,key):pass
            def event(self,job,text):pass
            def run(self,job,args,timeout=30):
                return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=timeout,text=True)
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'source.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:sample_rate=44100',
                            '-t','3.25',str(source)],check=True,capture_output=True)
            record=highlight_audio.scan(Local(),{'id':'clock','config':{'count':1}},source,folder,3.25)
            rows=json.loads((folder/'highlight-audio/energy-000.json').read_text())['rows']
            self.assertTrue(record['complete']);self.assertEqual(len(rows),7)
            self.assertEqual(rows[1]['at']-rows[0]['at'],.5)

    def test_reaction_cues_and_peak_proposals_do_not_auto_qualify(self):
        cues=highlight_audio.caption_cues([{'start':10,'text':'Oh my god. Oh my god. Oh my god.'},
                                          {'start':40,'text':'The characters discuss the mission.'}])
        self.assertEqual(len(cues),1);self.assertEqual(cues[0]['cue_source'],'transcript')
        rows=[{'at':i*.5,'rms_db':-30,'peak_db':-20} for i in range(30)]
        rows[20]={'at':10,'rms_db':-5,'peak_db':-1}
        self.assertTrue(highlight_audio.peaks(rows))
        self.assertNotIn('passes',highlight_audio.peaks(rows)[0])


if __name__=='__main__':unittest.main()
