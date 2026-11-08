"""Reuse immutable source analysis across edits, never candidate/editor decisions."""
import json
from pathlib import Path
import shutil
import wave

from . import runtime, core
from .contracts import SceneIndex


def fingerprint(source):
    source=Path(source).resolve();stat=source.stat()
    return {'path':str(source),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}


def restore(studio,job,source,metadata,folder):
    identity=fingerprint(source)
    studio.update(job,analysis_source_fingerprint=identity)
    if (folder/'scene-index.json').exists():
        return False
    for previous in sorted(studio.jobs_dir.glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if previous.parent==folder:
            continue
        try:
            old=json.loads(previous.read_text())
            if old.get('status') in {'queued','running'} or old.get('analysis_source_fingerprint')!=identity:
                continue
            if old.get('config',{}).get('language','auto')!=job['config'].get('language','auto'):
                continue
            prior=previous.parent
            index=json.loads((prior/'scene-index.json').read_text())
            marker=json.loads((prior/'transcript-turbo.complete.json').read_text())
            ready=json.loads((prior/'frames/ready.json').read_text())
            if index.get('version')!=2 or abs(index['duration']-metadata['duration'])>.1 or marker.get('settings_version')!=2:
                continue
            SceneIndex(index['duration'],index['blocks'],index['audio_events'],index['cuts']).validate()
            frames=sorted((prior/'frames').glob('frame-*.jpg'))
            if len(frames)<int(metadata['duration'])-2 or ready.get('fps')!=1:
                continue
            required=('speech.wav','transcript-turbo.json','transcript-turbo.complete.json')
            if not all((prior/name).is_file() for name in required):
                continue
            core.parse_whisper(json.loads((prior/'transcript-turbo.json').read_text()))
            with wave.open(str(prior/'speech.wav')) as audio:
                if abs(audio.getnframes()/audio.getframerate()-metadata['duration'])>.5:
                    continue
        except (OSError,ValueError,KeyError,TypeError,wave.Error,EOFError):
            continue
        studio.event(job,'Reusing the saved transcript and full-video scene analysis. Selecting fresh moments and making new edits for this brief.')
        def copy(source,target):
            studio.check_cancel(job['id'])
            temporary=target.with_name(target.name+'.reuse.tmp')
            shutil.copy2(source,temporary)
            temporary.replace(target)
        for name in (*required,'segments.json','transcript-provenance.json','scene-cuts.json','audio-events.json'):
            if (prior/name).is_file():
                copy(prior/name,folder/name)
        directory=folder/'frames';directory.mkdir(exist_ok=True)
        for frame in frames:
            copy(frame,directory/frame.name)
        copy(prior/'frames/ready.json',directory/'ready.json')
        # Install the complete-index marker only after all dependencies exist.
        copy(prior/'scene-index.json',folder/'scene-index.json')
        studio.update(job,analysis_reused_from=old['id'])
        return True
    return False
