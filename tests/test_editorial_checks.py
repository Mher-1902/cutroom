import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from cutroom import director
from cutroom import pipeline_v2
from cutroom.post_copy import caption,title
from cutroom import editorial_checks as checks
from cutroom.contracts import ClipEditPlan


class EditorialChecksTests(unittest.TestCase):
    def test_refinement_director_uses_the_same_aligned_speech_as_renderer(self):
        class RenderReached(Exception):pass
        class Studio:
            def event(self,*args):pass
            def update(self,*args,**kwargs):pass
            def check_cancel(self,*args):pass
        aligned=[{'start':26.172,'end':29.124,'text':'Your criminal profile.'}]
        candidate={'id':'event','title':'One topic','start':26.172,'end':100,'fine_evidence':{'summary':'observed'}}
        job={'id':'test','config':{},'clips':[]};state={'revisions':[]}
        with tempfile.TemporaryDirectory() as name,patch.object(pipeline_v2.runtime,'unload'), \
             patch.object(pipeline_v2.analysis,'densify_regions'), \
             patch.object(pipeline_v2.analysis,'align_candidate',return_value=aligned), \
             patch.object(pipeline_v2.director,'make_plan',return_value=ClipEditPlan.parse(
                 {'id':'event','spans':[{'start':26.172,'end':96.172}]},120,60,90).to_dict()) as plan, \
             patch.object(pipeline_v2,'evaluate',side_effect=RenderReached):
            with self.assertRaises(RenderReached):
                pipeline_v2.work_candidate(Studio(),job,Path('source'),candidate,{'language':'en'},[],{'width':1920,'height':1080},Path(name),state,
                                           user_notes='Correct the ending.',starting_revision=1)
        self.assertIs(plan.call_args.args[4],aligned)

    def test_exact_source_bounds_are_kept_in_the_measured_editor(self):
        class Inspected(Exception):pass
        def inspect(studio,job,system,prompt,schema,**kwargs):
            packet=json.loads(prompt[prompt.index('{"proposed_title"'):])
            self.assertTrue(all(26<=p['start']<p['end']<=100 for p in packet['packets']))
            raise Inspected()
        job={'id':'test','config':{'min_duration':60,'max_duration':90},'clips':[]}
        candidate={'id':'event','start':26,'end':100,'title':'One topic','boundary_policy':'exact'}
        with patch.object(director,'call',side_effect=inspect),self.assertRaises(Inspected):
            director.measured_plan(None,job,candidate,{'duration':180,'language':'en'},[])

    def test_styling_instructions_do_not_leak_into_post_copy(self):
        self.assertEqual(title('bold:Criminal profile choices'),'Criminal profile choices')
        self.assertEqual(caption(':bold:Would you risk it?'),'Would you risk it?')
        self.assertEqual(title('Bold choices change the ending'),'Bold choices change the ending')

    def test_edit_selector_receives_short_midpoint_and_maximum_lengths(self):
        class Inspected(Exception):pass
        def inspect(studio,job,system,prompt,schema,**kwargs):
            packet=json.loads(prompt[prompt.index('{"proposed_title"'):])
            lengths={round(p['end']-p['start']) for p in packet['packets']}
            self.assertTrue({60,75,90}.issubset(lengths))
            self.assertEqual(packet['revision_feedback'],'Start at the actual topic.')
            raise Inspected()
        job={'id':'test','config':{'min_duration':60,'max_duration':90},'clips':[]}
        with patch.object(director,'call',side_effect=inspect),self.assertRaises(Inspected):
            director.measured_plan(None,job,{'id':'event','start':0,'end':180,'title':'One topic'},
                                   {'duration':180,'language':'en'},[],feedback='Start at the actual topic.')

    def test_game_versions_are_supported_by_source_text_not_guessed_from_art(self):
        identity=checks.source_identity({'source_metadata':{'title':'Things to know about GTA 6'}},[])
        self.assertIsNotNone(checks.copy_issue({'title':'GTA V criminal profiles'},identity))
        self.assertIsNone(checks.copy_issue({'title':'GTA VI criminal profiles'},identity))
        self.assertIsNone(checks.copy_issue({'title':'GTA 6 criminal profiles'},identity))
        self.assertEqual(checks.game_versions('GTA VI and GTA V'),{'5','6'})

    def test_unknown_game_version_requires_generic_copy_and_real_comparisons_remain_allowed(self):
        identity=checks.source_identity({'source':{'name':'My local video'}},[])
        self.assertIsNotNone(checks.copy_issue({'screen_hook':{'text':'GTA V lets you choose'}},identity))
        self.assertIsNone(checks.copy_issue({'title':'Which criminal profile would you choose?'},identity))
        identity=checks.source_identity({},[{'text':'We compare GTA V and GTA VI.'}])
        self.assertIsNone(checks.copy_issue({'title':'GTA 5 versus GTA 6'},identity))

    def test_clipped_final_how_is_rejected_without_forbidding_a_complete_question(self):
        mapped=[{'start':66,'end':69.8,'text':'Your profile is going to shape how'}]
        problems=checks.review_problems({'duration':70},mapped,{},[],'en')
        self.assertTrue(any(p['action']=='tighten' for p in problems))
        mapped[0]['text']='Want to know how?'
        self.assertEqual(checks.review_problems({'duration':70},mapped,{},[],'en'),[])

    def test_ending_guard_does_not_invent_english_rules_for_other_languages_or_silent_action(self):
        mapped=[{'start':50,'end':60,'text':'And then they'}]
        self.assertEqual(checks.review_problems({'duration':70},mapped,{},[],'en'),[])
        mapped[0].update(end=69.9,text='to')
        self.assertEqual(checks.review_problems({'duration':70},mapped,{},[],'ja'),[])

    def test_window_tail_uses_only_retained_aligned_words(self):
        rows=[{'start':1,'end':6,'text':'That shapes how the story plays out.',
               'words':[{'start':1,'end':2,'text':'shapes'},{'start':2,'end':3,'text':'how'},
                        {'start':3.2,'end':4,'text':'the'},{'start':4.2,'end':5,'text':'story'},
                        {'start':5.2,'end':6,'text':'ends.'}]}]
        self.assertTrue(checks.dangling(checks.interval_tail(rows,0,3)))
        self.assertFalse(checks.dangling(checks.interval_tail(rows,0,6)))
        self.assertTrue(checks.dangling('since they each'))


if __name__=='__main__':unittest.main()
