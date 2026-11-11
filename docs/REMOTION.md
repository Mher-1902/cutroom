# Local Remotion finishing

New projects can use Remotion in **Make it yours → Finishing engine**. Existing
projects retain their original engine and exports. The vLLM Metal model setup
is unchanged.

Cutroom analyzes the source and creates a validated edit plan. FFmpeg prepares
the actual cuts, framing, zooms, freezes/replays and normalized/ducked audio.
A trusted compiler turns the plan and aligned words into authored React layers.
Remotion adds the approved caption presets, animated hook/open-loop/CTA titles,
replay labels and the user's watermark, then renders the MP4. The existing
technical checks, multimodal critique and revision loop inspect that output.
Model-generated JavaScript is never executed.

Install.command installs Node, pinned dependencies and the official local render
browser. Existing installations can run:

```sh
cd remotion
npm ci
node -r ./loopback.cjs ./node_modules/@remotion/cli/remotion-cli.js browser ensure
```

Start Cutroom with `./cutroom.command start --no-browser`, upload a video and
choose Remotion. Generation runs in the background without opening Studio.
On a finished clip, **Open Remotion Studio** prepares an optional editable
timeline without loading an LLM. The link appears once it is ready. Studio's
preview, caption/layer/timeline controls and Render interface operate on that
private project. Reopening it preserves manual source edits.

Manual Studio exports are separate from Cutroom's qualified collection. They
are not automatically scored or imported back. Cutroom refinements regenerate
from the validated edit plan. Subtitle files remain companions; ASS does not
reproduce every React animation.

All Studio and render listeners are forced to 127.0.0.1. No external model API,
cloud renderer or posting service is started. Rendering uses two browser workers
and requests hardware H.264 encoding where supported. Cancellation terminates
the owned render process group. Resume reuses the prepared-media checkpoint;
an interrupted frame render restarts that export. Fingerprints and file sizes
protect completed output, and changed plans invalidate cached critiques.

## Installed plugin library

All 12 installed workflows and their 259 files are copied unchanged, with SHA-256
checksums, into ignored `data/integrations/remotion/skills`. This includes the
router, creation, markup, captions, interactivity, Studio, rendering, SaaS,
multimedia, maps, documentation and upgrades. The skill version is 4.0.534; all
runtime packages are pinned together to compatible 4.0.542.

```sh
python3 scripts/remotion_tools.py status
python3 scripts/remotion_tools.py search 'caption timing'
python3 scripts/remotion_tools.py read remotion-markup/video-editing.md
python3 scripts/remotion_tools.py guide director
python3 scripts/remotion_tools.py import-skills /path/to/installed/remotion/skills
```

The local director receives bounded relevant guidance during edit planning.
The complete corpus is not stuffed into its 8,192-token context. The Codex
plugin remains a host plugin; Qwen uses the adapter and validated tools above.
Library availability does not enable maps, 3D, stock services, package
installation or cloud rendering as automatic director actions.

Remotion remains an external dependency under its own
[license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
The installed plugin corpus is private and is not redistributed in Git. The
unchanged Basic Captions element comes from the
[official source](https://www.remotion.dev/elements/captions/basic-captions/).
Company/SaaS use must satisfy the applicable Remotion license terms.

## Validation scope

A background render of a saved GTA edit produced an 89.984-second 720×1280 MP4
at −15.11 LUFS and −0.72 dBTP, passing technical checks. The first invocation
took 153.4 seconds including browser setup; h264_videotoolbox encoding was
observed. This is a renderer test using saved analysis, not a newly completed
AI production run or a whole-source turnaround promise. Main stays unchanged
until the user has tested a fresh upload and approved the result.

An additional real-media 18-second timeline test exercised cuts, a nonzero
second-scene trim and a replay. Audio correlation against the prepared timeline
measured 0 ms offset in all three scenes. Caption mapping and shared-parent
trimming are covered by the regression checks.
