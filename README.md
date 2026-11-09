# Cutroom v2

A personal Mac studio for turning a YouTube link or uploaded video into up to ten reviewed vertical shorts. New clips default to **61–120 seconds**. A separate prominent length selector offers **15–29 seconds**, **30–59 seconds**, **60–90 seconds** (also available as a one-click button), and a custom range within **15–180 seconds**. Exports must match the selected range; only a selection above one minute enforces >60 seconds. A shorter or weaker source can produce fewer qualifying clips. The Bordeaux/cream interface uses locally bundled Fraunces and Instrument Sans.

## Run

Double-click **Launch.command**. The studio opens at **http://127.0.0.1:8765** in your browser and runs in the background. You can close the terminal and this chat. Bookmark that address. This is a local website on your Mac; it is not listed in Google search.

From a terminal in this project folder:

```sh
./cutroom.command start                 # Start in background and open browser
./cutroom.command status                # Check whether it is running
./cutroom.command stop                  # Stop; unfinished projects can resume
./cutroom.command logs                  # Show recent background logs
./cutroom.command start --keep-awake    # Also prevent idle sleep while running
```

Use `--keep-awake` on power for long runs. It allows the display to sleep, but does not override closing the laptop lid or manually choosing Sleep. After rebooting, run Start again. See [RUNNING.md](RUNNING.md) for startup, access, and hosting details.

For a new installation, first run **Install.command**. It installs free Homebrew tools: `ffmpeg-full`, `whisper-cpp`, `yt-dlp`, and `uv`. Homebrew and Apple’s Command Line Tools must be available. Open **Inside the engine → Finish local setup** to create the app-local Python 3.12 environment, compile the macOS Vision helper and download free models. The tested analysis dependencies are in `requirements-v2.lock.txt`; the isolated inference installer pins its release wheels and model revisions.

Model downloads are large: retaining the legacy model and every tested larger profile uses roughly 50 GiB. Models, Python packages, source caches and projects stay in this app’s `data/` directory. Installation/model acquisition requires internet; generative inference uses an owned vLLM Metal server at `127.0.0.1:11440`. No Ollama or paid API fallback runs. The analysis environment and the vLLM environment are separate.

Paste a link, optionally describe the desired audience or pacing, then choose **Create 10 shorts**. The prominent count selector chooses 1–10 shorts independently of the clip-length selector. **Make it yours** contains duration, framing, captions, soundtrack, source provenance and other settings. Enter a watermark username in the visible field below clip length before creating shorts; blank disables it. The default is small 28px lettering at 1080 output with 20% opacity and a soft shadow. A timestamp in a URL is an attention hint; the full source is still analyzed. Uploading an accessible original file is the fallback for restricted sources. Browser cookies are used only when you explicitly enable a supported local browser session for that import.

## Models and calibration

- **Speech:** Whisper large-v3-turbo through whisper.cpp.
- **Visual indexing and draft inspection:** native MLX Qwen3.5 9B, four-bit weights, through vLLM Metal.
- **Director and story critic:** native MLX Qwen3 14B, four-bit weights, through vLLM Metal. Earlier 27B Q4/Q3 trials exceeded the additional-swap gate. Their failures remain in the local history.
- **Alignment:** local WhisperX forced alignment on selected excerpts, with clearly logged fallback to Whisper timing when unavailable.
- **Other evidence:** native macOS Vision faces/OCR, local AudioSet AST sound-event classification, and PySceneDetect boundaries.

A download alone never verifies a profile. Calibration runs sustained real-source structured-output requests for at least ten minutes and records process-tree RSS, Darwin physical footprint, system pressure, swap growth, GPU selection and inference timings. Separate GPU allocation is not available from this runtime. The gates are process memory below 19 GiB, no critical pressure, less than 1 GiB additional swap, valid structured output and verified GPU use. Failed fit trials are preserved; interrupted tests can be retried. No automatic fallback to the legacy 4B model is permitted.

The runtime benchmark chooses from explicit source-window IDs, avoiding invented benchmark timestamps. This verifies fit and structured response handling; it is not proof of editorial judgment. Actual selection and edit plans have separate boundary, duration and source-context validation. Calibration details are visible in **Inside the engine**, and saved in `data/models/profile-vllm-v1.json`. The previous-engine profile is retained separately.

## Editing workflow

1. Import the original-language audio and video, transcribe speech, and map the complete timeline. Map the whole source in 60-second broad windows, combining uniform visual samples with scene/sound cues and full speech. Selected candidates receive denser inspection around setup, reveals and reactions. Brief events between samples can still be missed.
2. Combine visual observations, speech, scene changes, faces/text and sound cues. Find up to forty distinct candidate events across the full video, with enough context for a complete challenge, reaction or gameplay beat. Exclude sponsor material and repeated outcomes.
3. The visual co-editor receives an eight-frame source storyboard, two motion strips and an optional private approved style reference. It recommends a measured opening frame, framing and visible details; the 14B text director uses those observations with source dialogue and title context. Reference imagery supplies style, never source facts.
4. Direct a validated edit: chronological source sections, optional replay/freeze beats, framing, timed punch-ins, captions, optional large animated on-screen hooks, detail callouts, music mood and SFX. A muted cold open can introduce a strong source visual without inventing spoken dialogue. Maintain source-to-output mapping through cuts, speed changes and replays.
5. Render a draft. Inspect image sequences, actual mapped speech and audio/technical measurements with the vision critic and a separate story-critic request. Revise specific weaknesses, allowing two automatic revision rounds.
6. Export only clips scoring at least 70/100 and passing technical checks. Backfill from the remaining candidate pool until ten qualify or the pool is exhausted. Scores describe editorial potential, not probabilities of virality or predicted views.

The director and story critic are separate requests using the selected director weights; they are not statistically independent judges. Visual critique uses the separate 9B model. Models can misread footage, captions and context. Human viewing remains necessary before publishing.

Framing supports subject-aware crops, an actual gameplay/facecam split and a full-frame blurred-backdrop fallback. Each source span can choose its own crop or fit treatment, so close-ups can fill the portrait frame while wide shots retain important action. The director and critic use a source-grounded [editorial brief](docs/editorial-reference.md) for clearer openings, earned payoffs, readable text and deliberate effects. Cropping falls back when it would lose wide action. Existing readable source captions are detected with visual/OCR evidence so generated speech captions can be suppressed during overlap. Captions use bundled Barlow Condensed and Anton. Source-language coverage depends on transcription, alignment and available font glyphs; the app does not translate dialogue.

Finishing uses locally bundled CC0 music and sound effects, speech normalization, music ducking, a final limiter and measured true-peak checks. The local catalog records source URLs, SHA-256 hashes and licenses. It covers action, tension, comedy and relaxed moods. A watermark or credit can be positioned in any corner with adjustable opacity; it is a branding/attribution feature and conveys no rights or monetization approval.

## Results, recovery and history

Videos **longer than three hours** automatically switch to half-hour scout tasks:
ten hours uses twenty scouts sharing one model, followed by sequential independent
clip edits. Sources up to twelve hours are accepted. Large uploads resume in chunks.
Every newly directed short follows Hook → Lead → Body 1 → Open loop → Body 2 →
Open loop → Body 3 → CTA, with event-specific tone and finishing. Post captions
stay below 160 characters. See [long-stream behavior and limits](docs/long-streams.md).

Each project shows real stages and an editing journal. Qualified clips have playable previews, critic explanations, scores, individual MP4/SRT/ASS downloads and optional refinement notes. Refinement retains previous exports; a failed revision does not replace the last qualified clip. New generations have separate files and review records.

**Style & captions** changes a saved clip without repeating AI analysis. Choose
Focus (bold/green), Clean (minimal) or Punch (bold/yellow), adjust type/color/size,
correct subtitle words, edit the opening title and change framing. Save a style
locally for reuse. A changed export retains previous versions and receives new
technical checks; its prior AI score is labeled as belonging to the earlier edit.
See the [public Klap feature comparison and measured style revision](docs/creation-benchmark.md).

The collection ZIP contains MP4s, covers, subtitles, editable captions, suggested post text, edit plans, the critic/technical report and finishing-asset license information. Detailed source index, candidate decisions, rejected drafts and model timings remain in the project folder for inspection. All this is local; nothing posts automatically to social accounts.

Audio extraction and MP4 renders are committed atomically. Interrupted outputs do not count as finished checkpoints. Model downloads retain completed ranges. Cancellation saves completed work; after closing or restarting the app, use **Your projects → Resume run**. Previous v1 projects remain readable and keep their existing files and settings.

## Originality, rights and creator payouts

Cutting another creator’s footage and adding captions, music, effects or a watermark does not automatically make it original or payout-eligible. Source provenance is a declaration, not verification. No local model can certify ownership, fair use, account eligibility or a platform’s payout decision.

Use footage/audio you are entitled to publish and monetize. Substantive original commentary or analysis may meet some platforms’ reused-content standards, but rights clearance and program eligibility remain separate. A CC0 finishing track does not clear music already embedded in the source. Videos over one minute with a Content ID claim face specific YouTube Shorts restrictions. The supplied MrBeast/Kai/GTA links are reference tests, not certified monetizable outputs.

A [source-backed platform review for a Latvian resident](docs/platform-monetization-latvia.md) distinguishes YouTube ad sharing, TikTok Creator Rewards, Instagram Gifts, Facebook Content Monetization and Snapchat’s program, including country restrictions. Rules were checked on 5 November 2026; check account dashboards and current terms before relying on income.

## Verification

The Mac is an Apple M5 with 10 CPU cores, 10 GPU cores and 24 GiB unified memory. The current 14B vLLM Metal director passed a 607.9-second sustained test with 28 valid source-window responses, 9.99 GiB peak process-tree physical footprint, verified GPU use and 0.519 GiB additional swap. A fresh two-window 9B vision batch took 44.1 seconds plus 23.9 seconds to load the model, within memory gates. These tests establish runtime behavior, not selection quality.

The approved 71.72-second portrait style preview passed technical checks. The same 1080×1920 edit encoded in 14.4 seconds with VideoToolbox versus 45.9 seconds with libx264; frame comparison averaged 0.9961 SSIM. Hardware encoding activates only with a verified local renderer profile and falls back to CPU if encoding fails.

An automatic GTA run using cached full-source analysis completed with two qualifying clips from three requested in 118 minutes. That earlier run exposed weak copy and costly large planning/review calls; it is not a benchmark of the newer measured-event planner or long-stream scouts. The corrected planner passed a real-reference excerpt test, followed by the user-approved caption revision. Full ten-hour production timing remains unmeasured. The old four-hour analysis projection came from 300 serial 12-second windows per source hour; it is not the current runtime's measured completion time. See [inference measurements](docs/inference-efficiency.md) and [acceptance status](VERIFICATION.md). Under one hour is a target, not a guarantee; downloads, clip count and revision rounds matter.

The previous v1 pipeline passed a synthetic narration demonstration. Current source checks cover timestamp mapping, replays, speed changes, framing, adaptive styles, source captions, imports, checkpointing, launch identity and audio-clock recovery. These checks and manually selected previews are not substitutes for a completed AI production run.

Fine-tuning preparation is available in [training/README.md](training/README.md) and the [proposal](docs/fine-tuning.md). No adapter has been trained and no quality improvement is claimed.

```sh
data/venv/bin/python app.py --no-browser
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Do not delete or move project/model folders while a run is active. Media, uncompressed WAVs, frame sequences, draft versions and archives can occupy substantial disk space. No data is automatically deleted. The local HTTP server checks request host, origin and a per-session mutation token; media paths are allowlisted. This is a single-user local application.

Approved style references stay in `data/style-references/` and are excluded from public Git. New entertainment edits use an energetic social-media brief with content-specific visual, reaction, humor or story angles. Source analysis can be reused for a new brief when source path, size, modification time and language match; candidate choices and edit plans are regenerated. Interrupted AI reviews retry once, preserve their rendered drafts and never qualify an incomplete answer.
