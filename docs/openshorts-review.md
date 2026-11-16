# OpenShorts review and Cutroom integration

Reference: [mutonby/openshorts](https://github.com/mutonby/openshorts/tree/1c8ed033f189bd30222d10b1d3ec28fe6219ac3a), pinned at `1c8ed033f189bd30222d10b1d3ec28fe6219ac3a` (reviewed 16 November 2026).

The reference was fetched for study, not installed or executed. The complete Git tree contains 560 entries. The local study contains all 428 non-media, non-lock source/config/documentation artifacts; a static AST inventory covers 228 Python modules (68,655 lines), including 138 test modules and 32 commercial cloud modules. This is an inventory, not a claim that every line was dynamically tested. Detailed review focused on the video-creation execution paths, their contracts, prompts, failure handling and regression tests. Demo binaries, generated lockfiles and marketing pages are not implementation evidence.

## Decisions

| Reference technique and code | Decision | Cutroom result |
|---|---|---|
| Score every transcript window, rank globally, detail only the shortlist (`main.get_viral_clips`, `clip_selection.py`) | Keep the existing equivalent; do not replace it with a cloud selector | Cutroom already requires one decision for every bounded evidence packet, ranks globally, uses measured word times and prepares detailed edits only for candidates it needs. Missing decisions remain errors rather than defaulting to the first windows. |
| Per-scene framing and output layout ranges (`reframe_v2.py`, `screencast_layout.py`, `layout_ranges.py`) | Adapt | `scene_layouts.compile_plan` derives render shots at measured source cuts. Native OCR/face evidence protects text and participants. The original story EDL, words, speed changes, replays and source mapping remain intact. |
| Protect source graphics against zooms (`edit_builder.py`) | Adapt | Remove whole-composition punch-ins over protected text, fitted shots and split layouts. The renderer builds all filter strings from validated data. |
| Face/content-aware hook and seam captions (`hook_placement.py`, `layout_ranges.py`) | Adapt | Shared timed placement for ASS and Remotion uses layout ranges, source faces/text, picture bands and competing title overlays. Explicit caption-position choices remain available. |
| Ground hooks in the actual clip rather than a whole-video topic (`hook_grounding.py`, `gemini_worker.py`) | Adapt the evidence rule, keep local inference | Existing close inspection and source-identity checks stay in use. Creator inspection now separates neutral camera/gameplay observations from a separate lead judgment, with frame citations. No Gemini upload. |
| Duplicate filtering by original source overlap (`clip_selection.dedupe_overlapping`) | Strengthen the existing safeguard | A second collection gate compares the union of normal source sections before rendering. Different crops, titles and replays cannot make a repeated source event distinct. Gaps between retained sections do not create false overlap. Existing semantic ranking remains necessary: source overlap cannot prove two topics are independent. |
| Agent tools reuse one underlying pipeline (`mcp_server.py`, `mcp_stdio.py`, `skills/openshorts/`) | Adapt internally | A bounded agent ledger records scouts, observers, directors, framing, rendering, critics and lead decisions. The supervising judge routes specific mechanical fixes, plan revision, export or candidate replacement. It does not execute model-generated commands. |
| Best-first delivery, partial recovery (`main.clip_render_order`, `app.py`, `recut.py`, tests) | Preserve Cutroom's existing checkpoints | One heavy task runs at a time. Finished drafts/exports survive failures. Source-entertainment rejection immediately replaces the candidate instead of spending two revisions decorating ordinary material. |
| Source-aware word recuts (`recut.py`, `editor.py`, `ClipEditor.jsx`) | Keep existing measured-cut/alignment contracts | Cutroom already has exact word mapping, bounded edit spans, caption edits and revision history. No second timeline implementation is imported. |
| Forward frame sampling and tiny shot proxies (`frame_sampler.py`, `scene_detection.py`) | Defer pending a local bottleneck measurement | Do not replace working native routines or add another neural model based on NVIDIA benchmarks. Sparse long-stream seeks and dense excerpt FFmpeg extraction remain. |
| Mouth-activity active speaker, two/four-person tiling (`active_speaker.py`, `split_layout.py`, `panel_layout.py`, `camera_inset.py`) | Defer | Valuable for a labeled podcast test set. Cutroom's current split remains a real measured creator camera plus gameplay; it does not claim multi-speaker diarization. |
| Remove the bottom source-subtitle band (`burned_subtitles.py`) | Do not copy that policy | Cropping can erase meaningful source content. Preserve source captions and suppress conflicting generated captions using the existing native evidence. |
| Rust one-pass CUDA compositor (`osrender/`, `gpu_render.py`, `gpu_decode.py`) | Do not install on the Mac | It requires NVIDIA CUDA/NVDEC/NVENC. It is not an Apple Metal renderer. Existing VideoToolbox encoding stays available. |
| Whisper/Parakeet, TransNetV2, YOLO/MediaPipe stack | Do not replace the calibrated stack blindly | Keep whisper.cpp, native macOS Vision and current scene detection. No new AGPL detector dependency or CPU vision fallback is introduced. |
| Gemini vision/silent-video selection, fal.ai actors, ElevenLabs dubbing, S3/R2, Upload-Post | Exclude | Paid/remote services conflict with local inference/free assets and are unnecessary for the requested clipping workflow. |
| Hosted MCP OAuth, metering, billing, queue prioritization, autopilot and commercial cloud backend | Exclude | Outside the local feature scope; `cloud/` also has a separate restrictive commercial license. No cloud source was ported. |

## How the agent loop works

These are specialized responsibilities, not seven simultaneously loaded LLMs:

1. **Scout:** propose moments from the whole-source index or long-stream audio/caption map. A proposal is not an approved highlight.
2. **Observer:** inspect timestamped source evidence. For creator footage, camera and gameplay images are separate requests on the same 9B model. Each records before/peak/after facts without the desired marketing outcome.
3. **Lead source judge:** use the calibrated 14B model to accept/reject the raw event from those facts, speech and noisy mixed-audio cues. Claims need distinct clear frame citations near the proposed peak. Code still enforces the existing creator/gameplay evidence gate.
4. **Director:** pick measured source cuts and a content-specific eight-beat story, copy and effects. Word alignment and source identity stay authoritative.
5. **Framer/renderer:** compile per-scene layouts and bounded commands, then render a local draft. The model cannot run shell/FFmpeg code.
6. **Critics:** inspect the rendered video, mapped speech, story and audio measurements.
7. **Supervising judge:** export only after all gates pass; apply specific framing/mix fixes directly; ask the director for story/cut revisions; replace an uninteresting source or a candidate that exhausts two revision rounds.

`agent-workflow.json` stores content-addressed handoffs beside project checkpoints. The existing editing report embeds this ledger. Resume does not append identical handoffs twice. A receipt is an audit trail, not proof that a model's observation is true. The ledger has no browser, network, publishing or arbitrary-code tool.

## Limits and validation

- Native OCR can miss text; sampled frames can miss brief actions. Layout protection is evidence-based, not a guarantee that every source graphic is understood.
- Strong source detection needs positive and negative examples. A safe rejection alone does not demonstrate good recall or ten entertaining clips from a long stream.
- No new weights were downloaded or fine-tuned. The current local 14B/9B model choices remain.
- The extra independent source judgment has a cost. Measure it separately; do not claim OpenShorts' paid-Gemini/NVIDIA timings for this Mac.
- Technical checks cover cut/replay/speed mapping, scene-specific framing, portrait preservation, graphics placement, repeated-source detection, tool routing and receipt recovery. Real-media measurements and preview acceptance are recorded separately from unit checks.
- This branch remains off main until the user watches/approves the resulting editing behavior. MP4 downloads remain direct video downloads.

## License boundary

The OpenShorts core is MIT, with copyright notice retained in `licenses/openshorts-MIT.txt`. Its root `NOTICE` explicitly excludes `cloud/`, whose commercial license restricts offering it to third parties as a hosted service. This integration uses independently adapted core techniques; it imports no cloud implementation, proprietary assets, API keys, font binaries or third-party model weights.
