# V2 acceptance status

Updated 6 November 2026. This file records verification, not a promise of views or monetization.

- Hardware inspected: Apple M5, 10 CPU cores, 10 GPU cores, 24 GiB unified memory.
- All approved weights acquired locally, including Whisper turbo, Qwen3.5 9B, both 27B quantizations and Qwen3 14B. The audio-event classifier and Python alignment/analysis environment are installed.
- Qwen3.5 27B Q4: failed fit gate; peak process RSS 16.09 GiB, peak Metal allocation 14.82 GiB, additional swap 9.772 GiB.
- Qwen3.5 27B Q3: failed fit gate; peak process RSS 13.86 GiB, peak Metal allocation 12.87 GiB, additional swap 2.117 GiB.
- Initial 14B response test: memory stayed within bounds (8.8 GiB RSS, 8.44 GiB Metal, no added swap), but returned invalid 1–2-second clip boundaries. It was not accepted as calibrated. The revised fit benchmark uses bounded source-window IDs and retains this earlier failed response test.
- Sustained 14B source-window benchmark: **passed** in 624.4 seconds with 22 valid responses, 8.39 GiB peak process RSS, 8.44 GiB Metal allocation, zero added swap and no critical memory pressure. Selected exact profile: Qwen3 14.8B, Q4_K_M.
- Full MrBeast source imported in the original audio language, 1,347 seconds. Complete Whisper turbo transcription saved; full v2 acceptance project: `ff346cda17684596b501abd00de6ce71`.
- Full Kai source imported in the original audio language, 1,547 seconds. Multimodal acceptance is pending.
- GTA link requires legitimate age-authorized access or an uploaded file. No browser cookies were accessed automatically. This reference is not verified.
- 47 application/unit checks pass, including launcher process identity and duplicate-instance protection. The fine-tuning toolkit has 23 separate CPU tests. JavaScript syntax check passes. Native macOS Vision helper compiles.
- Real FFmpeg smoke graphs passed for fit, crop and split with cuts, speed changes, freeze/replay, zooms and SFX. Music/ducking also passed after fixing a duration-format bug.
- Controlled cancellation after calibration preserved the full transcription and the verified profile; resume continued without repeating either stage.
- Corrected Whisper context carryover that repeated short phrases and drifted timestamps. A real 60-second excerpt transcribed in 2.51 seconds with Metal and without the repeated-context artifacts. Full transcription was rebuilt with context disabled. Original-language human uploader captions agreed with the local transcript on 90.5% of words and were selected as the text reference; automatic captions are never preferred over ASR.
- English CPU forced-alignment weights/tokenizer prepared through the resumable Hugging Face cache. The portrait preview aligned 58 segments / 228 words, including numeric phrases.
- A real 72.1-second renderer QA edit completed in about 40 seconds: 720×1280, −14.33 LUFS, −5.21 dBTP, music, SFX, captions, replay, freeze, zooms and credit watermark. Technical checks passed. This was manually selected renderer QA, not an AI-qualified output.
- New 61–120-second defaults and final >60-second export check implemented. Originality and Creator Rewards eligibility remain explicitly unverified for third-party sources.
- Complete v2 real-video clip production, preview/download/ZIP validation, final visual/audio checks and comparison against v1: **pending**.

## Native vLLM Metal migration

- Current generative server: vLLM 0.33.0 + vllm-metal 0.33.0 on local MLX, loopback port 11440. Startup no longer starts Ollama. Whisper/native Vision/alignment helpers remain separate.
- Pinned native 14B director passed **607.9 seconds**, **28 valid structured source-window responses**, **8.36 GiB peak RSS**, **9.99 GiB peak process-tree physical footprint**, **0.519 GiB added swap**, no critical pressure, actual GPU selection verified in the owned worker log. This new profile is separate from the older GGUF/Ollama results above.
- Fresh native 9B two-window batch: **44.1 seconds**, plus **23.9 seconds** model startup. Peak physical footprint **11.40 GiB**, added swap **0.425 GiB**, no critical pressure. An earlier 1.03 GiB-swap attempt failed and was preserved; it was not accepted.
- The user approved the revised **71.72-second** portrait preview with shot-specific crops/wide action views, captions and timed finishing. This remains manually selected renderer QA.
- The same preview at **1080×1920** encoded in **14.4 seconds** using actual VideoToolbox hardware versus **45.9 seconds** with libx264. Both passed technical checks; SSIM mean **0.996095**, minimum **0.991040** across **2,150 frames**. The hardware profile enables final encoding, with CPU fallback on hardware failure.
- New broad mapping covers 60-second source intervals with uniform visual anchors, extra scene/sound cues and full speech, then dense inspection of selected moments. Complete source mapping/selection quality still requires the reference run; brief events between sampled frames can be missed.
- Resumed the saved 22:27 reference project with the new runtime. Completed prior-engine intervals are explicitly labeled in its index. This resumed run cannot establish a cold start end-to-end average.
- No main promotion for these changes yet. A fully qualified real-video run and working exports remain required.

## Selectable clip lengths

The user's latest instruction allows short clips for other platforms. The default remains 61–120 seconds; visible independent controls select 1–10 clips and 15–29 seconds, 30–59 seconds, 61–120 seconds, or a custom 15–180-second range. Browser checks confirmed independent selection and custom 20–45-second input. Regression checks verify that short plans/export QC pass the requested range and fail an incompatible range. Short preset end-to-end AI production is still an acceptance check. The earlier unconditional >60-second rule is superseded by the selected range.
