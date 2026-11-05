"""Regression checks for rejecting unsafe or misleading dataset/eval inputs."""
from copy import deepcopy
from pathlib import Path
import unittest

from common import ROOT, read_jsonl, validate_bundle, validate_output, validate_source
from evaluate import coverage, iou, score_run


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.sources = deepcopy(read_jsonl(ROOT / "fixtures/sources.jsonl"))
        self.examples = deepcopy(read_jsonl(ROOT / "fixtures/examples.jsonl"))

    def test_fixtures_pass_only_with_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            validate_bundle(self.sources, self.examples)
        validate_bundle(self.sources, self.examples, True)

    def test_original_group_cannot_leak_to_valid(self):
        self.sources[1]["source_group"] = self.sources[0]["source_group"]
        with self.assertRaisesRegex(ValueError, "leakage"):
            validate_bundle(self.sources, self.examples, True)

    def test_duplicate_original_hash_cannot_leak(self):
        self.sources[1]["sha256"] = self.sources[0]["sha256"]
        with self.assertRaisesRegex(ValueError, "leakage"):
            validate_bundle(self.sources, self.examples, True)

    def test_unverified_training_rights_rejected(self):
        self.sources[0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "training rights"):
            validate_source(self.sources[0])

    def test_generated_label_cannot_become_human_label(self):
        # Deliberately invalid unit-test attestations, never exported as data.
        self.sources[0]["synthetic"] = False
        self.sources[0]["rights"] = {"basis": "user_owned", "permits_training": True,
            "holder": "TEST", "evidence": "TEST ONLY", "verified_by": "TEST", "verified_on": "TEST"}
        self.examples[0]["synthetic"] = False
        self.examples[0]["label"]["origin"] = "model"
        with self.assertRaisesRegex(ValueError, "Generated labels"):
            validate_bundle(self.sources[:1], self.examples[:1])

    def test_uncovered_source_gap_rejected(self):
        self.sources[0]["scene_index"]["blocks"][1]["start"] = 63
        with self.assertRaisesRegex(ValueError, "uncovered"):
            validate_source(self.sources[0], True)

    def test_finished_duration_must_exceed_sixty_seconds(self):
        self.examples[0]["target"]["spans"][0]["end"] = 60
        self.examples[0]["target"]["spans"][0]["duration"] = 60
        with self.assertRaisesRegex(ValueError, "finished clip duration"):
            validate_bundle(self.sources, self.examples, True)

    def test_plan_cannot_leave_evidence_window(self):
        self.examples[0]["target"]["spans"][0]["end"] = 121
        with self.assertRaisesRegex(ValueError, "span end"):
            validate_bundle(self.sources, self.examples, True)

    def test_invalid_rank_id_rejected(self):
        example = self.examples[-1]
        example["target"]["ordered_ids"].append("INVENTED")
        with self.assertRaisesRegex(ValueError, "partition"):
            validate_output(example, self.sources[-1], example["target"])

    def test_repeated_event_key_rejected(self):
        example = self.examples[-2]
        example["target"]["clips"][1]["event_key"] = "first"
        with self.assertRaisesRegex(ValueError, "Repeated event_key"):
            validate_output(example, self.sources[-1], example["target"])

    def test_missing_model_outputs_count_as_failures(self):
        cases = {e["id"]: e for e in self.examples if e["split"] == "test"}
        cases["missing"] = deepcopy(cases["test-plan-fixture"])
        result = score_run(ROOT / "fixtures/predictions.jsonl", cases, {s["id"]: s for s in self.sources})
        self.assertEqual(result["structural_temporal_pass_rate"], .75)
        self.assertEqual(result["plan_render_passes"], 0)

    def test_full_source_coverage_does_not_double_count_overlap(self):
        self.assertEqual(coverage([(0, 100), (50, 150)], 200), .75)
        self.assertEqual(iou({"start": 0, "end": 100}, {"start": 50, "end": 150}), 1/3)


if __name__ == "__main__":
    unittest.main()
