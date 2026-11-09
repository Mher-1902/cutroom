"""Regression checks for rejecting unsafe or misleading dataset/eval inputs."""
from copy import deepcopy
from pathlib import Path
import unittest

from common import (PLAN_KEYS, ROOT, app_contracts, messages, output_schema, parse_json,
                    read_jsonl, runtime_model_specs, validate_bundle, validate_output, validate_source)
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

    def test_training_plan_keys_match_current_director_schema(self):
        self.assertEqual(PLAN_KEYS, set(output_schema("plan")["required"]))

    def test_caption_style_is_required_even_when_parser_has_default(self):
        example = self.examples[0]
        del example["target"]["caption_style"]
        with self.assertRaisesRegex(ValueError, "missing or extra"):
            validate_output(example, self.sources[0], example["target"])

    def test_editing_strategy_is_required_even_when_parser_allows_omission(self):
        example = self.examples[0]
        del example["target"]["editing_strategy"]
        with self.assertRaisesRegex(ValueError, "missing or extra"):
            validate_output(example, self.sources[0], example["target"])

    def test_auto_is_input_policy_not_resolved_caption_style(self):
        example = self.examples[0]
        example["target"]["caption_style"] = "auto"
        with self.assertRaisesRegex(ValueError, "Invalid caption_style"):
            validate_output(example, self.sources[0], example["target"])

    def test_invalid_or_incomplete_strategy_is_rejected(self):
        for strategy in ({}, [], {"content_type": "challenge", "pacing": "balanced"},
                         {"content_type": "ad", "pacing": "balanced", "reason": "Fixture"},
                         {"content_type": "challenge", "pacing": "turbo", "reason": "Fixture"},
                         {"content_type": "challenge", "pacing": "balanced", "reason": ""}):
            with self.subTest(strategy=strategy):
                example = deepcopy(self.examples[0])
                example["target"]["editing_strategy"] = strategy
                with self.assertRaisesRegex(ValueError, "editing_strategy"):
                    validate_output(example, self.sources[0], example["target"])

    def test_supported_style_and_strategy_choices_survive_app_parser(self):
        schema = output_schema("plan")["properties"]
        for style in schema["caption_style"]["enum"]:
            for content in schema["editing_strategy"]["properties"]["content_type"]["enum"]:
                for pacing in schema["editing_strategy"]["properties"]["pacing"]["enum"]:
                    with self.subTest(style=style, content=content, pacing=pacing):
                        example = deepcopy(self.examples[0])
                        target = example["target"]
                        target["caption_style"] = style
                        target["editing_strategy"] = {"content_type": content, "pacing": pacing,
                                                      "reason": "Synthetic schema round-trip only"}
                        result = validate_output(example, self.sources[0], target)
                        self.assertEqual(result["caption_style"], style)
                        self.assertEqual(result["editing_strategy"], target["editing_strategy"])

    def test_prompt_defaults_to_auto_and_contains_current_strategy_schema(self):
        example = self.examples[0]
        example["input"].pop("style", None)
        packet = parse_json(messages(example, self.sources[0])[1]["content"])
        self.assertEqual(packet["style_request"], "auto")
        self.assertIn("editing_strategy", packet["output_schema"]["required"])

    def test_explicit_caption_request_is_honored(self):
        example = self.examples[0]
        example["input"]["style"] = "clean"
        example["target"]["caption_style"] = "none"
        with self.assertRaisesRegex(ValueError, "honor the explicit"):
            validate_output(example, self.sources[0], example["target"])
        example["target"]["caption_style"] = "clean"
        validate_output(example, self.sources[0], example["target"])

    def test_optional_shot_layout_and_focus_are_preserved(self):
        example = self.examples[0]
        example["target"]["spans"][0].update(layout="crop", focus=[.2, .1, .5, .8])
        validate_output(example, self.sources[0], example["target"])
        parsed = app_contracts().ClipEditPlan.parse(example["target"], 240).to_dict()
        self.assertEqual(parsed["spans"][0]["layout"], "crop")
        self.assertEqual(parsed["spans"][0]["focus"], [.2, .1, .5, .8])

    def test_unknown_shot_fields_and_unsupported_layout_are_rejected(self):
        for extra in ({"new_scene": "invented"}, {"layout": "split"}, {"focus": [0, 0, 2, 1]}):
            with self.subTest(extra=extra):
                example = deepcopy(self.examples[0])
                example["target"]["spans"][0].update(extra)
                with self.assertRaises(ValueError):
                    validate_output(example, self.sources[0], example["target"])

    def test_runtime_snapshot_metadata_is_read_without_backend_import(self):
        import sys
        specs = runtime_model_specs()
        self.assertEqual(specs["mlx-community/Qwen3-14B-4bit"]["revision"],
                         "a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4")
        self.assertIn("mlx-community/Qwen3.5-9B-MLX-4bit", specs)
        self.assertNotIn("cutroom.vllm_backend", sys.modules)


if __name__ == "__main__":
    unittest.main()
