#!/usr/bin/env python3
"""Validate provenance/labels/splits and emit MLX-LM chat JSONL. Standard library only."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from common import ROOT, digest, messages, read_jsonl, validate_bundle, write_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New output directory; never overwrites")
    parser.add_argument("--fixtures", action="store_true", help="Allow explicitly synthetic format demonstrations")
    args = parser.parse_args()
    sources, examples = read_jsonl(args.sources), read_jsonl(args.examples)
    by_id = validate_bundle(sources, examples, allow_synthetic=args.fixtures)
    if not args.fixtures and {e["split"] for e in examples} != {"train", "valid", "test"}:
        raise ValueError("Real dataset needs train, valid, test, separated by original source/event group")
    args.out.mkdir(parents=True, exist_ok=False)
    for split in ("train", "valid", "test"):
        rows = [{"messages": messages(e, by_id[e["source_id"]])} for e in examples if e["split"] == split]
        write_jsonl(args.out / f"{split}.jsonl", rows)
    # Audit metadata and target-free prompts remain separate from train JSONL.
    write_jsonl(args.out / "eval_cases.jsonl", [e for e in examples if e["split"] == "test"])
    prompts = [{"example_id": e["id"], "messages": messages(e, by_id[e["source_id"]])[:-1]}
               for e in examples if e["split"] == "test"]
    write_jsonl(args.out / "eval_prompts.jsonl", prompts)
    manifest = {"format_version": 1, "fixture_only": args.fixtures,
                "training_ready": False, "reason": "Exact tokenizer length check and GPU memory gate still required",
                "sources_digest": digest(sources), "examples_digest": digest(examples),
                "counts": dict(Counter(e["split"] for e in examples)),
                "tasks": dict(Counter(e["task"] for e in examples)),
                "source_groups": len({s["source_group"] for s in sources}),
                "contracts_digest": digest({name: (ROOT.parent / "cutroom" / name).read_text()
                                             for name in ("contracts.py", "director.py")})}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if args.fixtures:
        (args.out / "SYNTHETIC-DO-NOT-TRAIN.txt").write_text("FORMAT FIXTURES ONLY. No human labels, real footage, or performance evidence.\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
