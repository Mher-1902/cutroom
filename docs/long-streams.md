# Automatic long-stream editing

Completed sources longer than three hours automatically use hierarchical scouting.
Exactly three hours stays on the standard path. The maximum source length is twelve
hours. The requested number and duration of finished clips remain your choices.

| Recording | Scout tasks | Simultaneous heavy tasks |
| --- | ---: | ---: |
| 3 hours | Standard analysis | 1 project worker |
| 3 hours + 1 second | 7 | 1 |
| 4 hours | 8 | 1 |
| 10 hours | 20 | 1 |
| 12 hours | 24 | 1 |

Scouts are queued tasks sharing Qwen3.5-9B on vLLM Metal, not separate resident
model copies. A Qwen3-14B tournament judge compares their reports in bounded
contexts. Finalists receive detailed source inspection, editing and independent
review. Each clip completes sequentially and becomes playable when qualified.

Discovery uses matching source captions when available. Otherwise Whisper runs
in resumable five-minute sections. Original-audio ASR and forced alignment verify
selected excerpts before final captions. The small CPU-only
[multilingual E5 retrieval helper](https://huggingface.co/intfloat/multilingual-e5-small)
proposes extra inspection windows; it does not decide which clips qualify.
Its first use downloads free weights. If unavailable, scouts use distributed
speech/visual samples and report that fallback in the journal.

Every half-hour receives a sampled overview and proposed event windows. Only
finalists receive dense inspection. Brief events between samples can be missed;
this mode does not claim exhaustive frame-by-frame understanding. Failed scouts
are marked unassessed and can be retried without repeating successful scouts.

## Creator-highlight selection

Automatic selection uses a separate creator-highlight path for completed live
gameplay/reaction streams. Informative guides keep balanced selection. The
advanced **Moment selection** control can override this choice.

The highlight path scans the complete audio timeline with bounded FFmpeg
half-second energy measurements, then proposes bursts distributed across the
recording. Caption cues add proposals. A short-lived AudioSet classifier checks
these excerpts on MPS/CUDA; it has no CPU inference fallback. These are mixed
game/voice recordings, so sound scores propose inspection and never certify a
human reaction. One large generative model is resident at a time.

Up to forty proposals receive visual inspection on demand, before transcription,
editing or rendering. Original-resolution camera crops enlarge the real creator;
the inspector must distinguish that person from scripted game characters. Quiet
dialogue, routine gameplay, menus and technical setup cannot qualify merely
because they make a coherent story. Claimed laughter/screaming must agree with
the corresponding sound evidence. Exceptional gameplay needs a visible unusual
outcome. Source descriptions remain fallible and the final critics independently
check the retained edit.

The verified peak must remain audible in the main timeline, including after
duration repairs and revisions. An initial split framing preserves the camera
reaction when detected. The rendered critic also requires a separate source
entertainment score of at least 4/5; typography, music and a high overall editorial
score cannot compensate for ordinary source footage. This is a taste rubric,
not a predicted view count or a guarantee of exciting results.

Audio sections, classifications and individual verdicts are checkpointed. On
resuming an older project in this mode, previous exports stay accessible under
**Previous selection** and do not count toward the new qualification. Rejected
proposals and concrete reasons remain in the editing report. Detection is
targeted and can still miss moments; it does not watch every source frame.

## Eight-beat story contract

Every newly directed edit includes, in order: **Hook → Lead → Body 1 → Open loop 1
→ Body 2 → Open loop 2 → Body 3 → CTA**. The hook, two questions and CTA receive
timed on-screen graphics. Lead/body descriptions are internal editing intentions,
available in the result's story details and editing report. They are not section
headings stamped over the footage. Both open loops must receive later answers.
Critics can reject a structurally invalid edit even if its numerical score is high.
Existing exports remain unchanged.

The director first chooses a measured source window, then receives only that
window's evidence for its creative brief. Code compiles the retained timing and
effect cue IDs. Source ordering, duration, captions and replays remain validated.
Tone, pacing, caption treatment, framing, music and accents vary per event.
Suggested post copy is normalized and limited to **159 Unicode code points**,
including spaces, hashtags and emoji; it appears on the card and in the ZIP.

## Recovery and resource limits

SQLite checkpoints separate scout, speech-verification and clip tasks. A failed
task retries once, then other candidates continue. Resume reuses completed work.
Partial collections with unfinished tasks expose **Resume unfinished tasks**.
Uploaded files use resumable 8 MiB chunks, with a 64 GiB file limit and disk-space
checks; select the same unchanged file to resume. The server remains loopback-only.
Browser sessions are used only after the existing explicit authorization.

One heavy task runs at a time. CPU helpers and long-mode rendering use bounded
thread counts. A native Foundation helper reads macOS thermal state; serious or
critical heat, critical memory pressure or excess model footprint releases heavy
work and triggers an automatic cooldown. Processing resumes after thirty stable
seconds. This controls workload; it does not guarantee a cold laptop.

Ten-hour completion time is **not calibrated**. Downloads, missing captions,
model acquisition, revisions and cooldowns affect it. The planner displays scout
and edit counts instead of extrapolating a short vision benchmark into a promise.

## Delivery checks

GitHub Actions runs application, media, training-contract and JavaScript tests on
Linux and macOS, plus native helper/desktop compilation on macOS. Successful main
checks publish a source ZIP artifact. Local models, source recordings, renders,
credentials and private reference frames are excluded from that artifact.
No hosted service is deployed or social account posted to by this pipeline.
