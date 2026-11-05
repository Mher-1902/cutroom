# V2 acceptance status

Updated 5 November 2026. This file records verification, not a promise of views or monetization.

- Hardware inspected: Apple M5, 10 CPU cores, 10 GPU cores, 24 GiB unified memory.
- All approved weights acquired locally, including Whisper turbo, Qwen3.5 9B, both 27B quantizations and Qwen3 14B. The audio-event classifier and Python alignment/analysis environment are installed.
- Qwen3.5 27B Q4: failed fit gate; peak process RSS 16.09 GiB, peak Metal allocation 14.82 GiB, additional swap 9.772 GiB.
- Qwen3.5 27B Q3: failed fit gate; peak process RSS 13.86 GiB, peak Metal allocation 12.87 GiB, additional swap 2.117 GiB.
- Initial 14B response test: memory stayed within bounds (8.8 GiB RSS, 8.44 GiB Metal, no added swap), but returned invalid 1–2-second clip boundaries. It was not accepted as calibrated. The revised fit benchmark uses bounded source-window IDs and retains this earlier failed response test.
- Sustained 14B source-window benchmark: **passed** in 624.4 seconds with 22 valid responses, 8.39 GiB peak process RSS, 8.44 GiB Metal allocation, zero added swap and no critical memory pressure. Selected exact profile: Qwen3 14.8B, Q4_K_M.
- Full MrBeast source imported in the original audio language, 1,347 seconds. Complete Whisper turbo transcription saved; full v2 acceptance project: `ff346cda17684596b501abd00de6ce71`.
- Full Kai source imported in the original audio language, 1,547 seconds. Multimodal acceptance is pending.
- GTA link requires legitimate age-authorized access or an uploaded file. No browser cookies were accessed automatically. This reference is not verified.
- 31 application/unit checks pass, including launcher process identity and duplicate-instance protection. The fine-tuning toolkit has 12 separate CPU tests. JavaScript syntax check passes. Native macOS Vision helper compiles.
- Real FFmpeg smoke graphs passed for fit, crop and split with cuts, speed changes, freeze/replay, zooms and SFX. Music/ducking also passed after fixing a duration-format bug.
- Controlled cancellation after calibration preserved the full transcription and the verified profile; resume continued without repeating either stage.
- Corrected Whisper context carryover that repeated short phrases and drifted timestamps. A real 60-second excerpt transcribed in 2.51 seconds with Metal and without the repeated-context artifacts. Full transcription was rebuilt with context disabled. Original-language human uploader captions agreed with the local transcript on 90.5% of words and were selected as the text reference; automatic captions are never preferred over ASR.
- English CPU forced-alignment weights/tokenizer prepared through the resumable Hugging Face cache. Actual selected-clip alignment remains an acceptance check.
- A real 72.1-second renderer QA edit completed in about 40 seconds: 720×1280, −14.33 LUFS, −5.21 dBTP, music, SFX, captions, replay, freeze, zooms and credit watermark. Technical checks passed. This was manually selected renderer QA, not an AI-qualified output.
- New 61–120-second defaults and final >60-second export check implemented. Originality and Creator Rewards eligibility remain explicitly unverified for third-party sources.
- Complete v2 real-video clip production, preview/download/ZIP validation, final visual/audio checks and comparison against v1: **pending**.
