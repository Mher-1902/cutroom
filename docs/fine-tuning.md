# Cutroom fine-tuning preparation — 5 November 2026

**Recommendation: finish the source/evidence pipeline and collect licensed human edit decisions before training.** A small director adapter is a reasonable experiment. There is no trained adapter or evidence that fine-tuning currently improves Cutroom. All work completed here was CPU-only preparation; no model downloads, package installs, GPU inference, or training were performed by this agent.

The host is the verified Apple M5 with 24 GiB unified memory. The app's Qwen3 14B Q4_K_M inference calibration passed 22 structured responses in about 624 seconds without added swap, according to the main app's session measurements. That establishes an inference result for that workload, not training capacity. The rejected 27B configurations should not be retried as part of this pilot.

**What should be learned.** Generic marketing, advertising, or business-management prose is a poor first dataset for choosing source-video beats. The useful targets are complete setup→attempt→outcome selections; source-faithful 61–120 second edit plans; restrained hooks; pacing; preserved context; real payoffs; and rejection of repeated coverage of the same event. Advertising knowledge becomes relevant for a separate actual advertising task with a concrete audience, licensed product footage, truthful claims, and approved examples. It does not establish that entertainment edits will be engaging or profitable.

The current app already supplies `SceneIndex`, `ClipEditPlan`, and `DraftReview` contracts. Keep those deterministic checks after fine-tuning. Earlier calibration produced 1–2 second snippets despite an instruction requesting longer clips; a bounded window-ID contract then succeeded. Repetitive ASR, oversized evidence packets, and incomplete multimodal review are orchestration/data issues. An adapter should not be used to conceal them. Freeze the improved prompt/evidence baseline first, and retain the unchanged baseline for comparison.

**Verified free training route.** Qwen3 14B is a text causal model with 14.8B parameters and 40 layers, available under Apache 2.0. Its text role fits editing structured observations; it does not directly see raw frames or hear audio. Keep the existing vision/Whisper/native-Vision stages as evidence providers. Its non-thinking mode can be explicitly selected in the chat template. This is a suitability judgment, not a video-editing benchmark result. [Qwen's official model card](https://huggingface.co/Qwen/Qwen3-14B)

MLX-LM **0.32.2** is the inspected release. Its Qwen3 implementation exposes the normal attention projections, and the tuner wraps linear/quantized linear layers with LoRA. This supports a Qwen3 MLX LoRA/QLoRA experiment even though the prose LoRA guide's family list still mentions Qwen2. Runtime success and memory fit on this particular machine remain untested. [Release](https://pypi.org/project/mlx-lm/0.32.2/), [Qwen3 implementation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/models/qwen3.py), [generic LoRA conversion](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/utils.py)

Use `mlx-community/Qwen3-14B-4bit` as a separate training base. Its repository contains about 8.32 GB of MLX safetensors; the config specifies `model_type: qwen3`, 4-bit weights, and group size 64. The included download helper resolves an immutable revision before fetching it and records that revision. The app's existing Ollama GGUF is an inference artifact and is not the trainable MLX checkpoint. A `.safetensors` extension alone does not guarantee compatible tensor layouts or quantization. [MLX model files](https://huggingface.co/mlx-community/Qwen3-14B-4bit/tree/main), [model config](https://huggingface.co/mlx-community/Qwen3-14B-4bit/blob/main/config.json)

The example config trains only q/v adapters in the last four layers, rank 4, batch 1, gradient accumulation 4, checkpointing, a 2,048-token cap, and a low learning rate. These are conservative starting choices, not measured optimums. MLX quantized LoRA uses MLX's quantized base; do not assume bitsandbytes/NF4 or CUDA commands apply. The inspected example uses `scale`, not a PEFT-style `alpha`. [MLX-LM config example](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/examples/lora_config.yaml)

**Smallest useful pilot.** Begin with one plan adapter. Aim for approximately 80–120 human-approved plans from at least eight original training source/event groups; 16–24 validation plans from at least two different groups; and 20 held-out finished edits from at least five additional groups. These counts are a practical starting proposal, not a statistically powered quality claim. If the available data is smaller, use it to improve the prompt and annotation process first.

For every held-out source, also annotate the complete candidate-window sweep and a global ranking with duplicate decisions. Do not evaluate only a hand-picked opening minute. A long source may require many selection windows beyond the 20 finished-edit cases. Keep the entire original episode/event, overlapping windows, alternate cuts, reuploads, and crops in one split. The included tools reject split conflicts by original group and media hash. Reserve test sources before selecting the final training examples.

Do not train the critic in this first run. First collect real blinded A/B human preferences with reasons tied to hook, clarity, payoff, pacing, visual coherence, caption readability, and sound balance. The last three require reviewing actual renders. A later critic experiment can learn those judgements, with calibration against fresh humans. Calling the base model's own scores “human preference” or training on every produced clip would make the evaluation misleading. Preference learning is not automatically enabled by the ordinary LoRA/SFT command provided here.

**Data rights and labels are the current blocker.** Use user-owned footage or an explicit licence that permits the intended training use, and retain evidence of that permission and who verified it. Public availability, a source URL, a reference example, attribution, or an added watermark is not a training licence. The currently discussed other-creators' footage has unverified rights and must not be imported as real training data. The scripts perform no YouTube scraping or fetching. They record attestations; they cannot independently determine ownership or platform originality/payout eligibility.

Every real label must be reviewed by an actual person who checked the full source, source times, and factual support. Mark model-generated drafts as drafts until corrected and approved. Keep all engagement outcomes empty unless they are real, attributable observations with appropriate permissions. There are no fabricated human labels, views, retention results, or performance outcomes in the deliverables. The invented bridge records are explicitly synthetic format fixtures and rejected by default.

**Data and evaluation tooling.** `training/prepare_dataset.py` emits MLX-LM chat records with system/user/assistant messages. The inspected loader uses the final assistant message as the masked completion. Rights, split metadata, and audit hashes stay outside the trainer's chat examples. All supplied window evidence is included; oversized examples fail the exact tokenizer gate instead of silently dropping the answer. MLX-LM can truncate overlong sequences, which is why this separate check matters. [Dataset loader](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/datasets.py), [batch truncation behavior](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)

`training/evaluate.py` consumes saved predictions and checks current app plan validation, source-window bounds, finished plan duration, unknown ranking IDs, repeated event keys, missing outputs, one-to-one temporal selection overlap, duplicate precision/recall, and pairwise ranking agreement. Optional `render_path` values are measured using ffprobe; a valid plan alone is not a verified finished clip. It reports full-source selection-window coverage and real blinded human preferences separately. Mechanical checks cannot establish the truth of a caption, verify every semantic duplicate, or measure actual entertainment quality.

Before accepting an adapter, require all held-out plan outputs to meet the hard structural/time rules; all delivered renders to measure 61–120 seconds; all held-out source timelines to be covered; and no source-truth or context failures after human review. Compare selection recall and duplicate rejection with the frozen baseline, including distinct late-source events. Review both successful and rejected cases. Report raw human wins/losses/ties and an interval grouped by source, plus failure counts and latency/memory. A small apparent win with wide uncertainty is inconclusive. Lower validation loss is insufficient, and virality is not guaranteed.

**Commands prepared for later use.** Run from `/Users/mher/Documents/Codex/2026-11-05/if-x20/outputs/cutroom`. The first block is CPU-only and already verified with the current system Python:

```sh
python3 -m unittest discover -s training -p 'test_*.py' -v
python3 training/readiness.py
```

There are 12 passing regression checks. The prepared fixture evaluation is labelled `fixture_only: true`, with `performance_evidence: false`. It echoes invented answers; it is not model inference. `training/README.md` explains the schemas and examples.

The following setup/download commands are **prepared, not executed**. Use the existing app's Python 3.12 only to create an isolated environment under `training/`; install nothing into the running app environment. The inspected package lists Python 3.11–3.13. The default shell Python here is 3.15.2, so it is not the proposed training interpreter.

```sh
data/venv/bin/python -m venv training/.venv
training/.venv/bin/python -m pip install --cache-dir training/pip-cache 'mlx-lm[train]==0.32.2'
training/.venv/bin/python -m pip freeze > training/environment.lock.txt
training/.venv/bin/python training/fetch_base.py --download
```

After licensed sources and real human examples are supplied at the indicated paths:

```sh
training/.venv/bin/python training/prepare_dataset.py --sources training/sources.jsonl --examples training/examples.jsonl --out training/prepared
training/.venv/bin/python training/check_tokens.py --data training/prepared --tokenizer training/base-qwen3-14b-4bit --max-seq-length 2048 --memory-gate-out training/memory-gate-data
training/.venv/bin/python training/readiness.py
```

The exact-token check reads the local tokenizer only. Do not solve an oversized packet by silently cutting the final answer or omitting relevant source context. Make a reviewed, bounded evidence representation that matches the actual app call, or test a larger sequence budget separately.

**24 GiB readiness gate.** Training must wait until the main agent releases the GPU and unloads competing director, vision, transcription, and render work. The inventory cannot establish this from the present sandbox because host memory/process telemetry is blocked; missing telemetry is reported as a blocker, not a green result. The parent app's verified hardware/inference measurements are retained above. No further permission was requested because the authorized task here is preparation.

After the GPU is free, use the longest approved train/validation examples for a separate four-microstep memory smoke test. This reaches one accumulated optimizer update, with validation/checkpoint work included. It is not enough to assess quality. Discard its adapter. Observe host memory pressure and swap externally throughout; stop if memory pressure becomes sustained yellow/red, swap increases, or the system becomes unresponsive. Require no added swap and normal memory pressure before continuing. Leave ordinary macOS headroom; do not raise wired-memory limits to force the model to fit.

```sh
/usr/bin/time -l training/.venv/bin/mlx_lm.lora --config training/qlora-pilot.yaml --data training/memory-gate-data --iters 4 --steps-per-report 1 --steps-per-eval 4 --save-every 4 --val-batches 1 --adapter-path training/adapters/memory-gate
```

If that gate fails, reduce the sequence budget only where the task still fits, reduce adapted layers, or evaluate a separately identified smaller-base pilot. A 14B inference fit does not promise 14B training fit. Never substitute a smaller model and label the result as the 14B director.

Only after all gates pass, the planned pilot command is:

```sh
training/.venv/bin/mlx_lm.lora --config training/qlora-pilot.yaml
```

The 160 configured iterations are microsteps, approximately 40 optimizer updates with accumulation 4. Use validation to choose the checkpoint; avoid repeated test-set tuning. These arguments are supported by the inspected CLI, but this local training run has not been attempted. [MLX-LM training CLI](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/lora.py)

For a fair adapter comparison, run the same pinned MLX base, evidence, prompt, sampling settings, and seed list with and without the adapter, one at a time. The prepared runner explicitly selects Qwen's non-thinking template, uses temperature .7/top-p .8/top-k 20, and requires `--gpu-released`. It stores raw outputs, including failures, rather than repairing invalid outputs invisibly. These scripts have been syntax/guard checked; their model-loading path is intentionally unrun. [MLX sampling API](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/sample_utils.py), [generation API](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/generate.py)

```sh
training/.venv/bin/python training/predict_mlx.py --data training/prepared --base training/base-qwen3-14b-4bit --out training/baseline-predictions.jsonl --gpu-released
training/.venv/bin/python training/predict_mlx.py --data training/prepared --base training/base-qwen3-14b-4bit --adapter training/adapters/pilot --out training/adapter-predictions.jsonl --gpu-released
training/.venv/bin/python training/evaluate.py --sources training/sources.jsonl --cases training/prepared/eval_cases.jsonl --predictions training/adapter-predictions.jsonl --baseline training/baseline-predictions.jsonl --human-judgments training/human-judgments.jsonl --out training/pilot-evaluation.json
```

The existing Ollama app is a second, necessary end-to-end baseline: its Q4_K_M quantization and structured decoding differ from the MLX 4-bit pilot. An MLX win does not by itself justify replacing the app's runtime. Freeze actual production evidence/prompt packing and test rendered results before any integration.

**Deployment compatibility is unresolved.** Native MLX adapter inference is supported through `load(..., adapter_path=...)` or `mlx_lm.generate --adapter-path ...`, so it is the smallest first evaluation route. A prototype MLX adapter endpoint is not yet integrated into Cutroom. Keep the working Ollama model as the default. [MLX adapter inference guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)

Do not follow old tutorials that promise a direct `ADAPTER` Modelfile import: current official Ollama import and Modelfile pages no longer document that directive. This is a documentation/support gap for this deployment, not proof that every historical Ollama build behaves identically. [Current import docs](https://docs.ollama.com/import), [current Modelfile reference](https://docs.ollama.com/modelfile)

Also, `mlx_lm.fuse --export-gguf` explicitly rejects `qwen3` in the inspected release; its direct exporter is limited to llama/mixtral/mistral. Do not give that command as a Qwen3 solution. The larger possible route is dequantized fused safetensors, then llama.cpp's Qwen3 HF converter, then GGUF quantization/import. Qwen3 architecture conversion is present in llama.cpp, but the full MLX-fused→converter→Ollama chain has not been tested here. Dequantizing 14.8B parameters to 16-bit weights alone is about 27.6 GiB, already over this Mac's 24 GiB before working memory, so a conventional full dequantize/fuse should not be attempted on this machine. A streaming/sharded conversion would need its own verified implementation and evaluation. No such exporter was fabricated for this task. [MLX fuse limitations](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/fuse.py), [llama.cpp Qwen3 converter](https://github.com/ggml-org/llama.cpp/blob/master/conversion/qwen.py)

**Current blockers:** licensed source examples and real human preferences; the main acceptance job still owning GPU priority; the separate pinned MLX training environment/base; exact token checks; a monitored training memory gate; and an end-to-end deployment/quality comparison. All can be completed with free local tools, but none should be described as completed training or proven improvement.
