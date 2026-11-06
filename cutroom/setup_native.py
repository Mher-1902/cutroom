"""Pinned vLLM Metal installation, isolated from the analysis/alignment environment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

from . import local_models, runtime, vllm_backend

WHEELS = [
    ("https://github.com/vllm-project/vllm/releases/download/v0.33.0rc3/vllm-0.33.0%2Bcpu-cp38-abi3-macosx_11_0_arm64.whl",
     "74840d3eec2ec097de26c331f803e276b5c7eb235709e624cd9b58ee3cc5b5c8"),
    ("https://github.com/vllm-project/vllm-metal/releases/download/v0.33.0/vllm_metal-0.33.0-cp312-cp312-macosx_15_0_arm64.whl",
     "fcf2224250976412a3a8304ec6f48525060f6d30a38c1afad0a97844e03c8dd0"),
]


def install(root, log):
    root = Path(root).resolve()
    data = root / "data"
    runtime.initialize(data)
    env = dict(os.environ, UV_CACHE_DIR=str(data / "cache/uv"), UV_NO_PROGRESS="1",
               HF_HOME=str(data / "models/huggingface"), HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    def run(args):
        with subprocess.Popen(args, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                if line.strip():
                    log(line.strip()[-500:])
            if process.wait():
                raise RuntimeError("vLLM setup stopped. Retry to resume cached downloads.")
    python = data / "vllm-venv/bin/python"
    uv = local_models.binary("uv")
    if not uv:
        raise RuntimeError("Install uv with Install.command first.")
    if not vllm_backend.installed():
        cache = data / "cache/vllm-install"
        cache.mkdir(parents=True, exist_ok=True)
        wheels = []
        for url, digest in WHEELS:
            target = cache / url.rsplit("/", 1)[1].replace("%2B", "+")
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                log("Downloading the verified " + target.name)
                temporary = target.with_suffix(".partial")
                urllib.request.urlretrieve(url, temporary)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Runtime package failed its published checksum.")
                temporary.replace(target)
            wheels.append(str(target))
        if not python.is_file():
            run([uv, "venv", "--python", str(data / "venv/bin/python"), str(data / "vllm-venv")])
        log("Installing pinned vLLM Metal packages in the separate local environment.")
        run([uv, "pip", "install", "--python", str(python), *wheels])
        with zipfile.ZipFile(wheels[-1]) as wheel:
            requirement = "vllm_metal/requirements-torch.txt"
            if requirement in wheel.namelist():
                torch_pins = cache / "requirements-torch.txt"
                torch_pins.write_bytes(wheel.read(requirement))
                run([uv, "pip", "install", "--python", str(python), "-r", str(torch_pins)])
        versions = json.loads(subprocess.check_output([str(python), "-c",
            "import json,importlib.metadata as m;print(json.dumps({n:m.version(n) for n in ['vllm','vllm-metal','mlx','mlx-lm','mlx-vlm','torch']}))"], env=env, text=True))
        if versions["vllm"].split("+")[0] != "0.33.0" or versions["vllm-metal"] != "0.33.0":
            raise RuntimeError("Installed runtime differs from the verified version pair.")
        runtime.atomic_json(data / "vllm-environment.json", versions)
        frozen = subprocess.check_output([uv, "pip", "freeze", "--python", str(python)], env=env, text=True)
        (data / "vllm-environment.lock.txt").write_text(frozen)
    for model, spec in vllm_backend.MODELS.items():
        if model in vllm_backend.model_names():
            continue
        log("Downloading " + model + ". Completed snapshot files are reused on retry.")
        target = vllm_backend.model_path(model)
        # The analysis environment already supplies the resumable HF client.
        script = ("from huggingface_hub import snapshot_download;"
                  "snapshot_download(repo_id=" + repr(model) + ",revision=" + repr(spec["revision"]) +
                  ",local_dir=" + repr(str(target)) + ",max_workers=4,allow_patterns=" +
                  repr(["*.json", "*.safetensors", "*.txt", "*.model", "*.tiktoken", "*.jinja"]) + ")")
        run([str(data / "venv/bin/python"), "-c", script])
        runtime.atomic_json(target / "cutroom-source.json", {"repo": model, "revision": spec["revision"], "directory": str(target)})
    log("vLLM Metal environment and weights prepared. Calibration still required.")
