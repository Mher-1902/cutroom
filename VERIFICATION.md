# V2 acceptance status

Updated 8 November 2026. This file records verification, not a promise of views or monetization. Later dated entries supersede earlier historical status.

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

## 7 November status

49 application tests pass, including selected short-length project creation and preservation of unrelated model servers. The real-video run has **zero qualified exports**: the first edit proposals exceeded duration bounds, and the previous vLLM worker later reported a Metal out-of-memory error. Source analysis, candidate decisions, alignment and raw invalid plans remain saved. Tightened duration/ad-removal instructions, a smaller 8,192-token director context, 256-token prefill chunks and a smaller output cap are implemented; their full real-video acceptance is pending.

At the user's request, a separate Qwen server on port 8687 remains running. Cutroom waits in the background before loading its own large model while another vLLM server is active. Cancellation exits that wait; no external server is stopped or reconfigured. The site remains available. Main promotion is still pending successful real-video output checks.

## Desktop window and editorial guidance

A native Swift/AppKit/WebKit Cutroom.app was compiled, locally signed, installed on the Desktop and opened successfully against the existing studio. The app window displayed the count/length controls and current GPU-wait status. Closing the window leaves background jobs running. Source includes a reproducible Build Desktop.command. macOS iconutil required unsandboxed icon-service access in this Codex session; the produced bundle and signature verified successfully.

Director/critic guidance now explicitly requires a truthful curiosity question, progressive evidence and a delivered answer/payoff, while avoiding invented stakes or filler. Global selection reinforces distinct events rather than alternate crops/hooks of one event. Those prompt changes are implemented, not evidence of a newly qualified real-video output. A launcher regression now waits for the installation lock after the HTTP port closes, fixing rapid restart during shutdown. 50 application tests pass.

## Journal and watermark controls

The empty queued-project journal previously opened to a blank area. It now uses an explicit Open/Close button with an entry count, persistent open state during refresh, current-stage status, and a useful zero-entry explanation. Verified in the native desktop window against the user's queued project.

The username/watermark field is now visible before Create, outside the advanced panel. Blank disables it; the user supplies their own username. Appearance options include a live preview, corner placement and opacity. New defaults are 28px at 1080 output, 20% opacity, a light outline and soft shadow. Existing project settings/exports are preserved. Renderer escaping and style checks pass; native UI verified the 20% preview and empty/off state. 50 application checks and three JavaScript checks pass. No new automatic qualified output is claimed.

## Browser authorization diagnosis

The user correctly saved explicit Safari authorization on project `660054ac1e444231ad280052e4d313a8`. A metadata-only retry returned macOS `Operation not permitted` for Safari's cookie file. The user then explicitly authorized Chrome for the same import. Chrome is installed, but directory metadata access to its standard profile folder also returned `PermissionError: Operation not permitted`; the downloader had hidden that denial as a missing database. No cookie values were printed or exported.

The importer now distinguishes missing consent, denied OS access, missing profile data, keychain errors and rejected YouTube sessions. Chrome's authorized directory-access preflight prevents the misleading missing-database diagnosis. The existing project was retried through a desktop-launched backend and remained blocked by macOS privacy controls. The UI now shows that cause once, with a permission/upload choice. Full Disk Access has not been granted or changed by the agent. 52 application tests and six JavaScript tests pass. No successful restricted-video import or qualified v2 output is claimed.

## 7 November GTA import and planner recovery

After the user granted the desktop app browser access, the explicitly authorized Chrome import succeeded. The 1,608-second source was downloaded and fully transcribed/mapped. The unrelated Qwen server was stopped by the user. Editing no longer requires browser access for this already imported source.

The subsequent run incorrectly reported a quality-cutoff failure at 50%. Inspection showed all six candidates had failed edit-plan validation, with **zero rendered drafts and zero critic reviews**. Errors were invalid normalized framing rectangles and retained durations below the selected 61-second minimum. This was a planner failure, not evidence that the footage failed the editorial rubric.

The corrected planner keeps source bounds, chronology and duration strict. Invalid optional framing falls back to a full-frame fit, and invalid optional graphic/audio cues are omitted with recorded adjustments. It never pads or repeats footage to reach a duration. Saved raw cuts can be recovered without another model call. Technical planning failures retry once after this planner update, while actual critic rejections remain preserved. The first draft is prioritized before batch planning. Failure messages distinguish planning from review, and failed projects display Stopped instead of a frozen percentage.

The existing project resumed from saved analysis. Its first recovered edit rendered at **86.70 seconds, 720×1280**, with **−14.31 LUFS** and **−0.84 dBTP**; technical checks passed. Play/Pause and the 1:26 duration were verified in the native desktop app. The independent critics scored it **55/100** for missing story context and pacing/continuity issues; revision is running. This is a real rendered draft, **not a qualified final export or completed automatic production run**.

57 application tests and seven JavaScript tests pass, including strict duration/source-bound preservation, saved-plan recovery, single retry of technical failures, preservation of critic rejections, and stopped-state messaging. Main promotion remains pending qualified real-video output checks.

## 8 November: reviewer recovery and real hook output

Private diagnostics reproduced the incomplete-review failure: after writing its reason/weakness the model emitted repeated whitespace until its 700-token cap, without completing the required rejection field. Request-level whitespace flags did not correct this installed backend. Enabling compact JSON at the **server's xgrammar configuration** did: the exact previously failing story review completed in **45.47 seconds including 13.52 seconds model startup**, returning **76 output tokens** from a 5,568-token prompt. Truncated answers remain rejected. Review operations retry once, successful visual/story components checkpoint independently, and an unfinished review does not discard other candidate drafts. Revisions with identical rendered content are no longer rendered/reviewed repeatedly.

The independent 60–90-second button was verified in the native desktop window: it sets the length selector and summary to 60–90 seconds. The editor now explicitly chooses optional on-screen hook text; enabled hooks are burned into the opening and off decisions remain off. A local 14B director chose **“What happens when you can't let go?”** for an operator-annotated source interval. The resulting **65.53-second, 1080×1920** edit passed technical checks and both critics at **81/100**, −15.03 LUFS and −0.93 dBTP. Its MP4/SRT/ASS/cover endpoints returned usable range responses; the 12-entry ZIP passed integrity checks. It is available as a separate completed preview project. This verifies model direction/render/review for an annotated interval, **not automatic full-source candidate selection**.

Following user feedback, a more energetic **68.07-second** operator-directed style preview added a muted portrait cold open, short freeze, large animated “WAIT… THIS IS GTA?!” headline, timed visual-detail callouts, punch-ins, licensed music/SFX and a final viewer question. Technical checks passed at **1080×1920**, −14.98 LUFS and −0.91 dBTP. The user accepted this general direction. The preview is not represented as an automatically selected or critic-qualified production run.

## Visual co-editor and fresh hype run

Selected events now send the vision model an **eight-frame timestamped storyboard**, **two motion strips** and, when installed, a separate private approved style image. It returns source-frame IDs, an opening recommendation, a hook angle and shot suggestions. Source times are resolved from measured frame IDs; native face regions support the framing recommendations. The text-only 14B director receives this visual brief, the actual source title, speech and audience brief. It is not described as directly processing images itself. Style-reference content is explicitly separated from source evidence, and private source/reference frames remain outside public Git.

Real GTA visual-brief test: **44.24 seconds total**, four images, 3,930 prompt tokens and 268 output tokens. A separate MrBeast-source check with the same GTA style reference completed in **54.32 seconds** and produced a host/prize/challenge hook without copying GTA wording. These probes verify image input and source-specific recommendations, not that every visual interpretation is correct. Later native-region checks constrain unsupported portrait recommendations.

The previous GTA run was cancelled with its renders and checkpoints retained after the user requested a different direction. A fresh **three-clip, 60–90-second** run uses the hype brief. Source fingerprint/language validation allowed reuse of all **1,608 source frames**, audio, transcription and full-video analysis, while selecting new candidates and plans. The editing journal confirms reuse and fresh selection. This is a warm run and cannot establish cold-start completion timing. Full automatic production acceptance remains pending.

69 application tests and eight JavaScript tests pass. Main remains unchanged pending the required automatic production and export acceptance checks.

## 9 November: long sources, measured planning and revised captions

100 application tests, 23 training-data guard tests and 12 JavaScript tests pass.
Regressions cover the strict >3h automatic boundary, 20 scouts for ten hours,
independent failure/retry/resume, CPU/thermal pauses, complete source mapping,
large resumable uploads, 159-character Unicode post text and all eight story
stages for 15–180-second edits. A generated ten-hour container was probed and
sparsely sought; it is a container/timeline test, not ten-hour AI production.

A prior automatic GTA run completed from cached full-source analysis: two
71/100 exports from three requested, 89.61s and 89.94s, in 118 minutes. Its
copy and planning latency were weak. The corrected director now splits bounded
event selection, story copy and finishing intent; each copy receives evidence
only from its retained event and stage. It cannot combine another challenge's
prize/outcome. The installed xgrammar backend rejected combined string pattern
and length constraints; request validation now catches that incompatibility
before model loading, while Python validates the eight-beat copy with a bounded
copy-only retry. Invalid/incomplete model responses still cannot qualify.

A hierarchical scout/direct/render/review test used the real MrBeast reference
between 1160–1347 seconds, with cached source speech/analysis. The director
selected a complete basketball event at 1249.388–1328.908 seconds. Its 79.52s
1080×1920 export passed both critics at 85/100 and technical checks. Peak model
physical footprint was 13,530,034,536 bytes, additional swap 0, thermal state
nominal. This establishes this scoped real-footage path, not full-source
automatic long-stream selection or a cold-start benchmark.

The user rejected the old video typography. Public Klap creation examples and
documentation informed a replacement: wider bundled type, small phrase groups,
selective active-word color and restrained opening/loop graphics. The user
approved **bold with green highlights** as the default. A browser-tested saved
clip editor now changes presets, font/size/color, positions, animation, opening
title, caption words and framing without an LLM request. The actual UI revision
rendered in 25.67s using VideoToolbox; 1080×1920, 79.52s, −14.61 LUFS, −5.32 dBTP.
Four word corrections kept output timestamps, two earlier exports remain, and
the updated ZIP passed integrity checks with 15 members. Its displayed score is
explicitly the previous AI-reviewed score; the changed style needs user preview.

Remaining acceptance limits: a complete new ten-hour source run and its timing,
all short-length presets in actual AI production, dedicated active-speaker
tracking, multilingual visual font coverage, and private reference selection
recall are not claimed verified. CI checks run on Linux/macOS and compile native
Mac helpers. Source packaging runs only after successful main checks.
