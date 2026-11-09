# Inference and end-to-end speed

References supplied by the user, read 6 November 2026: [Analytics Vidhya's inference guide](https://www.analyticsvidhya.com/blog/2026/10/llm-inference-explained-optimization-techniques/) and [Danilchenko's research guide](https://www.danilchenko.dev/posts/llm-inference-efficiency-guide/). Their recommendations are checked against the installed Mac implementation before use.

The largest identified cost was application design: one visual request per 12 seconds produced 300 serial requests for an hour. At the old measured median of 45.14 seconds per request, that stage projected to about 226 minutes. Replacing Python orchestration with another language would not remove those requests; the expensive math already executes in native kernels.

The new map covers every source interval and the full speech transcript in 60-second broad windows. Uniform visual anchors are supplemented by scene/sound/timestamp cues. Selected candidates receive dense visual inspection and precise face/text regions. Short events between broad samples can still be missed, so reference-event selection and finished clips must be tested rather than treating fewer requests as proof of equal editorial quality.

Implemented or being validated:

- Four-bit model weights, a bounded context, non-thinking structured responses, and concise evidence packets.
- Two fresh vision windows shared the same resident 9B model in **44.1 seconds**, plus **23.9 seconds** for model startup. The test peaked at **11.40 GiB** process-tree physical footprint and added **0.425 GiB** swap, with no critical pressure. An earlier attempt added 1.03 GiB swap and was rejected; the passing configuration bounds context at 8,192 tokens, uses a 768 MiB KV pool and disables the image-processing cache. A warm repeated-image batch is not used to project full-source speed.
- The 14B editor uses bounded eight-bit key/value caches supported by the installed Metal plugin. Its corrected 1.125 GiB cache and 12,288-token context passed a **607.9-second** sustained source-window test: 28 valid responses, 9.99 GiB peak physical footprint, 0.519 GiB additional swap and verified Metal GPU selection. The original undersized-cache failure is retained.
- Candidate inspection and initial edit planning are grouped by model to reduce repeated process/model loads. Per-clip refinement remains checkpointed.
- A final story assessment can be reused only when both the edit plan and mapped speech are identical. Final technical and visual checks still run.
- Mac hardware H.264 encoding passed the real 71.72-second, 1080×1920 edit test: **14.4 seconds** encoding versus **45.9 seconds** with libx264. Both outputs passed duration, size and sound checks; 2,150-frame comparison averaged **0.9961 SSIM** (minimum 0.9910). The local verified renderer profile enables it for final exports, with CPU retry on hardware failure.
- Phase durations, model-load time, input/output tokens, render time, memory pressure, swap, process-tree RSS, and Darwin physical footprint are recorded separately.

The installed plugin supplies paged/chunked attention and prefix caching. Its cache configuration differs from generic CUDA flags; its own documentation is authoritative. Paper results on large NVIDIA systems do not establish end-to-end gains on this M5. Extra draft models, sparse-cache eviction, new training architectures, and hosted diffusion models have not been added. They need compatible model support, memory, licensing, and quality evidence.

The target is a complete run under an hour where feasible. It is not yet a measured service guarantee. Source download speed, source length and complexity, clip count, rejected candidates, and revision rounds affect the result. A successful end-to-end run is required to calibrate the user-facing estimate.

Primary implementation references: [vLLM Metal configuration](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/docs/configuration.md), [Metal KV compression](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/docs/turboquant.md), [supported models](https://github.com/vllm-project/vllm-metal/blob/v0.33.0/docs/supported_models.md).

A full-source trial exposed a selection failure despite valid JSON: generated numerical boundaries left zero valid candidates. A first ID-table attempt also mismatched stories to windows. The current selector gives each small group of real source windows its own speech and visual evidence, selects matching packet IDs, and retains raw decisions. These changes need actual clip qualification; syntactically valid IDs alone do not establish that an event is complete. Initial editing is grouped in batches of up to three so the first preview can appear before all requested clips have been planned.

The interface now shows a mapping-stage projection (about 23–31 minutes for a source hour) separately from the requested editing workload. Full-run duration remains uncalibrated and no longer displays the earlier engine's 4–11-hour planning budget as current timing.
