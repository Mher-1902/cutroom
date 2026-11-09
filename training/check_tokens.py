#!/usr/bin/env python3
"""Exact CPU tokenizer-only length gate. No weights, GPU, network, or truncation."""
import argparse
import json
from pathlib import Path
import sys

from common import parse_json, read_jsonl, require, write_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True, help="Existing local MLX model/tokenizer directory")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--memory-gate-out", type=Path, help="New directory with longest train/valid examples only")
    args = parser.parse_args()
    manifest = parse_json((args.data / "manifest.json").read_text())
    require(manifest.get("format_version") == 2,
            "Rebuild prepared data for caption_style/editing_strategy before token checks")
    require(args.tokenizer.is_dir(), "Tokenizer must already exist locally")
    # Deliberately avoid mlx_lm.load: AutoTokenizer reads tokenizer/config only.
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True, trust_remote_code=False)
    report, failures, longest = {}, [], {}
    for split in ("train", "valid", "test"):
        path = args.data / f"{split}.jsonl"
        if not path.read_text().strip():
            report[split] = {"examples": 0}
            continue
        lengths = []
        for n, row in enumerate(read_jsonl(path), 1):
            # Match mlx-lm v0.32.2 ChatDataset.process, including Qwen's template.
            tokens = tokenizer.apply_chat_template(row["messages"], tools=row.get("tools"), return_dict=False)
            prefix = tokenizer.apply_chat_template(row["messages"][:-1], tools=row.get("tools"),
                                                    add_generation_prompt=True, return_dict=False)
            require(len(tokens) > len(prefix), f"{split}:{n}: assistant answer lost")
            lengths.append(len(tokens))
            if split not in longest or len(tokens) > longest[split][0]:
                longest[split] = (len(tokens), row)
            if len(tokens) > args.max_seq_length:
                failures.append({"split": split, "line": n, "tokens": len(tokens)})
        report[split] = {"examples": len(lengths), "max_tokens": max(lengths)}
    print(json.dumps({"max_seq_length": args.max_seq_length, "splits": report, "oversized": failures}, indent=2))
    require(not failures, "Oversized examples: deliberately shorten evidence or raise the tested memory budget; never silently truncate")
    if args.memory_gate_out:
        require("train" in longest and "valid" in longest, "Memory gate needs train and valid examples")
        args.memory_gate_out.mkdir(parents=True, exist_ok=False)
        for split in ("train", "valid"):
            write_jsonl(args.memory_gate_out / f"{split}.jsonl", [longest[split][1]])
        (args.memory_gate_out / "README.txt").write_text(
            "Memory smoke test only: longest training and validation sequences. No test targets. Discard this adapter.\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, ImportError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
