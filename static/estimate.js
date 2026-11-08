'use strict';
// Planning budget, not a measured end-to-end average. Keep this provenance
// visible until successful complete runs calibrate the replacement runtime.
const CutroomEstimate = (() => {
  function estimate(minutes, count) {
    minutes = Number(minutes); count = Number(count);
    if (!Number.isFinite(minutes) || minutes < 1 || minutes > 720 ||
        !Number.isInteger(count) || count < 1 || count > 10) return null;
    if (minutes > 180) return {mode:'long_stream',scoutCount:Math.ceil(minutes/30),
      heavyConcurrency:1,reviewedClips:count,calibrated:false,basis:'hierarchical-scouting; end-to-end-unmeasured'};
    // Fresh native 9B test: 44.1 seconds for two 60-second source windows.
    // Full selection/edit/review timing is not yet validated. Never present
    // the old engine's multi-hour budget as a current end-to-end measurement.
    return {analysisLow: Math.ceil(minutes * 44.1 / 120 + .4),
            analysisHigh: Math.ceil(minutes * .5 + .5), reviewedClips: count,
            calibrated: false, basis: 'fresh-native-vision-batch; analysis-stage-only'};
  }
  function duration(minutes) {
    const hours = Math.floor(minutes / 60), rest = minutes % 60;
    return hours ? `${hours}h${rest ? ` ${rest}m` : ''}` : `${rest}m`;
  }
  function range(value) {
    if(!value)return 'Enter 1–720 minutes';
    if(value.mode==='long_stream')return `${value.scoutCount} scouts + ${value.reviewedClips} edits · timing uncalibrated`;
    return `${duration(value.analysisLow)}–${duration(value.analysisHigh)} mapping + ${value.reviewedClips} ${value.reviewedClips===1?'edit':'edits'}`;
  }
  return {estimate, duration, range};
})();
if (typeof module !== 'undefined') module.exports = CutroomEstimate;
