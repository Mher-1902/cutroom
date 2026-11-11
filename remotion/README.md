# Cutroom Remotion runtime

See [the integration guide](../docs/REMOTION.md) for setup, supported capabilities,
licensing and local skill-library tools. Cutroom generates each editable project
under ignored local job data. Open Remotion Studio on a finished clip is optional.

Run `npm ci` to install pinned dependencies, then `npx tsc --noEmit` for component
checks. `render.mjs` is the trusted renderer called by Cutroom. `loopback.cjs`
keeps its servers on this Mac. Private media and plugin guidance stay out of Git.
