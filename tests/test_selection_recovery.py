import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cutroom import director, longform, pipeline_v2
from cutroom.contracts import REVIEW_WEIGHTS


class SelectionRecoveryTests(unittest.TestCase):
    def test_explainer_decisions_replace_empty_v4_cache(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            (folder/'candidates-packets-v4-partial.json').write_text(json.dumps({'through':1,'candidates':[]}))
            (folder/'candidate-packets-v4-000.json').write_text('{"clips":[]}')
            studio=Mock()
            job={'id':'test','config':{'min_duration':60,'max_duration':90},'source':{}}
            index={'duration':100,'language':'en','blocks':[],'audio_events':[]}
            candidate={'window_id':'W001','complete':True,'title':'How the police recognize your car',
                       'setup':'The narrator asks how pursuit works.','payoff':'Changing cars removes the vehicle description.',
                       'event_key':'police','score':4,'reason':'A complete spoken explanation.'}
            def respond(studio,job,system,prompt,schema,**kwargs):
                if 'W001' in schema['properties']:
                    self.assertIn('spoken answer IS the payoff',prompt)
                    self.assertEqual(schema['required'],['W001'])
                    return {'W001':{k:v for k,v in candidate.items() if k!='window_id'}}
                return {'ordered_ids':['C001'],'duplicate_ids':[],'reason':'Complete explanation.'}
            with patch.object(director,'call',side_effect=respond):
                result=director.propose(studio,job,index,[],folder)
            self.assertEqual(len(result),1)
            self.assertTrue((folder/'candidate-packets-v6-000.json').exists())

    def test_each_packet_is_a_required_key_not_a_repeatable_array_item(self):
        schema=director.decision_schema({'W001':[0,180],'W002':[90,270],'W003':[180,360]})
        self.assertEqual(schema['required'],['W001','W002','W003'])
        self.assertEqual(set(schema['properties']),set(schema['required']))
        self.assertNotIn('window_id',schema['properties']['W001']['properties'])

    def test_long_judge_omissions_remain_unapproved_backups(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);studio=Mock()
            candidates=[{'id':str(i),'start':i*200,'end':i*200+100,'title':'Event '+str(i),
                         'setup':'Setup','payoff':'Answer','event_key':str(i),'score':3} for i in range(3)]
            index={'scout_candidates':candidates}
            job={'id':'test','config':{'count':3}}
            with patch.object(director,'call',return_value={'ordered_ids':['C002'],'duplicate_ids':['C001'],'reason':'Distinct.'}):
                selected=longform.propose(studio,job,index,folder)
            self.assertEqual([c['id'] for c in selected],['1','2'])
            record=json.loads((folder/'candidates.json').read_text())
            self.assertEqual(record['discarded_duplicates'],['0'])
            self.assertTrue(any('unranked' in call.args[1] for call in studio.event.call_args_list))

    def test_invalid_critic_is_retried_without_rendering_or_changing_scores(self):
        accepted={'score':72,'reject':False}
        operation=Mock(side_effect=[director.ReviewValidationError('bad timestamp'),accepted])
        self.assertEqual(pipeline_v2.retry_review(Mock(),{},operation),accepted)
        self.assertEqual(operation.call_count,2)
        operation=Mock(side_effect=director.ReviewValidationError('bad timestamp'))
        with self.assertRaises(director.ReviewValidationError):pipeline_v2.retry_review(None,{},operation)
        self.assertEqual(operation.call_count,2)

    def test_bad_timestamp_rejection_is_recoverable_but_real_rejection_is_kept(self):
        states={'bad':{'status':'rejected','error':'review timestamp must be in 0–64.31899999999999'},
                'real':{'status':'rejected','error':'The story has no payoff.'}}
        self.assertEqual(pipeline_v2.recover_review_errors(states),1)
        self.assertEqual(states['bad']['status'],'review_error')
        self.assertEqual(states['real']['status'],'rejected')

    def test_critic_decoder_uses_actual_duration_and_parser_stays_strict(self):
        raw={k:4 for k in REVIEW_WEIGHTS}
        raw.update(reason='Clear explanation.',weakness='Small text.',reject=False,
                   problems=[{'at':64.3,'issue':'Small text.','action':'move_captions'}])
        with patch.object(director,'call',return_value=raw) as call:
            result=director.critique(object(),{}, {'duration':64.31899999999999},[],[],{}, {})
        bounds=call.call_args.args[4]['properties']['problems']['items']['properties']['at']
        self.assertEqual(bounds['minimum'],0)
        self.assertLessEqual(bounds['maximum'],64.31899999999999)
        self.assertEqual(result['score'],80)
        raw['problems'][0]['at']=70
        with patch.object(director,'call',return_value=raw),self.assertRaises(director.ReviewValidationError):
            director.critique(object(),{}, {'duration':64.31899999999999},[],[],{}, {})
