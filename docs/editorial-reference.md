# Editorial reference integration

User-supplied reference, read 5 November 2026: [Elser AI's short-video prompt article](https://www.elser.ai/blog/25-viral-short-video-prompts-for-ai-creators-hooks-scenes-and-workflows-that-actually-work), dated 5 August 2026.

The editing director now uses an original, task-specific creative brief in `cutroom/editorial.py`: choose an appropriate narrative structure, make the opening immediately legible, retain an earned ending, compose for a phone, and place restrained emphasis around real events. The visual critic checks the same editorial goals against actual rendered frames. This updates inference instructions; no weights were trained.

The article primarily discusses generating scenes. Cutroom edits existing recordings, so scene invention, synthetic character transformations, product promotion, and mandatory looping were not adopted. There is no Elser integration, account requirement, paid API, or copied prompt collection. No claim in the article is treated as evidence that a clip will achieve particular views.

The director can specify fit/crop framing and a bounded focus region separately on each source span. A wide establishing shot therefore does not force every reaction close-up into a small landscape strip. Wide-action fallback and the critic's lost-action checks remain active. An explicit project-wide framing choice takes precedence over shot overrides; the fit-frame correction clears them.

Your preview feedback also guides this change: stronger visible editing, closer portrait presentation, readable captions, and effects with a narrative purpose. Full real-video acceptance and human viewing are still required to judge whether the resulting choices are good.
