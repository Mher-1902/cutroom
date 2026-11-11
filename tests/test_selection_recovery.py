import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cutroom import director, longform


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
