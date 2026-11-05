import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from cutroom import analysis,local_models

@unittest.skipUnless(local_models.binary('ffmpeg'),'FFmpeg unavailable')
class ContainerClockTests(unittest.TestCase):
    def test_positive_clock_is_normalized_without_losing_content(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);source=folder/'offset.mkv'
            subprocess.run([local_models.binary('ffmpeg'),'-hide_banner','-loglevel','error','-y',
                '-f','lavfi','-i','testsrc2=s=160x90:r=10:d=10','-f','lavfi','-i','sine=f=220:r=16000:d=10',
                '-c:v','libx264','-preset','ultrafast','-threads','1','-c:a','aac','-output_ts_offset','15',str(source)],check=True)
            class Studio:
                def run(self,job,args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE)
                def event(self,*a):pass
            studio=Studio();normalized=analysis.normalize_source(studio,{},source,folder)
            metadata=analysis.inspect_source(normalized,lambda args:studio.run({},args))
            self.assertAlmostEqual(metadata['duration'],10,delta=.15)
            self.assertEqual(metadata['width'],160)
            clocks=json.loads(studio.run({},[local_models.binary('ffprobe'),'-v','error','-show_entries','format=start_time:stream=codec_type,start_time,nb_read_frames','-count_frames','-of','json',str(normalized)]))
            self.assertLess(float(clocks['format']['start_time']),.1)
            video=next(s for s in clocks['streams'] if s['codec_type']=='video')
            self.assertEqual(int(video['nb_read_frames']),100)
            self.assertEqual(json.loads((folder/'normalization.json').read_text())['original_container_start'],15)
            self.assertEqual(analysis.normalize_source(studio,{},source,folder),normalized)
