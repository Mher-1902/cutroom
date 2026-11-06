# Project working preferences

- Finish the current video workflow and validate real output before broad rewrites.
- Prefer Rust for new CPU-heavy components when profiling identifies a worthwhile bottleneck. Scala is acceptable where it fits. Keep Python bindings for ML libraries and existing working components when their costly operations already execute in native kernels.
- Keep inference local and loopback-only, with no paid model APIs and no Ollama fallback. Test supported native Mac runtimes and report actual speed, memory, and quality. Do not multiply unrelated research-paper speedup claims into a promised end-to-end time.
- Load one large model at a time. Two independent windows may share that same model only within tested memory limits.
- Make editing decisions per content/event. Preserve source meaning, setup, and outcome. Do not apply one high-energy template to every video.
- Default to 61–120 seconds, but honor the user's newer request for 15–29-second, 30–59-second and custom 15–180-second outputs. Validate against the selected range; only an over-one-minute selection requires >60 seconds. Return fewer qualifying clips when appropriate.
- Show a rendered preview before promoting material editing changes to main. The current portrait preview style has been approved; the engine changes still need technical checks.
- Exclude `data/`, credentials, source footage, generated clips, and private reference frames from public Git history. Keep asset manifests and licenses.
- Run focused source checks and real video verification. Do not describe unit tests or a manually selected style preview as a completed AI production run.
