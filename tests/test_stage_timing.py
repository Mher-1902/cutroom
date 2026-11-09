import threading
import unittest
from unittest.mock import patch
from cutroom.engine import Studio


class StageTimingTests(unittest.TestCase):
    def test_paused_time_is_excluded_and_progress_updates_do_not_reset_clock(self):
        studio=Studio.__new__(Studio);studio.lock=threading.RLock();studio.save=lambda job:None
        job={'status':'queued','stage':'Queued'}
        with patch('cutroom.engine.time.time',side_effect=[10,15,20,1000,1001,1011]):
            studio.update(job,status='running',stage='Analyzing')
            studio.update(job,progress=20)
            studio.update(job,status='cancelled',stage='Cancelled')
            studio.update(job,status='queued',stage='Queued to resume')
            studio.update(job,status='running',stage='Analyzing')
            studio.update(job,status='complete',stage='Ready')
        self.assertEqual(job['stage_seconds']['Analyzing'],20)
        self.assertIsNone(job['stage_started'])
