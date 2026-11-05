"""Idempotent setup; all caches and runtimes live inside this application."""
import json
import os
from pathlib import Path
import subprocess

from . import local_models, runtime


def run_setup(root, log):
    root = Path(root)
    data = root / 'data'
    data.mkdir(exist_ok=True)
    env = dict(os.environ, HF_HOME=str(data/'models/huggingface'),HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false',
               MPLCONFIGDIR=str(data/'cache/matplotlib'))
    def run(args):
        with subprocess.Popen(args, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                if line.strip():
                    log(line.strip()[-500:])
            if process.wait():
                raise RuntimeError('Setup stopped at '+Path(args[0]).name+'. Retry to resume downloaded files.')
    missing = [name for name in ('ffmpeg','ffprobe','whisper-cli','yt-dlp','ollama') if not local_models.binary(name)]
    if missing:
        raise RuntimeError('Run Install.command first. Missing: '+', '.join(missing))
    local_models.start_server(data)
    python = data/'venv/bin/python'
    marker = data/'environment-v2.json'
    if not marker.exists():
        uv = local_models.binary('uv')
        if not uv:
            raise RuntimeError('uv is missing. Run Install.command to install the project-local Python environment.')
        if not python.exists():
            log('Creating the local Python 3.12 environment.')
            run([uv,'venv','--python','3.12',str(data/'venv')])
        log('Installing local analysis and alignment packages. Interrupted downloads can resume.')
        requirements=root/'requirements-v2.lock.txt'
        if not requirements.exists():
            requirements=root/'requirements-v2.txt'
        run([uv,'pip','install','--python',str(python),'-r',str(requirements)])
        run([str(python),'-c','import numpy,PIL,torch,torchaudio,transformers,whisperx,scenedetect'])
        runtime.atomic_json(marker,{'python':str(python),'version':2})
    binary = data/'bin/vision-probe'
    swift = root/'native/VisionProbe.swift'
    if not binary.exists() or binary.stat().st_mtime < swift.stat().st_mtime:
        log('Compiling the macOS Vision face and text helper.')
        binary.parent.mkdir(exist_ok=True)
        run(['/usr/bin/swiftc',str(swift),'-O','-module-cache-path',str(data/'cache/swift'),'-o',str(binary)])
    needed={runtime.DIRECTORS[0],runtime.VISION_MODEL}-set(local_models.model_names())
    if needed or not (data/'models/ggml-large-v3-turbo.bin').exists():
        log('Downloading the quality models. This does not load them into memory.')
        run([str(python),'-m','cutroom.downloads'])
        status=json.loads((data/'bootstrap-v2.json').read_text())
        if status.get('errors'):
            raise RuntimeError('; '.join(status['errors']))
    log('Preparing the local audio-event classifier.')
    run([str(python),'-m','cutroom.analysis_worker','prepare-audio','--cache',str(data/'models/huggingface')])
    runtime.atomic_json(data/'audio-model-ready.json',{'model':'MIT/ast-finetuned-audioset-10-10-0.4593'})
    log('Preparing the resumable English speech-alignment model and tokenizer.')
    run([str(python),'-m','cutroom.analysis_worker','prepare-align','--cache',str(data/'models/huggingface')])
    log('Setup complete. The director will be calibrated on real footage before its first quality run.')
