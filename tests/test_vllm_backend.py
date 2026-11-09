import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cutroom import runtime, vllm_backend as backend


class NativeBackendTests(unittest.TestCase):
    def test_context_budget_reserves_output_and_keeps_all_source_images(self):
        from PIL import Image
        import base64
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        counts=[8090,6400]
        def tokenize(request,**kwargs):
            value=json.loads(request.data)
            self.assertEqual(value['chat_template_kwargs'],{'enable_thinking':False})
            self.assertEqual(value['messages'][1]['content'][0]['text'],'all original source evidence')
            return Response(json.dumps({'count':counts.pop(0),'max_model_len':8192}).encode())
        with tempfile.TemporaryDirectory() as name:
            image=Path(name)/'sheet.jpg';Image.new('RGB',(800,400)).save(image)
            body=backend.payload(runtime.VISION_MODEL,'system','all original source evidence',{'type':'object'},[image,image],1400)
            original=image.read_bytes()
            with patch.object(backend.urllib.request,'urlopen',side_effect=tokenize):budget=backend.fit_context(body)
            self.assertEqual(budget['image_resize_rounds'],1)
            self.assertLessEqual(budget['prompt_tokens']+budget['reserved_output_tokens']+32,8192)
            self.assertEqual(body['max_tokens'],1400)
            self.assertEqual(len(body['messages'][1]['content']),3)
            self.assertEqual(image.read_bytes(),original)
            encoded=body['messages'][1]['content'][1]['image_url']['url'].split(',',1)[1]
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as resized:self.assertEqual(resized.size,(640,320))

    def test_oversized_text_is_not_silently_truncated(self):
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        body=backend.payload(runtime.DIRECTORS[0],'system','source evidence',{'type':'object'},None,1400)
        with patch.object(backend.urllib.request,'urlopen',return_value=Response(b'{"count":8090,"max_model_len":8192}')):
            with self.assertRaisesRegex(RuntimeError,'response tokens'):
                backend.fit_context(body)
        self.assertEqual(body['messages'][1]['content'],'source evidence')

    def test_schema_incompatibility_is_caught_before_loading_a_large_model(self):
        schema={'type':'object','properties':{'question':{'type':'string','pattern':'.*[?]$','maxLength':60}}}
        with patch.object(backend,'ensure_model') as load:
            with self.assertRaisesRegex(ValueError,'pattern'):
                runtime.chat(runtime.DIRECTORS[0],'system','source',schema)
            load.assert_not_called()
        from cutroom.editor_contracts import PLAN_SCHEMA
        backend.validate_schema_features(PLAN_SCHEMA)

    def test_structured_responses_cannot_add_unbounded_fields_or_whitespace(self):
        schema={'type':'object','properties':{'detail':{'type':'object','properties':{'score':{'type':'integer'}}}}}
        body=backend.payload(runtime.DIRECTORS[0],'system','source',schema,[],300)
        structured=body['structured_outputs']
        self.assertTrue(structured['disable_any_whitespace'])
        self.assertFalse(structured['json']['properties']['detail']['additionalProperties'])
        self.assertNotIn('additionalProperties',schema)
    def test_other_server_is_detected_without_taking_it_over(self):
        rows='12 /app/vllm serve /model --port 11440\n42 python -m vllm.entrypoints.cli.main serve /other --port 8687\n99 /bin/editor\n'
        with patch.object(backend.subprocess,'check_output',return_value=rows),patch.object(backend,'process_id',return_value=12):
            self.assertEqual(backend.competing_servers(),[{'pid':42,'port':8687}])
        with patch.object(backend,'competing_servers',return_value=[{'pid':42,'port':8687}]), \
             patch.object(backend,'stop') as stop,patch.object(backend,'_record') as record, \
             patch.object(backend.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'Cancelled'):
                backend.ensure_model(runtime.DIRECTORS[0],cancelled=lambda:True)
        stop.assert_called_once();sleep.assert_not_called()
        self.assertEqual(record.call_args_list[0].kwargs['status'],'waiting_for_gpu')

    def test_batch_checkpoints_completed_window_when_its_neighbor_fails(self):
        model=runtime.VISION_MODEL
        saved=[]
        def stream(body,*args):
            if body['messages'][1]['content']=='failed window':
                raise RuntimeError('interrupted response')
            return {'summary':'completed window'},{'completion_tokens':5}
        requests=[{'prompt':text,'schema':{'type':'object'}} for text in ('completed window','failed window')]
        with patch.object(backend,'ensure_model'),patch.object(backend,'stream',side_effect=stream):
            with self.assertRaisesRegex(RuntimeError,'interrupted response'):
                runtime.chat_batch(model,'system',requests,key='job',on_result=lambda i,r:saved.append((i,r)))
        self.assertEqual(saved,[(0,{'summary':'completed window'})])

    def test_partial_or_wrong_revision_does_not_count_as_downloaded(self):
        with tempfile.TemporaryDirectory() as name, patch.object(backend, 'DATA', Path(name)):
            model=next(iter(backend.MODELS));folder=backend.model_path(model);folder.mkdir(parents=True)
            (folder/'config.json').write_text('{"model_type":"qwen3_5"}')
            (folder/'model.safetensors').write_bytes(b'x'*2000)
            self.assertEqual(backend.model_names(),[])
            marker=folder/'cutroom-source.json'
            marker.write_text(json.dumps({'repo':model,'revision':'wrong'}))
            self.assertEqual(backend.model_names(),[])
            marker.write_text(json.dumps({'repo':model,'revision':backend.MODELS[model]['revision']}))
            self.assertEqual(backend.model_names(),[model])

    def test_payload_keeps_images_and_schema_and_refuses_wrong_model(self):
        model=next(iter(backend.MODELS));schema={'type':'object'}
        with tempfile.TemporaryDirectory() as name:
            image=Path(name)/'frame.jpg';image.write_bytes(b'frame')
            body=backend.payload(model,'system','source',schema,[image],500)
            self.assertEqual(body['structured_outputs']['json'],schema)
            self.assertTrue(body['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
            self.assertFalse(body['chat_template_kwargs']['enable_thinking'])
            with self.assertRaises(ValueError):backend.payload('cloud/model','s','p',schema,[],500)
            with self.assertRaises(ValueError):backend.payload('mlx-community/Qwen3-14B-4bit','s','p',schema,[image],500)

    def test_partial_stream_is_not_accepted_even_if_prefix_is_valid_json(self):
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        packet={'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':None}]}
        with patch.object(backend.urllib.request,'urlopen',return_value=Response(b'data: '+json.dumps(packet).encode()+b'\n')):
            with self.assertRaisesRegex(RuntimeError,'without a complete'):
                backend.stream({},lambda:False,lambda r:None,lambda:None)

    def test_stream_collects_actual_usage_and_unregisters(self):
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        packets=[{'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':'stop'}]},
                 {'choices':[],'usage':{'completion_tokens':5,'prompt_tokens':20}}]
        raw=b''.join(b'data: '+json.dumps(p).encode()+b'\n' for p in packets)+b'data: [DONE]\n'
        called=[]
        with patch.object(backend.urllib.request,'urlopen',return_value=Response(raw)):
            result,usage=backend.stream({},lambda:False,lambda r:called.append('register'),lambda:called.append('unregister'))
        self.assertEqual(result,{'ok':True});self.assertEqual(usage['prompt_tokens'],20)
        self.assertEqual(called,['register','unregister'])
