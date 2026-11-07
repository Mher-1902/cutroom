'use strict';
const CutroomProjectStatus = (() => {
  function describe(job, jobs, health) {
    const active = jobs.find(item => item.status === 'running' && item.id !== job.id);
    if (job.status === 'queued') return {
      stage: 'Queued', progressLabel: 'Queued',
      detail: active ? `Waiting for “${active.name}” to finish. Its current stage: ${active.stage}. Your project has not started yet.` : 'Your project is queued. It will start when the worker is available.'
    };
    if (job.status === 'running' && health.gpu_waiting) return {
      stage: 'Waiting for available model memory', progressLabel: 'Waiting',
      detail: 'Another local model server is still loaded. Progress is saved; processing continues when it closes. Stop & save progress cancels the wait.'
    };
    return {stage: job.stage, progressLabel: `${job.progress}%`,
      detail: job.status === 'failed' ? (job.error || 'Processing stopped. Read the editing journal for details.').replace('In Advanced settings,','In Make it yours → Restricted YouTube video?,') : (job.events?.at(-1)?.message || 'Preparing your project…')};
  }
  return {describe};
})();
if (typeof module !== 'undefined') module.exports = CutroomProjectStatus;
