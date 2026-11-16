from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cutroom import agents, highlights, source_judge, pipeline_v2


class AgentTests(unittest.TestCase):
    def test_handoffs_allow_only_role_tools_and_resume_without_duplicate_receipts(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            for _ in range(2):agents.record(folder,'candidate','observer','inspect_source',{'frames':['F01']},{'artifact':'observations.json'})
            data=json.loads((folder/'agent-workflow.json').read_text())
            self.assertEqual(len(data['handoffs']),1)
            with self.assertRaises(ValueError):agents.record(folder,'candidate','observer','export',{}, {})

    def test_replay_cannot_make_a_duplicate_appear_distinct(self):
        clip={'id':'old','edit_plan':{'spans':[{'start':20,'end':80,'kind':'normal'}]}}
        plan={'id':'new','spans':[{'start':30,'end':75,'kind':'normal'}, {'start':100,'end':103,'kind':'replay'}]}
        self.assertEqual(agents.collection_conflict(plan,[clip])['shared_source_seconds'],45)

    def test_disjoint_cuts_are_compared_as_unions_not_outer_bounds(self):
        clip={'id':'old','edit_plan':{'spans':[{'start':40,'end':60,'kind':'normal'}]}}
        plan={'id':'new','spans':[{'start':0,'end':30,'kind':'normal'},{'start':70,'end':100,'kind':'normal'}]}
        self.assertIsNone(agents.collection_conflict(plan,[clip]))
        self.assertIsNone(agents.collection_conflict({**clip['edit_plan'],'id':'old'},[clip]))

    def test_pipeline_admits_disjoint_saved_edit_before_working_candidate(self):
        planned={'id':'new','start':0,'end':100,'spans':[{'start':0,'end':30,'kind':'normal'},
                                                        {'start':70,'end':100,'kind':'normal'}]}
        existing={'id':'old','start':40,'end':60,'edit_plan':{'spans':[{'start':40,'end':60,'kind':'normal'}]}}
        with tempfile.TemporaryDirectory() as name,patch.object(pipeline_v2,'work_candidate',return_value='rendered') as work:
            folder=Path(name);(folder/'plan-new-r0.json').write_text(json.dumps(planned))
            result=pipeline_v2.process_candidate(None,{'config':{},'clips':[existing]},None,{'id':'new'},
                                                  {},[],{},folder,{'new':{'status':'pending'}})
            self.assertEqual(result,'rendered');work.assert_called_once()

    def test_lead_does_not_try_to_repair_boring_source_with_effects(self):
        self.assertEqual(agents.judge_review({'entertainment_passed':False},False,True)['action'],'replace_candidate')
        self.assertEqual(agents.judge_review({},False,False)['action'],'replace_candidate')

    def test_critic_actions_route_mechanical_repairs_without_new_story_generation(self):
        review={'problems':[{'action':'fit_frame'}], 'metrics':{'hook':4,'clarity':4,'payoff':4}}
        self.assertEqual(agents.judge_review(review,False,True)['action'],'apply_fixes')
        review['problems'].append({'action':'more_context'})
        self.assertEqual(agents.judge_review(review,False,True)['action'],'revise_plan')
        self.assertEqual(agents.judge_review(review,True,False)['action'],'export')

    def test_source_verdict_needs_distinct_clear_actor_frames_near_the_peak(self):
        facts={'observations':[{'id':'O01','frame_id':'F01','at':1,'subject':'creator','certainty':'clear'},
                              {'id':'O02','frame_id':'F02','at':3,'subject':'creator','certainty':'uncertain'},
                              {'id':'O03','frame_id':'F03','at':5,'subject':'game_character','certainty':'clear'}]}
        raw={'actor':'creator','peak_frame_id':'F02','support_ids':['O01','O02','O03']}
        self.assertFalse(source_judge.supported(raw,facts,{'F02':3}))
        facts['observations'][1]['certainty']='clear'
        self.assertTrue(source_judge.supported(raw,facts,{'F02':3}))
        raw['support_ids']=['O02','O02']
        self.assertFalse(source_judge.supported(raw,facts,{'F02':3}))

    def test_observer_is_not_conditioned_on_marketing_goal_or_audio_labels(self):
        class Studio:
            def model_cancelled(self,key):return False
        raw={key:{'frame_id':f'F{i}','subject':'creator','certainty':'clear','visible_action':'Sitting in a chair.'}
             for i,key in enumerate(('before','peak','after'))}
        raw['limitations']='Still frames cannot prove who is speaking.'
        def respond(model,system,requests,**kwargs):
            for i,request in enumerate(requests):kwargs['on_result'](i,deepcopy(raw))
        with tempfile.TemporaryDirectory() as name, patch.object(source_judge.runtime,'chat_batch',side_effect=respond) as model:
            result=source_judge.observe(Studio(),{'id':'job'},['source.jpg','camera.jpg'],{'F0':0,'F1':1,'F2':2},Path(name))
            requests=model.call_args.args[2];prompt=requests[0]['prompt']
            self.assertNotIn('mixed_audio',prompt)
            self.assertNotIn('CREATOR HIGHLIGHTS',prompt)
            self.assertIn('Do not infer emotion',prompt)
            self.assertEqual([r['images'] for r in requests],[['camera.jpg'],['source.jpg']])
            self.assertEqual(len(result['observations']),6)
            source_judge.observe(Studio(),{'id':'job'},['source.jpg','camera.jpg'],{'F0':0,'F1':1,'F2':2},Path(name))
            self.assertEqual(model.call_count,1)

    def test_gasps_do_not_exhaust_the_laughter_inspection_budget(self):
        gasp={'human_reaction_score':.15,'reaction_labels':[{'label':'Gasp','score':.15}],'proposal_score':1}
        laugh={'human_reaction_score':.08,'reaction_labels':[{'label':'Laughter','score':.08}],'proposal_score':1}
        self.assertGreater(highlights.proposal_priority(laugh),highlights.proposal_priority(gasp))


if __name__=='__main__':unittest.main()
