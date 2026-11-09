# Video creation benchmark: Klap and Cutroom

Reviewed 9 November 2026. This is a comparison of public product demonstrations
and documentation, not access to Klap's private code, models or training data.
No source footage was uploaded to Klap. Social posting is outside this project.

## Public features and local implementation

| Creation feature | Cutroom status |
| --- | --- |
| Standalone moment selection | Local transcript + visual scouts, source-bounded event selection and critic revisions. |
| Subject reframing | Native face/OCR regions; crop, full-frame and gameplay/facecam layouts. No dedicated active-speaker diarization or automatic multi-person grid. |
| Animated subtitles | Three bundled presets: Focus, Clean and Punch. Wider type, short phrases, word highlighting or fades; no opaque caption slabs. |
| Editable captions | Per-output word corrections retain measured timing through cuts, speed changes and replays. SRT/ASS are regenerated. |
| Hook titles | Source-grounded AI opening graphics; editable opening title in the saved-clip editor. |
| Style reuse | Browser-local saved font, color, size, casing, word count, position and animation. Choose “My saved style” for a new project. |
| Framing adjustments | Saved-clip full-frame/portrait controls and horizontal crop center. Re-render and inspect the resulting crop. |
| Manual cuts | AI plans and refinement notes exist. A draggable multitrack timeline is not implemented. |
| Silence removal | Director can omit unneeded pauses. No unconditional silence stripper: suspense and action pauses may be intentional. |
| B-roll and translation | No automatic stock/generative B-roll or translated captions. Original source audio/language is retained. |

Sources: [official workflow](https://klap.app/how-it-works),
[style presets](https://docs.klap.app/styling),
[task editing options](https://docs.klap.app/endpoints/tasks),
[existing-video caption/reframe workflow](https://docs.klap.app/usecases/caption-reframe-video).
The portrait showcase on [Klap's homepage](https://klap.app) informed the visual
comparison: broad bold type, brief groups and selective color. The exact fonts,
models and private implementation cannot be established from that demonstration.

## Caption design and fast revision

Focus is the user-approved default: a renamed Montserrat ExtraBold instance,
white words and a green active word, subtle outline/shadow, and natural casing.
Clean uses a renamed Instrument Sans Bold instance and phrase fades. Punch uses
short uppercase groups and a yellow highlight. Derived font names are Cutroom
Sans and Cutroom Studio; sources, OFL licenses and SHA-256 records are bundled.
Existing exports and old projects retain their original treatment.

Open a finished clip's **Style & captions** button. A saved-plan render reuses
the original media and aligned speech, without reloading an LLM. It preserves
prior exports and checks duration, picture dimensions and audio. Changing style
does not silently certify a new visual score: the UI identifies the previous
AI-reviewed score and asks the user to watch the changed export.

The Mac UI test changed the opening title, corrected four subtitle words and
rendered a 79.52-second 1080×1920 MP4. VideoToolbox rendering took **25.67 seconds**;
audio/container checks and packaging add time. Playback, version preservation
and a 15-member ZIP with no corrupt entries were verified. This is a measured
style-only revision, not an end-to-end generation time estimate.
