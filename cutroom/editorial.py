"""Original editorial instructions adapted to editing existing source footage.

Reference and scope: docs/editorial-reference.md. This is prompt guidance,
not a trained adapter or a claim about future reach.
"""

DIRECTOR_GUIDE = """SHORT-FORM CREATIVE BRIEF:
Every short needs a truthful curiosity gap: its opening should make the viewer
wonder one specific question. Reveal evidence and partial answers as the real
event unfolds, then answer that question with the retained payoff before ending.
The question may be implicit in action, stakes or dialogue; a literal question
on screen is optional. In the edit reason, state what viewers will wonder and
which retained moment answers it. Do not invent stakes, promise an unseen result,
withhold essential context, or add filler merely to delay the answer.
Choose a structure supported by the source: a challenge with an outcome, a reveal
with its real reaction, a clear change over time, or an emotional turning point.
For each candidate, consider three truthful opening approaches internally: stakes,
curiosity about an observable detail, and a real emotional reaction. Choose the
clearest one; do not export repeated versions as distinct clips.
Make the first two output seconds understandable: show the subject and the reason
to care, with a brief source-language hook only when it adds useful context.
Plan the ending before adding effects. The opening's promise must be answered by
an outcome actually retained in the edit. Preserve suspense that earns that outcome.
Use portrait composition deliberately. Prefer subject-filling crops for isolated
people, objects, and reactions when evidence supports them. Use optional layout
and focus on individual spans to alternate portrait close-ups with wide shots
that preserve essential action. Do not shrink an entire clip just because one
shot needs a wide view; never crop away a participant, important text, or the payoff.
Time a few readable graphics, short camera accents and sound effects to actual
story beats. Leave visual breathing room and keep expressions and action visible.
Match sound mood to the scene and keep speech dominant. Do not claim beat detection.
A natural ending can invite rewatching; never add filler loops to reach a duration target.
Use only the footage and licensed finishing assets available to this editor.
Do not generate new scenes, impersonate people, invent transformations, add an
advertising CTA, or imply that editing establishes originality or monetization.
Summarize the chosen structure, opening and payoff in the edit reason.
"""

CRITIC_GUIDE = """Check whether the first two seconds communicate a concrete subject
and premise, and make the viewer wonder a specific, source-grounded question. Verify that
the retained sequence develops the answer and actually delivers it before the
clip ends. Flag an opening whose promised answer is missing or contradicted;
do not reward empty clickbait or forced question text.
Check that the retained ending answers the hook honestly. Flag tiny
source pictures inside excessive empty backdrop when a safe closer view exists,
as well as crops that hide action. Evaluate text against faces, source text and
the edges of a phone screen. Effects should emphasize real beats and preserve
emotional timing; do not reward effect count or demand fabricated scenes. Give
timestamped corrections, not a prediction of views.
"""

STYLE_GUIDE = """ADAPT THE EDIT TO THIS PARTICULAR VIDEO AND EVENT:
First classify the event from its speech and visual evidence, then choose and
record an editing_strategy. The source may contain several formats; classify
the candidate itself rather than forcing the whole source into one genre.
Challenge: make the rules/stakes legible, preserve the attempt's suspense,
build tension sparingly and clearly show the outcome. Do not rush a risky step.
Reaction/comedy: retain the reveal and authentic response, preserve a comic
pause when it matters, use reaction close-ups and occasional playful accents.
Gameplay: keep the objective, escalation and payoff visible. Protect gameplay,
HUD and spatial context; use a facecam layout only when the footage has one.
Conversation/interview: preserve the speaker's point and context, make clean
sentence cuts, use readable restrained captions and little or no SFX/music.
Tutorial: preserve the steps and visible evidence of the result, keep labels
and demonstrations readable, and remove repetition without skipping a step.
Story/documentary: establish necessary context and retain the turning point
and resolution; let emotional moments breathe instead of adding comic effects.
Mixed/unclear creator footage: state what the evidence supports and choose
restrained treatment where uncertain. No mandatory zoom, replay or sound effect.
Decide pacing, caption treatment, music mood, shot framing and effect density
from that event. Fast is not always entertaining. The approved portrait preview
is a visual reference for suitable entertainment clips, not a universal template.
Respect explicit caption, soundtrack and framing settings over automatic choices.
"""
