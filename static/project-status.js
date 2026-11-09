'use strict';
const CutroomProjectStatus = (() => {
  function importMessage(error){
    const text=error||'Processing stopped. Read the editing journal for details.';
    if(text.includes('vLLM reached its output limit')||text.includes('vLLM returned incomplete JSON'))return 'The AI review did not finish. Your source, analysis and rendered drafts are saved. Resume run retries the unfinished step; you do not need to upload the video again.';
    if(text.includes('macOS blocked access'))return 'Your browser authorization was saved. macOS is blocking protected browser data. To use browser imports, enable Cutroom in System Settings → Privacy & Security → Full Disk Access, then restart the local studio and retry. This grants broader file access; uploading a video file avoids that permission.';
    return text.replace('In Advanced settings,','In Make it yours → Restricted YouTube video?,');
  }
  function describe(job, jobs, health) {
    const active = jobs.find(item => item.status === 'running' && item.id !== job.id);
    if (job.status === 'queued') return {
      stage: 'Queued', progressLabel: 'Queued',
      detail: active ? `Waiting for “${active.name}” to finish. Its current stage: ${active.stage}. Your project has not started yet.` : 'Your project is queued. It will start when the worker is available.'
    };
    if (job.status === 'running' && health.gpu_waiting && !job.pending_style) return {
      stage: 'Waiting for available model memory', progressLabel: 'Waiting',
      detail: 'Another local model server is still loaded. Progress is saved; processing continues when it closes. Stop & save progress cancels the wait.'
    };
    if(job.status==='running'&&job.resource_pause)return {
      stage:job.resource_pause,progressLabel:'Cooling / memory pause',
      detail:'Heavy work is paused automatically. Your completed videos and task checkpoints are safe. Processing resumes when your Mac recovers.'
    };
    if (job.status === 'failed') return {
      stage: job.failure_summary?.stage === 'planning' ? 'Edit planning failed' : job.stage,
      progressLabel: 'Stopped', detail: importMessage(job.error)
    };
    return {stage: job.stage, progressLabel: `${job.progress}%`,
      detail: job.status === 'failed' ? importMessage(job.error) : (job.events?.at(-1)?.message || 'Preparing your project…')};
  }
  function scouting(job){
    if(job.processing_strategy?.mode!=='long_stream')return '';
    const total=job.processing_strategy.scout_count,progress=job.scout_progress||{};
    const coverage=progress.total?`${progress.complete}/${total} sections scouted${progress.failed?` · ${progress.failed} need attention`:''}`:`${total} scout tasks queued`;
    return `Long-stream mode · ${coverage} · one heavy task at a time · ${(job.clips||[]).length}/${job.config.count} shorts ready`;
  }
  return {describe,scouting};
})();
if (typeof module !== 'undefined') module.exports = CutroomProjectStatus;
