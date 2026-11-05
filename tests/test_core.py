import math
import unittest

from cutroom.core import (ass_escape, ass_time, caption_groups, choose_clips,
                          make_ass, parse_whisper, score_judgment, settings,
                          transcript_chunks, validate_candidate, youtube_url)


class ClipValidationTests(unittest.TestCase):
    def setUp(self):
        self.segments = [{"id": i, "start": i * 5.0, "end": (i + 1) * 5.0,
                          "text": f"Sentence {i}.", "words": []} for i in range(50)]

    def test_model_cannot_invent_or_reverse_boundaries(self):
        for raw in [{"start_id": -1, "end_id": 3}, {"start_id": 3, "end_id": 100}, {"start_id": 5, "end_id": 3}]:
            self.assertIsNone(validate_candidate(raw, self.segments, 15, 30))
        self.assertIsNone(validate_candidate({"start_id": 0, "end_id": 1}, self.segments, 15, 30))
        clip = validate_candidate({"start_id": 2, "end_id": 6}, self.segments, 15, 30)
        self.assertEqual((clip["start"], clip["end"]), (10.0, 35.0))

    def test_deduplication_and_rejection_do_not_fill_with_bad_clips(self):
        clips = [{"start": 0, "end": 60, "score": 80}, {"start": 10, "end": 65, "score": 90},
                 {"start": 90, "end": 150, "score": 99, "reject": True}, {"start": 140, "end": 200, "score": 60}]
        chosen = choose_clips(clips, 7)
        self.assertEqual([c["score"] for c in chosen], [90, 60])

    def test_chunks_cover_full_source_with_overlap(self):
        chunks = transcript_chunks(self.segments, seconds=100, overlap=30)
        covered = {s["id"] for chunk in chunks for s in chunk}
        self.assertEqual(covered, set(range(50)))
        self.assertTrue(set(s["id"] for s in chunks[0]) & set(s["id"] for s in chunks[1]))

    def test_quality_cutoff_excludes_weak_candidates(self):
        candidates = [{"start": 0, "end": 20, "score": 81}, {"start": 40, "end": 60, "score": 47}]
        self.assertEqual(len(choose_clips(candidates, 6)), 1)
        self.assertEqual(len(choose_clips(candidates, 6, min_score=40)), 2)

    def test_judge_scores_are_bounded(self):
        score, metrics = score_judgment(dict.fromkeys(["hook", "clarity", "payoff", "emotion", "shareability"], 3))
        self.assertEqual(score, 60)
        for bad in [0, 6, math.nan, math.inf]:
            values = dict(metrics, hook=bad)
            with self.assertRaises(ValueError):
                score_judgment(values)

    def test_input_validation(self):
        self.assertEqual(youtube_url("https://youtu.be/abc"), "https://youtu.be/abc")
        for url in ["http://youtube.com/watch?v=x", "https://youtube.com.evil.com/x", "https://127.0.0.1/video", "https://user:pass@youtube.com/watch?v=x"]:
            with self.assertRaises(ValueError):
                youtube_url(url)
        for values in [{"min_duration": -1}, {"max_duration": 500}, {"count": 99}, {"model": "qwen3:cloud"}]:
            with self.assertRaises(ValueError):
                settings(values)


class SubtitleTests(unittest.TestCase):
    def test_whisper_millisecond_offsets_and_subword_joining(self):
        payload = {"transcription": [{"offsets": {"from": 1000, "to": 3000}, "text": " Hello world.", "tokens": [
            {"id": 10, "text": " Hello", "offsets": {"from": 1000, "to": 1500}},
            {"id": 11, "text": " world", "offsets": {"from": 1500, "to": 2700}},
            {"id": 12, "text": ".", "offsets": {"from": 2700, "to": 3000}}]}]}
        result = parse_whisper(payload)
        self.assertEqual(result[0]["start"], 1.0)
        self.assertEqual(result[0]["words"][1]["text"], "world.")
        self.assertEqual(result[0]["words"][1]["end"], 3.0)

    def test_relative_timing_and_override_injection(self):
        segment = {"start": 10, "end": 12, "text": "hello", "words": [
            {"start": 10, "end": 11, "text": "Hello"}, {"start": 11, "end": 12, "text": "{\\pos(0,0)}world"}]}
        result = make_ass([segment], {"start": 10, "end": 12})
        self.assertIn("0:00:00.00,0:00:01.00", result)
        self.assertNotIn("{\\pos(0,0)}", result)
        self.assertEqual(ass_time(3661.23), "1:01:01.23")
        self.assertNotIn("\\", ass_escape("text\\Nnew"))

    def test_missing_word_alignment_uses_one_phrase(self):
        segments = [{"start": 1, "end": 3, "text": "A complete phrase", "words": []}]
        groups = caption_groups(segments, {"start": 0, "end": 4})
        self.assertEqual(len(groups[0]), 1)


if __name__ == "__main__":
    unittest.main()
