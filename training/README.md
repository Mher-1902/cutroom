This folder prepares a small, free local fine-tuning experiment. No model has been trained, downloaded, or shown to improve Cutroom. The scripts used so far run on the CPU. Keep training and inference paused until the main app has finished acceptance testing and released the GPU.

Read the full proposal in [fine-tuning.md](../docs/fine-tuning.md).

Files and purposes:

| File | Purpose |
| --- | --- |
| `common.py` | Validate rights attestations, real human labels, source-group split isolation, full-source indexes, temporal bounds, and app plan contracts. Reads literal app JSON schemas without importing the app runtime. |
| `prepare_dataset.py` | Emit `train.jsonl`, `valid.jsonl`, `test.jsonl`, a manifest, held-out cases, and target-free held-out prompts. Refuses to overwrite an output directory. |
| `check_tokens.py` | Exact local-tokenizer length check; optional longest-example memory-gate data. Needs the later isolated training environment, but never loads weights. |
| `qlora-pilot.yaml` | Conservative, unrun 14B MLX 4-bit LoRA example. |
| `fetch_base.py` | Future explicit model download; resolves and records an immutable Hugging Face revision. No weights are loaded. |
| `predict_mlx.py` | Future serial baseline/adapter inference. Requires `--gpu-released`, a real prepared dataset, a local model, and inspected MLX-LM version. Never runs on fixtures. |
| `evaluate.py` | Score saved held-out outputs; optional ffprobe duration checks and real blinded human preferences. Does not run models. |
| `readiness.py` | Read-only inventory; reports missing dependencies/data/base and unavailable host telemetry. Never asserts that training fits. |
| `test_validation.py` | Rejection/regression tests for provenance, synthetic data, source leakage, invented IDs/times, coverage, and missing outputs. |
| `fixtures/`, `fixture-prepared/`, `fixture-evaluation.json` | Invented format examples and echoed answers only. No footage, human labels, model inference, or improvement evidence. |
| `templates/` | Intentionally incomplete rights/label and human-judgment forms. They fail validation until a human actually completes the work. |

Run these CPU-only checks from `outputs/cutroom`:

```sh
python3 -m unittest discover -s training -p 'test_*.py' -v
python3 training/readiness.py
python3 training/prepare_dataset.py --sources training/fixtures/sources.jsonl --examples training/fixtures/examples.jsonl --out training/fixture-check-new --fixtures
python3 training/evaluate.py --sources training/fixtures/sources.jsonl --cases training/fixture-check-new/eval_cases.jsonl --predictions training/fixtures/predictions.jsonl --fixtures
```

Use a new output path on every preparation/evaluation run. `--fixtures` is only a format demonstration. Never pass `fixture-prepared` or any other synthetic fixture data to the trainer.

Real data uses the same outer source/example structure as `fixtures/`. Set `synthetic` to `false`, use the real media SHA-256, and fill every rights and human-label field shown in `templates/rights-and-label.example.json`. Group an original source, its overlapping candidate windows, reuploads, crops, and derivatives together. The validator rejects a group or media hash shared by train, valid, and test.

Targets support `plan`, `select`, and `rank`; start by training **plan only**. The output shape comes from the current app schema. `plan` targets must survive the real `ClipEditPlan.parse` contract and yield 61–120 seconds after speed changes. The preparation contract for `select` deliberately requires at least 61 source seconds and at most 180 per candidate. `rank` requires an exhaustive partition of candidate IDs into retained and duplicate sets. These preparation choices are stricter than some production candidate heuristics and must not silently replace production behavior.

Every real example needs `label.origin: human`, a reviewer/date, and true `approved`, `full_source_reviewed`, `all_claims_supported`, and `timings_verified` attestations. A checkbox does not establish legal ownership or semantic truth: the responsible human must inspect the evidence. Audio balance, visual coherence, caption placement, and setup/payoff quality also need the actual rendered clip, not just these text records.

Prediction JSONL contains `example_id` and `output` (a JSON object or raw model text). A plan prediction may additionally provide `render_path`; ffprobe measures that real file's duration. Omitted renders remain unverified. Evaluate only prepared `eval_cases.jsonl` records with `split: test`. Do not send `eval_cases` or `test.jsonl` targets to inference; `eval_prompts.jsonl` contains the target-free messages.

Human-judgment JSONL follows `templates/human-judgment.example.json`, with actual human `origin`, reviewer, blinded consensus winner (`baseline`, `adapter`, or `tie`), and explicit semantic checks for both variants. Report both ties and decisive preferences. The source-group bootstrap avoids treating overlapping windows as independent samples; its interval remains exploratory for a small pilot.

Limitations: checks can reject invalid structures, out-of-window times, exact repeated event keys, leaked source groups, or missing predictions. They cannot prove that a title is true, find every semantic duplicate, establish monetization eligibility, or predict virality. The generic source/evidence format is a preparation format, not an automatic export of every production prompt. Freeze and compare actual production prompts before integration.
