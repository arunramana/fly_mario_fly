/** What this build of the page offers. `npm run build:lite` makes the hosted copy: it talks to the lite server (settings, a run,
 *  a video), so there is no evolution, no downloads, no saved moments and no saving of flies, and only the blank fly to start from.
 *  Everything that depends on it checks it here. */
const LITE = import.meta.env.VITE_LITE === '1'

export const FEATURES = {
  lite: LITE,
  downloads: !LITE,
  evolution: !LITE,
  moments: !LITE,
  saveFly: !LITE,
}

/** The fly presets offered: the lite build has the blank fly only. */
export const LITE_PRESETS = ['blank']
