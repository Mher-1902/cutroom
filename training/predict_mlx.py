#!/usr/bin/env python3
"""Future sequential MLX inference for saved held-out prompts. GPU use is explicit."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

from common import parse_json, read_jsonl, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gpu-released", action="store_true", help="Operator confirms app acceptance work ended and models unloaded")
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()
    require(args.gpu_released, "GPU use requires explicit --gpu-released after the main app frees it")
    require(not args.out.exists(), "Refusing to overwrite predictions")
    manifest = parse_json((args.data / "manifest.json").read_text())
    require(manifest.get("format_version") == 2,
            "Rebuild prepared data for caption_style/editing_strategy and rerun token checks")
    require(manifest.get("fixture_only") is False, "Never run models on the synthetic format fixtures")
    require(args.base.is_dir() and (args.base / "config.json").is_file(), "Existing local model required")
    config = parse_json((args.base / "config.json").read_text())
    require(config.get("model_type") == "qwen3" and config.get("num_hidden_layers") == 40
            and config.get("hidden_size") == 5120,
            "This runner targets the Qwen3 14B plan pilot; Qwen3.5 9B adapter compatibility is not verified")
    require(importlib.metadata.version("mlx-lm") == "0.32.2", "Use the inspected release or recheck APIs")
    if args.adapter:
        require((args.adapter / "adapter_config.json").is_file()
                and (args.adapter / "adapters.safetensors").is_file(), "Missing adapter files")
    prompts = read_jsonl(args.data / "eval_prompts.jsonl")
    for row in prompts:
        require(all(m["role"] != "assistant" for m in row["messages"]), "Evaluation prompts must not contain target answers")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    # Model imports are intentionally after all explicit execution and dataset guards.
    import mlx.core as mx
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler
    model, tokenizer = load(str(args.base), adapter_path=str(args.adapter) if args.adapter else None,
                            trust_remote_code=False)
    sampler = make_sampler(temp=.7, top_p=.8, top_k=20, min_p=0)
    with args.out.open("x") as handle:
        for n, row in enumerate(prompts):
            mx.random.seed(37 + n)
            prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=False)
            require(len(tokenizer.encode(prompt)) + args.max_tokens <= 8192, "Held-out prompt exceeds pilot inference budget")
            started = time.perf_counter()
            output = generate(model, tokenizer, prompt=prompt, sampler=sampler,
                              max_tokens=args.max_tokens, verbose=False)
            handle.write(json.dumps({"example_id": row["example_id"], "output": output,
                "inference": {"runtime": "mlx-lm-offline-evaluation", "runtime_version": "0.32.2",
                              "wall_seconds": time.perf_counter() - started, "seed": 37 + n,
                              "vllm_deployment_verified": False}}, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"Saved held-out output {n+1}/{len(prompts)}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, ImportError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
