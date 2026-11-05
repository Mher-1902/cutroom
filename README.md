# Cutroom v2

A personal Mac studio for turning a YouTube link or uploaded video into up to ten reviewed vertical shorts. New clips are **61–120 seconds** by default and must exceed 60 seconds at export. A shorter or weaker source can produce fewer qualifying clips. The Bordeaux/cream interface uses locally bundled Fraunces and Instrument Sans.

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

For a new installation, first run **Install.command**. It installs free Homebrew tools: `ffmpeg-full`, `whisper-cpp`, `yt-dlp`, `ollama`, and `uv`. Homebrew and Apple’s Command Line Tools must be available. Open **Inside the engine → Finish local setup** to create the app-local Python 3.12 environment, compile the macOS Vision helper and download free models. The tested dependency versions are in `requirements-v2.lock.txt`.

Model downloads are large: retaining the legacy model and every tested larger profile uses roughly 50 GiB. Models, Python packages, source caches and projects stay in this app’s `data/` directory. Installation/model acquisition requires internet; inference uses an isolated loopback Ollama endpoint at `127.0.0.1:11439`, with cloud execution disabled. The normal Ollama service on port 11434 is not used.

Paste a link, optionally describe the desired audience or pacing, then choose **Create 10 shorts**. **Make it yours** contains count, duration, framing, captions, soundtrack, source provenance, watermark/credit and other settings. A timestamp in a URL is an attention hint; the full source is still analyzed. Uploading an accessible original file is the fallback for restricted sources. Browser cookies are used only when you explicitly enable a supported local browser session for that import.

## Models and calibration

- **Speech:** Whisper large-v3-turbo through whisper.cpp.
- **Visual indexing and draft inspection:** local Qwen3.5 9B Q4_K_M.
- **Director and story critic:** test Qwen3.5 27B Q4_K_M, then Q3_K_M; use Qwen3 14B if both larger quantizations fail.
- **Alignment:** local WhisperX forced alignment on selected excerpts, with clearly logged fallback to Whisper timing when unavailable.
- **Other evidence:** native macOS Vision faces/OCR, local AudioSet AST sound-event classification, and PySceneDetect boundaries.

A download alone never verifies a profile. Calibration runs sustained real-source structured-output requests for at least ten minutes and records process memory, system pressure, swap growth, Metal allocation and inference timings. The gates are process RSS below 19 GiB, no critical pressure, less than 1 GiB additional swap, valid structured output and verified GPU use. Failed fit trials are preserved; interrupted tests can be retried. No automatic fallback to the legacy 4B model is permitted.

The runtime benchmark chooses from explicit source-window IDs, avoiding invented benchmark timestamps. This verifies fit and structured response handling; it is not proof of editorial judgment. Actual selection and edit plans have separate boundary, duration and source-context validation. Calibration details are visible in **Inside the engine**, and saved in `data/models/profile-v2.json`.

## Editing workflow

1. Import the original-language audio and video, transcribe speech, and map the complete timeline. Inspect one source frame per second in timestamped sequences; use denser four-frame-per-second sequences around candidate reveals and reactions.
2. Combine visual observations, speech, scene changes, faces/text and sound cues. Find up to forty distinct candidate events across the full video, with enough context for a complete challenge, reaction or gameplay beat. Exclude sponsor material and repeated outcomes.
3. Direct a validated edit: chronological source sections, optional replay/freeze beats, framing, timed punch-ins, captions, hook/callouts, music mood and SFX. Maintain source-to-output mapping through cuts, speed changes and replays.
4. Render a draft. Inspect image sequences, actual mapped speech and audio/technical measurements with the vision critic and a separate story-critic request. Revise specific weaknesses, allowing two automatic revision rounds.
5. Export only clips scoring at least 70/100 and passing technical checks. Backfill from the remaining candidate pool until ten qualify or the pool is exhausted. Scores describe editorial potential, not probabilities of virality or predicted views.

The director and story critic are separate requests using the selected director weights; they are not statistically independent judges. Visual critique uses the separate 9B model. Models can misread footage, captions and context. Human viewing remains necessary before publishing.

Framing supports subject-aware crops, an actual gameplay/facecam split and a full-frame blurred-backdrop fallback. Cropping falls back when it would lose wide action. Existing readable source captions are detected with visual/OCR evidence so generated speech captions can be suppressed during overlap. Captions use bundled Barlow Condensed and Anton. Source-language coverage depends on transcription, alignment and available font glyphs; the app does not translate dialogue.

Finishing uses locally bundled CC0 music and sound effects, speech normalization, music ducking, a final limiter and measured true-peak checks. The local catalog records source URLs, SHA-256 hashes and licenses. It covers action, tension, comedy and relaxed moods. A watermark or credit can be positioned in any corner with adjustable opacity; it is a branding/attribution feature and conveys no rights or monetization approval.

## Results, recovery and history

Each project shows real stages and an editing journal. Qualified clips have playable previews, critic explanations, scores, individual MP4/SRT/ASS downloads and optional refinement notes. Refinement retains previous exports; a failed revision does not replace the last qualified clip. New generations have separate files and review records.

The collection ZIP contains MP4s, covers, subtitles, editable captions, suggested post text, edit plans, the critic/technical report and finishing-asset license information. Detailed source index, candidate decisions, rejected drafts and model timings remain in the project folder for inspection. All this is local; nothing posts automatically to social accounts.

Audio extraction and MP4 renders are committed atomically. Interrupted outputs do not count as finished checkpoints. Model downloads retain completed ranges. Cancellation saves completed work; after closing or restarting the app, use **Your projects → Resume run**. Previous v1 projects remain readable and keep their existing files and settings.

## Originality, rights and creator payouts

Cutting another creator’s footage and adding captions, music, effects or a watermark does not automatically make it original or payout-eligible. Source provenance is a declaration, not verification. No local model can certify ownership, fair use, account eligibility or a platform’s payout decision.

Use footage/audio you are entitled to publish and monetize. Substantive original commentary or analysis may meet some platforms’ reused-content standards, but rights clearance and program eligibility remain separate. A CC0 finishing track does not clear music already embedded in the source. Videos over one minute with a Content ID claim face specific YouTube Shorts restrictions. The supplied MrBeast/Kai/GTA links are reference tests, not certified monetizable outputs.

A [source-backed platform review for a Latvian resident](docs/platform-monetization-latvia.md) distinguishes YouTube ad sharing, TikTok Creator Rewards, Instagram Gifts, Facebook Content Monetization and Snapchat’s program, including country restrictions. Rules were checked on 5 November 2026; check account dashboards and current terms before relying on income.

## Verification

The Mac is an Apple M5 with 10 CPU cores, 10 GPU cores and 24 GiB unified memory. The 27B Q4 and Q3 fit tests exceeded the additional-swap gate; their failures are retained. Qwen3 14.8B Q4_K_M passed a 624.4-second sustained test with 22 valid responses, 8.39 GiB peak process RSS, Metal acceleration and no additional swap. The complete real-footage acceptance run must still finish before v2 is described as ready. See the live model profile and `VERIFICATION.md` for the measured status.

The previous v1 pipeline passed a synthetic narration demonstration. That result does not validate the new multimodal pipeline. Current v2 unit checks cover time mapping, replays, speed changes, context trimming, source-caption overlap, source authentication consent, original audio choice, truncated-audio recovery, repeated refinement generations and watermark escaping. Real FFmpeg graph smoke checks exercised all layouts, music/ducking, SFX, freezes, replays and zooms.

For a 20–30-minute source on this Mac, budget a provisional **4–8 hours** at the current quality settings. This is an estimate from individual stage measurements, not a measured end-to-end average. Full visual indexing alone takes approximately 1½–2 hours for 22 minutes. Candidate count and revision rounds can increase the total; checkpoints can reduce repeated work. A real 72.1-second renderer preview passed technical checks, but was manually selected and is not evidence of completed autonomous selection.

Fine-tuning preparation is available in [training/README.md](training/README.md) and the [proposal](docs/fine-tuning.md). No adapter has been trained and no quality improvement is claimed.

```sh
data/venv/bin/python app.py --no-browser
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Do not delete or move project/model folders while a run is active. Media, uncompressed WAVs, frame sequences, draft versions and archives can occupy substantial disk space. No data is automatically deleted. The local HTTP server checks request host, origin and a per-session mutation token; media paths are allowlisted. This is a single-user local application.
