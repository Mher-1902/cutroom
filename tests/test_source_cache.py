import json
from pathlib import Path
import tempfile
import unittest
import wave

from cutroom import source_cache


class SourceCacheTests(unittest.TestCase):
    def test_fresh_edit_reuses_only_matching_analysis_not_previous_editor_choices(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source.mp4';source.write_bytes(b'original source')
            jobs=root/'jobs';prior=jobs/'old';folder=jobs/'new';prior.mkdir(parents=True);folder.mkdir()
            class Studio:
                jobs_dir=jobs
                def update(self,job,**values):job.update(values)
                def event(self,*args):pass
                def check_cancel(self,*args):pass
            def save(path,value):path.write_text(json.dumps(value))
            save(prior/'job.json',{'id':'old','status':'cancelled','config':{'language':'auto'},
                'analysis_source_fingerprint':source_cache.fingerprint(source)})
            save(prior/'scene-index.json',{'version':2,'duration':6,'blocks':[{'start':0,'end':6}],
                 'audio_events':[],'cuts':[]})
            save(prior/'transcript-turbo.complete.json',{'settings_version':2})
            save(prior/'transcript-turbo.json',{'transcription':[]})
            save(prior/'candidates.json',{'candidates':['OLD EDIT CHOICES']})
            with wave.open(str(prior/'speech.wav'),'wb') as audio:
                audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\0\0'*48000)
            (prior/'frames').mkdir()
            for number in range(6):(prior/'frames'/f'frame-{number+1:06}.jpg').write_bytes(b'cached image')
            save(prior/'frames/ready.json',{'fps':1,'frames':6,'duration':6})
            job={'id':'new','config':{'language':'en','min_duration':60,'max_duration':90}}
            self.assertFalse(source_cache.restore(Studio(),job,source,{'duration':6},folder))
            job['config']['language']='auto'
            self.assertTrue(source_cache.restore(Studio(),job,source,{'duration':6},folder))
            self.assertTrue((folder/'scene-index.json').exists())
            self.assertFalse((folder/'candidates.json').exists())
            self.assertEqual(job['analysis_reused_from'],'old')
            # Copies are independent: a later analysis cannot modify the prior run.
            (folder/'frames/frame-000001.jpg').write_bytes(b'new analysis')
            self.assertEqual((prior/'frames/frame-000001.jpg').read_bytes(),b'cached image')
            other=jobs/'changed';other.mkdir();source.write_bytes(b'changed source')
            self.assertFalse(source_cache.restore(Studio(),{'id':'changed','config':{'language':'auto'}},source,{'duration':6},other))
