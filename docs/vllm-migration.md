# Faster-engine migration — 6 November 2026

The user clarified that faster local inference is the goal: vLLM or comparable methods are acceptable, and Ollama should no longer serve the models. New app startup and v2 generation now target an owned loopback vLLM Metal server, with no Ollama fallback. Old projects stay readable. Previously measured Ollama results are preserved in `profile-v2.json`; they do not validate the new engine. A separate `profile-vllm-v1.json` requires fresh calibration.

The pinned trial uses official vLLM Metal 0.33.0 and its paired macOS vLLM 0.33.0 CPU-tagged wheel. That wheel tag describes the host framework packaging; GPU use comes from the Metal plugin and must be verified in the actual server log. The installer follows the release's separate Torch requirements. Packages live under `data/vllm-venv`; the analysis/alignment environment is separate. `requirements-vllm.lock.txt` records the measured inference environment, with official hashed wheel URLs and immutable MLX source revisions instead of machine-local paths.

Target weights: mlx-community/Qwen3.5-9B-MLX-4bit for vision and mlx-community/Qwen3-14B-4bit for direction/story critique, each pinned to an immutable HF revision in `cutroom/vllm_backend.py`. Exactly one model is loaded at a time. No 4B fallback is introduced. An additional direct-GGUF director trial can reuse existing 14B weights without running Ollama; it is not selected as the production model.

Fast Whisper transcription, native macOS face/OCR, and CPU alignment/audio-event helpers remain. Runtime changes alone are not assumed to reduce their already small share of processing time.

Measured status: installation and pinned MLX snapshots are complete. The 14B director passed a sustained 607.9-second benchmark with 28 structured source-window responses, verified Metal GPU use, 9.99 GiB peak physical footprint and 0.519 GiB additional swap. The 9B model passed fresh-image batching and a finishing test after reducing its context/cache budgets. See [measurements](inference-efficiency.md). Full autonomous source selection, qualification, exports and recovery remain acceptance work.

The prominent count selector accepts every integer from 1 to 10. Both YouTube and upload actions reflect the selection. A whole-source map is still needed for one clip; subsequent clips add inspection, planning, rendering and critique. Time projections must distinguish measured stage throughput from unmeasured full-run behavior. The old engine's hours-long projection is retained only as a historical baseline, not as current-engine timing.

Changes remain on `preview/portrait-editorial`, off main, pending remaining engine acceptance checks. The user has approved the revised portrait editing preview.

Sources: [vLLM Metal 0.33.0 installation](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/install.sh), [supported models](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/docs/supported_models.md), [configuration](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/docs/configuration.md).

## Interrupted-request recovery — 15 November 2026

A stopped GPU worker can leave an HTTP streaming connection open. Active owned
requests now check server health, release a dead connection, restart only the
owned model server and retry the same request once. Successful neighboring batch
windows stay checkpointed. Cancellation, invalid schemas and truncated output do
not silently become accepted responses. Model unloading waits for active inference;
shutdown first interrupts registered connections.

A real local test interrupted a 9B vision request with SIGTERM. The same request
completed after one automatic model restart, with Metal GPU use verified. The
76.55-second measurement includes initial model loading, interruption, reloading
and the recovered response; it is not an end-to-end video estimate.

Older saved jobs could retain a 500 error after a later retry had already returned
a complete source rejection. Resume now archives that stale transport error. A
completed selection with no qualifying moments reports an empty collection and
its editorial reasons, rather than falsely reporting a model/planning crash.
Actual unfinished technical failures stay retryable and distinct from source
quality decisions. Main remains held for the user's video acceptance.
