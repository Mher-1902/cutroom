import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cutroom import remotion_bridge as bridge, remotion_knowledge as knowledge
from cutroom.contracts import remap_words


class RemotionTests(unittest.TestCase):
    def test_cut_replay_speed_words_stay_on_output_clock(self):
        segments=[{'start':10,'end':12,'text':'real payoff',
                   'words':[{'start':10,'end':11,'text':'real'},{'start':11,'end':12,'text':'payoff'}]}]
        plan={'spans':[{'start':10,'end':12,'speed':2,'kind':'normal','out_start':0,'out_end':1,'duration':1},
                       {'start':10,'end':12,'speed':1,'kind':'replay','out_start':1,'out_end':3,'duration':2}]}
        mapped=remap_words(segments,plan)
        words=bridge.caption_styles.words(mapped)
        caps=bridge.captions_for(words,0,3,0)
        self.assertEqual([(c['startMs'],c['endMs']) for c in caps],[(0,500),(500,1000),(1000,2000),(2000,3000)])
        self.assertEqual([c['text'] for c in caps],['real',' payoff',' real',' payoff'])

    def test_project_has_authored_layers_and_escapes_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fonts=root/'static/fonts/captions';fonts.mkdir(parents=True)
            (fonts/'font.ttf').write_bytes(b'test')
            base=root/'prepared.mp4';base.write_bytes(b'media')
            hostile='</div>{process.exit()}\n"hello" TOTAL WIDTH HEIGHT'
            plan={'duration':3,'layout':'fit','spans':[{'out_start':0,'out_end':3,'kind':'normal','duration':3}],
                  'overlays':[{'at':0,'duration':2,'kind':'hook','text':hostile}]}
            mapped=[{'start':0,'end':1,'text':'real','words':[{'start':0,'end':1,'text':'real'}]}]
            out=bridge.compile_project(root,root/'project',plan,mapped,[],{'resolution':720,'watermark_text':hostile},base)
            jsx=(out/'index.tsx').read_text()
            self.assertIn('width={720}',jsx)
            self.assertIn('<CutroomCaptions premountFor={fps} from={0}',jsx)
            self.assertIn('text={'+json.dumps(hostile)+'}',jsx)
            self.assertIn('premountFor={fps}',jsx)
            self.assertEqual((out/'public/prepared.mp4').read_bytes(),b'media')
            self.assertNotIn('.map(',jsx)

    def test_existing_captions_are_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'static/fonts/captions').mkdir(parents=True)
            base=root/'base.mp4';base.write_bytes(b'video')
            plan={'duration':2,'layout':'fit','spans':[{'out_start':0,'out_end':2,'kind':'normal','duration':2}],'overlays':[]}
            mapped=[{'start':0,'end':1,'text':'covered'}]
            out=bridge.compile_project(root,root/'workspace',plan,mapped,[(0,1)],{},base)
            self.assertNotIn('<CutroomCaptions ',(out/'index.tsx').read_text())

    def test_scene_trims_apply_to_video_and_caption_layers_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'static/fonts/captions').mkdir(parents=True)
            base=root/'base.mp4';base.write_bytes(b'video')
            plan={'duration':4,'layout':'fit','spans':[
                {'out_start':0,'out_end':2,'kind':'normal','duration':2},
                {'out_start':2,'out_end':4,'kind':'normal','duration':2}],'overlays':[]}
            mapped=[{'start':2.5,'end':3.5,'text':'second scene'}]
            out=bridge.compile_project(root,root/'workspace',plan,mapped,[],{},base)
            jsx=(out/'index.tsx').read_text()
            self.assertIn('from={60} trimBefore={60} durationInFrames={60}',jsx)
            self.assertIn('from={75} durationInFrames={30}',jsx)
            self.assertNotIn('<Video trimBefore=',jsx)

    def test_library_is_complete_checksummed_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'installed';(src/'remotion-best-practices').mkdir(parents=True)
            (src/'remotion-best-practices/SKILL.md').write_text('captions '*200)
            (src/'private.txt').write_text('asset')
            manifest=knowledge.install(root/'data',src)
            self.assertEqual(len(manifest['files']),2)
            self.assertEqual(len(knowledge.read(root/'data','remotion-best-practices/SKILL.md',10)),10)
            self.assertEqual(knowledge.search(root/'data','captions'),['remotion-best-practices/SKILL.md'])
            with self.assertRaises(ValueError):knowledge.read(root/'data','../../private.txt')

    def test_classic_projects_do_not_dispatch_to_remotion(self):
        from cutroom import render_v2
        with patch.object(bridge,'render',side_effect=AssertionError('Unexpected migration')):
            with patch.object(render_v2,'make_ass',side_effect=ValueError('classic renderer')):
                with self.assertRaisesRegex(ValueError,'classic renderer'):
                    render_v2.render(object(),{'config':{}},None,{'id':'a'},[],{},None,Path('/tmp'))


if __name__=='__main__':unittest.main()
