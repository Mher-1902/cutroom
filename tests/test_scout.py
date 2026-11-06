import unittest
from cutroom import scout


class ScoutTests(unittest.TestCase):
    def test_quiet_hour_is_covered_with_sixty_bounded_windows(self):
        seen=[]
        for start in range(0,3600,scout.WINDOW_SECONDS):
            points=scout.positions(start,start+60,3600)
            self.assertEqual(points[0],start);self.assertEqual(points[-1],start+59)
            self.assertLessEqual(max(b-a for a,b in zip(points,points[1:])),6)
            self.assertEqual(len(points),12)
            seen.extend(points)
        self.assertEqual(len(seen),720)
        self.assertEqual(scout.positions(60,63.3,64),[60,61,62,63])

    def test_events_add_samples_without_replacing_uniform_coverage(self):
        events=[{'at':i+.5,'kind':'shout','confidence':.8} for i in range(60)]
        quiet=scout.positions(0,60,60)
        active=scout.positions(0,60,60,cuts=range(60),sounds=events,hint=21)
        self.assertTrue(set(quiet).issubset(active));self.assertLessEqual(len(active),18)
        self.assertTrue(any(abs(p-21)<1 for p in active))

    def test_incomplete_cached_interval_is_never_counted_as_complete(self):
        def block(a,b):return {'start':a,'end':b,'summary':'visible','mode':'challenge','events':[],
                               'regions':[{'at':a,'faces':[],'texts':[]}],'existing_captions':False}
        complete=[block(i,i+12) for i in range(0,60,12)]
        self.assertIsNotNone(scout.legacy_window(complete,0,60))
        self.assertIsNone(scout.legacy_window(complete[:-1],0,60))
        self.assertIsNone(scout.legacy_window([complete[0],*complete[2:]],0,60))
