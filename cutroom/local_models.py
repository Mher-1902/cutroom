"""Local model lifecycle. The only inference endpoint is an owned loopback server."""
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11439"
WHISPER_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
WHISPER_SHA256 = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
_server = None
_server_log = None
_lock = threading.Lock()


def binary(name):
    if name in {"ffmpeg", "ffprobe"}:
        for prefix in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"):
            path = Path(prefix) / name
            if path.is_file():
                return str(path)
    found = shutil.which(name)
    if found:
        return found
    for prefix in ("/opt/homebrew/bin", "/usr/local/bin"):
        path = Path(prefix) / name
        if path.is_file():
            return str(path)
    return None


def request(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode(errors="replace")
        raise RuntimeError("Local model error: " + detail) from exc


def start_server(data):
    global _server, _server_log
    with _lock:
        try:
            request("/api/version", timeout=1)
            return
        except (OSError, RuntimeError):
            pass
        executable = binary("ollama")
        if not executable:
            raise RuntimeError("Ollama is missing. Run Install.command first.")
        data = Path(data)
        (data / "models" / "ollama").mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11439", OLLAMA_MODELS=str(data / "models" / "ollama"),
                   OLLAMA_NO_CLOUD="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1",
                   OLLAMA_FLASH_ATTENTION="1", OLLAMA_KV_CACHE_TYPE="q8_0")
        _server_log = open(data / "ollama.log", "a")
        _server = subprocess.Popen([executable, "serve"], env=env, stdout=_server_log, stderr=subprocess.STDOUT)
        for _ in range(60):
            if _server.poll() is not None:
                raise RuntimeError("Ollama could not start. Check data/ollama.log.")
            time.sleep(0.5)
            try:
                request("/api/version", timeout=1)
                return
            except (OSError, RuntimeError):
                pass
        raise RuntimeError("Local model server did not start in time.")


def stop_server():
    if _server is not None and _server.poll() is None:
        _server.terminate()
        try:
            _server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server.kill()
    if _server_log:
        _server_log.close()


def model_names():
    return [m["name"] for m in request("/api/tags").get("models", [])
            if not m.get("remote_host") and "cloud" not in m["name"].lower()]


@lru_cache(maxsize=4)
def subtitles_supported(executable):
    if not executable:
        return False
    try:
        result = subprocess.run([executable, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10)
        return " subtitles " in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def health(data):
    tools = {name: binary(name) for name in ("ffmpeg", "ffprobe", "whisper-cli", "yt-dlp", "ollama")}
    try:
        models = model_names()
        online = True
    except (OSError, RuntimeError):
        models, online = [], False
    whisper = Path(data) / "models" / "ggml-small.bin"
    captions = subtitles_supported(tools["ffmpeg"])
    return {"tools": {k: bool(v) for k, v in tools.items()}, "online": online, "models": models, "captions": captions,
            "whisper": whisper.is_file() and whisper.stat().st_size > 100_000_000,
            "ready": all(tools.values()) and captions and online and bool(models) and whisper.is_file() and whisper.stat().st_size > 100_000_000,
            "endpoint": OLLAMA_URL, "default_model": "qwen3:4b"}


def setup(data, log):
    state = health(data)
    missing = [k for k, v in state["tools"].items() if not v]
    if missing:
        raise RuntimeError("Missing tools: " + ", ".join(missing) + ". Run Install.command first.")
    start_server(data)
    if "qwen3:4b" not in model_names():
        log("Downloading the free Qwen3 4B model (about 2.5 GB).")
        payload = json.dumps({"model": "qwen3:4b", "stream": True}).encode()
        req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=payload, headers={"Content-Type": "application/json"})
        previous = ""
        with urllib.request.urlopen(req, timeout=7200) as response:
            for line in response:
                event = json.loads(line)
                if event.get("error"):
                    raise RuntimeError(event["error"])
                status = event.get("status", "Downloading")
                if event.get("total"):
                    status += " " + str(round(event.get("completed", 0) / event["total"] * 100) // 10 * 10) + "%"
                if status != previous:
                    log(status)
                    previous = status
    target = Path(data) / "models" / "ggml-small.bin"
    if not target.is_file() or target.stat().st_size < 100_000_000:
        target.parent.mkdir(parents=True, exist_ok=True)
        log("Downloading Whisper small (about 466 MB).")
        download_whisper(target, log)
    log("Local models are ready. All inference stays on this Mac.")


def download_whisper(target, log):
    """Download verified byte ranges concurrently; retain completed ranges to resume."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(WHISPER_URL, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        content_range = response.headers.get("Content-Range", "")
        if response.status != 206 or "/" not in content_range:
            raise RuntimeError("Model host did not support a resumable download. Please retry.")
        total = int(content_range.rsplit("/", 1)[1])
    parts = target.parent / "whisper-download"
    parts.mkdir(exist_ok=True)
    block = 8 * 1024 * 1024
    count = (total + block - 1) // block
    def fetch(index):
        start, end = index * block, min(total - 1, (index + 1) * block - 1)
        part = parts / f"{index:04}.part"
        if part.is_file() and part.stat().st_size == end - start + 1:
            return part
        error = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(WHISPER_URL, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=180) as response:
                    if response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}":
                        raise RuntimeError("Unexpected model download range.")
                    with open(part, "wb") as output:
                        shutil.copyfileobj(response, output, length=1024 * 1024)
                if part.stat().st_size != end - start + 1:
                    raise RuntimeError("Incomplete model download range.")
                return part
            except (OSError, RuntimeError) as exc:
                error = exc
                time.sleep(attempt + 1)
        raise RuntimeError(f"Model download failed: {error}. Setup can resume completed parts.")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, i) for i in range(count)]
        for completed, future in enumerate(as_completed(futures), 1):
            future.result()
            if completed % 5 == 0 or completed == count:
                log(f"Whisper download {round(completed / count * 100)}%")
    temp = target.with_suffix(".part")
    with open(temp, "wb") as output:
        for index in range(count):
            with open(parts / f"{index:04}.part", "rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if temp.stat().st_size != total:
        raise RuntimeError("Incomplete combined model download. Please retry setup.")
    digest = hashlib.sha256()
    with open(temp, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != WHISPER_SHA256:
        for part in parts.glob("*.part"):
            part.unlink()
        temp.unlink(missing_ok=True)
        raise RuntimeError("Whisper download failed its publisher checksum. Please retry setup.")
    temp.replace(target)
    for part in parts.glob("*.part"):
        part.unlink()
    parts.rmdir()


def chat(model, system, prompt, schema, cancelled=lambda: False):
    if model not in model_names():
        raise RuntimeError(f"{model} is not downloaded locally. Open Local models and run setup.")
    if cancelled():
        raise RuntimeError("Cancelled")
    # A transcript is data, never an instruction to the model or a shell command.
    body = {"model": model, "stream": False, "think": False, "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "options": {"temperature": 0.15, "num_ctx": 12288, "num_predict": 4096}, "keep_alive": "10m"}
    result = request("/api/chat", body, timeout=1200)
    if cancelled():
        raise RuntimeError("Cancelled")
    content = result.get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("The local model returned invalid JSON. Try a different model or rerun.") from exc
