#!/usr/bin/env python3
"""CPU-only held-out output checks; consumes saved predictions, never runs a model."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import subprocess
import sys

from common import (parse_json, read_jsonl, require, validate_bundle, validate_output, window)


def iou(left, right):
    intersection = max(0, min(left["end"], right["end"]) - max(left["start"], right["start"]))
    union = max(left["end"], right["end"]) - min(left["start"], right["start"])
    return intersection / union if union else 0


def coverage(windows, duration):
    cursor, total = 0, 0
    for a, b in sorted(windows):
        if b > cursor:
            total += b - max(a, cursor)
            cursor = b
    return min(1, total / duration)


def probe(path):
    require(Path(path).is_file(), f"Render does not exist: {path}")
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "json", str(path)], text=True, capture_output=True,
                            timeout=30, check=True)
    duration = float(parse_json(result.stdout)["format"]["duration"])
    require(math.isfinite(duration), "Non-finite rendered duration")
    return duration


def score_run(path, cases, sources):
    predictions = read_jsonl(path)
    by_id = {}
    for prediction in predictions:
        ident = prediction["example_id"]
        require(ident in cases and ident not in by_id, "Unknown or repeated prediction ID")
        by_id[ident] = prediction
    rows = []
    for ident, case in cases.items():
        row = {"example_id": ident, "task": case["task"], "valid": False}
        if ident not in by_id:
            row["error"] = "missing prediction"
            rows.append(row)
            continue
        prediction = by_id[ident]
        try:
            output = prediction["output"]
            if isinstance(output, str):
                output = parse_json(output)  # Reject markdown/fences/extra prose.
            row.update(validate_output(case, sources[case["source_id"]], output))
            row["valid"] = True
            if case["task"] == "plan":
                row["render_verified"] = False
                if prediction.get("render_path"):
                    row["rendered_duration"] = probe(prediction["render_path"])
                    row["render_verified"] = 61 - .05 <= row["rendered_duration"] <= 120 + .05
            elif case["task"] == "select":
                targets = case["target"]["clips"]
                unmatched = list(output["clips"])
                matched = 0
                # One-to-one matching prevents duplicate predictions inflating recall.
                for target in targets:
                    if unmatched:
                        best = max(range(len(unmatched)), key=lambda i: iou(target, unmatched[i]))
                        if iou(target, unmatched[best]) >= .5:
                            unmatched.pop(best)
                            matched += 1
                row["temporal_recall_iou_0_5"] = matched / len(targets) if targets else None
                row["temporal_precision_iou_0_5"] = matched / len(output["clips"]) if output["clips"] else None
            elif case["task"] == "rank":
                gold = case["target"]
                expected, actual = set(gold["duplicate_ids"]), set(output["duplicate_ids"])
                row["duplicate_precision"] = len(expected & actual) / len(actual) if actual else (1 if not expected else 0)
                row["duplicate_recall"] = len(expected & actual) / len(expected) if expected else (1 if not actual else 0)
                common = [i for i in gold["ordered_ids"] if i in output["ordered_ids"]]
                pairs = [(a, b) for n, a in enumerate(common) for b in common[n+1:]]
                rank = {i: n for n, i in enumerate(output["ordered_ids"])}
                row["pairwise_rank_agreement"] = sum(rank[a] < rank[b] for a, b in pairs) / len(pairs) if pairs else None
        except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
            row["valid"] = False
            row["error"] = str(exc)
        rows.append(row)
    plans = [r for r in rows if r["task"] == "plan"]
    task_rates = {task: {"cases": len([r for r in rows if r["task"] == task]),
                         "passes": sum(r["valid"] for r in rows if r["task"] == task)}
                  for task in sorted({r["task"] for r in rows})}
    return {"cases": len(rows), "structural_temporal_pass_rate": sum(r["valid"] for r in rows) / len(rows),
            "by_task": task_rates,
            "plan_render_passes": sum(r.get("render_verified", False) for r in plans),
            "plan_renders_expected": len(plans), "rows": rows}


def preference_report(path, cases, sources):
    groups, seen, counts = defaultdict(list), set(), defaultdict(int)
    failures = {"baseline": 0, "adapter": 0}
    for row in read_jsonl(path):
        ident = row["example_id"]
        require(ident in cases and ident not in seen, "One blinded consensus judgment per test example is required")
        seen.add(ident)
        require(row.get("blinded") is True and bool(row.get("reviewer")), "Real blinded human reviewer required")
        require(row.get("origin") == "human", "Model/synthetic judgments cannot be human evidence")
        winner = row["winner"]
        require(winner in {"baseline", "adapter", "tie"}, "Invalid human preference")
        counts[winner] += 1
        for variant in failures:
            checks = row[variant]
            require(all(type(checks.get(k)) is bool for k in
                        ("claims_supported", "timings_verified", "setup_payoff_complete", "duplicate_free")),
                    "Missing semantic checks for a variant")
            failures[variant] += not all(checks.values())
        group = sources[cases[ident]["source_id"]]["source_group"]
        groups[group].append({"baseline": 0, "tie": .5, "adapter": 1}[winner])
    # Bootstrap entire source groups; overlapping windows are not independent trials.
    samples = []
    rng = random.Random(37)
    values = list(groups.values())
    for _ in range(2000):
        draw = [x for _ in values for x in rng.choice(values)]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    scores = [x for group in values for x in group]
    return {"judged": len(seen), "expected": len(cases), "complete": len(seen) == len(cases),
            "source_groups": len(values), "preferences": dict(counts),
            "adapter_preference_with_half_ties": sum(scores) / len(scores),
            "source_group_bootstrap_95pct": [samples[49], samples[1949]] if len(values) >= 5 else None,
            "semantic_failures": failures,
            "note": "Exploratory interval; small pilot is not evidence of virality or future engagement"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--human-judgments", type=Path)
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    source_rows, examples = read_jsonl(args.sources), read_jsonl(args.cases)
    require(all(e["split"] == "test" for e in examples), "Evaluation accepts held-out test only")
    sources = validate_bundle(source_rows, examples, args.fixtures)
    cases = {e["id"]: e for e in examples}
    selections = defaultdict(list)
    for case in examples:
        if case["task"] == "select":
            selections[case["source_id"]].append(window(case, sources[case["source_id"]]))
    report = {"fixture_only": args.fixtures, "performance_evidence": False,
              "measurement_scope": "Saved-output structural checks; source truth and improvement require real blinded review",
              "promotion_decision": "Human decision required; automated temporal checks do not establish source truth",
              "adapter": score_run(args.predictions, cases, sources),
              "selection_source_coverage": {s: coverage(w, sources[s]["scene_index"]["duration"])
                                            for s, w in selections.items()},
              "uncovered_test_sources": sorted({e["source_id"] for e in examples} - set(selections)),
              "human_preference": None}
    if args.baseline:
        report["baseline"] = score_run(args.baseline, cases, sources)
    if args.human_judgments:
        require(not args.fixtures, "Synthetic fixtures cannot supply human performance judgments")
        require(args.baseline is not None, "Human comparison needs saved baseline and adapter predictions")
        report["human_preference"] = preference_report(args.human_judgments, cases, sources)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.out:
        require(not args.out.exists(), "Refusing to overwrite evaluation report")
        args.out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
