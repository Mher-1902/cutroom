"""Owned loopback-only vLLM Metal server, one loaded model at a time.

No Ollama or remote inference fallback. The app-local runtime and model snapshots
must finish installation before this backend can start.
"""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:11440"
MODELS = {
    "mlx-community/Qwen3.5-9B-MLX-4bit": {"folder": "Qwen3.5-9B-MLX-4bit", "vision": True,
        "revision": "938d8919941c6e7efd3c7150eff7fe9d12afa631"},
    "mlx-community/Qwen3-14B-4bit": {"folder": "Qwen3-14B-4bit", "vision": False,
        "revision": "a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4"},
}
DATA = Path(__file__).resolve().parents[1] / "data"
_lock = threading.RLock()
_process = None
_log = None
_model = None
_state = {}
_log_start = 0


class IncompleteResponse(RuntimeError):
    def __init__(self, message, partial='', usage=None):
        super().__init__(message)
        self.partial = partial
        self.usage = usage or {}


def configure(data):
    global DATA
    requested = Path(data).resolve()
    if _process is not None and _process.poll() is None and requested != DATA.resolve():
        raise RuntimeError("Cannot change installation while a model is loaded.")
    DATA = requested


def model_path(model):
    if model not in MODELS:
        raise ValueError("Choose an approved local MLX model.")
    return DATA / "models/vllm" / MODELS[model]["folder"]


def model_names():
    names = []
    for model in MODELS:
        folder = model_path(model)
        marker = folder / "cutroom-source.json"
        try:
            source = json.loads(marker.read_text())
            if source.get("repo") != model or source.get("revision") != MODELS[model]["revision"]:
                continue
            config = json.loads((folder / "config.json").read_text())
            index = folder / "model.safetensors.index.json"
            shards = set(json.loads(index.read_text())["weight_map"].values()) if index.exists() else {"model.safetensors"}
            if config and shards and all(Path(s).name == s and (folder / s).stat().st_size > 1000 for s in shards):
                names.append(model)
        except (OSError, ValueError, KeyError):
            continue
    return names


def installed():
    marker = DATA / "vllm-environment.json"
    try:
        versions = json.loads(marker.read_text())
        return bool((DATA / "vllm-venv/bin/vllm").is_file() and versions.get("vllm", "").split("+")[0] == "0.33.0"
                    and versions.get("vllm-metal") == "0.33.0")
    except (OSError, ValueError):
        return False


def process_id():
    return _process.pid if _process is not None and _process.poll() is None else None


def competing_servers():
    """Observe other model servers; never stop or reconfigure them."""
    import re
    try:
        output=subprocess.check_output(['ps','-axo','pid=,command='],text=True,timeout=5)
    except (OSError,subprocess.SubprocessError):
        return []
    servers=[]
    for line in output.splitlines():
        fields=line.strip().split(None,1)
        if len(fields)!=2:continue
        pid=int(fields[0]);command=fields[1]
        if pid==process_id() or not re.search(r'(?:/vllm\s+serve\s|vllm\.entrypoints\.cli\.main\s+serve\s)',command):continue
        port=re.search(r'--port\s+(\d+)',command)
        servers.append({'pid':pid,'port':int(port[1]) if port else None})
    return servers


def gpu_verified():
    if _process is None or _process.poll() is not None:
        return False
    try:
        with open(DATA / "vllm.log", "rb") as log:
            log.seek(_log_start)
            text = log.read(256 * 1024).decode(errors="replace").lower()
        return any(marker in text for marker in ("mlx device set to: device(gpu", "metalplatform", "platform metal", "using metal", "metal: loaded"))
    except OSError:
        return False


def _record(**fields):
    _state.update(fields, updated=time.time(), endpoint=BASE_URL)
    DATA.mkdir(exist_ok=True, parents=True)
    target = DATA / "vllm-runtime.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(_state, indent=2))
    temporary.replace(target)


def stop():
    global _process, _log, _model, _log_start
    with _lock:
        if _process is not None and _process.poll() is None:
            os.killpg(_process.pid, signal.SIGTERM)
            try:
                _process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(_process.pid, signal.SIGKILL)
                _process.wait(timeout=10)
        if _log is not None:
            _log.close()
        _process = _log = _model = None
        _record(status="idle", model=None, pid=None)


def ensure_model(model, cancelled=lambda: False):
    global _process, _log, _model, _log_start
    with _lock:
        competitors=competing_servers()
        if competitors:
            stop()
            while competitors:
                _record(status='waiting_for_gpu',blocking_servers=competitors,model=model)
                if cancelled():
                    _record(status='idle',blocking_servers=[],model=None)
                    raise RuntimeError('Cancelled')
                time.sleep(2)
                competitors=competing_servers()
        _state.pop('blocking_servers',None)
        if _model == model and _process is not None and _process.poll() is None:
            return
        if not installed() or model not in model_names():
            raise RuntimeError("The vLLM Metal environment or model is not ready. Finish local setup; no Ollama fallback is used.")
        stop()
        # Never take over another user's model server or bind a public interface.
        import socket
        with socket.socket() as test:
            if test.connect_ex(("127.0.0.1", 11440)) == 0:
                raise RuntimeError("Port 11440 is already occupied. The existing process was left untouched.")
        env = dict(os.environ, HF_HOME=str(DATA / "models/huggingface"), HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1",
                   TOKENIZERS_PARALLELISM="false", VLLM_NO_USAGE_STATS="1", VLLM_METAL_BACKEND="mlx",
                   VLLM_METAL_MULTIMODAL_MODE="auto", OMP_NUM_THREADS="2")
        command = [str(DATA / "vllm-venv/bin/vllm"), "serve", str(model_path(model)),
                   "--host", "127.0.0.1", "--port", "11440", "--served-model-name", model,
                   "--max-model-len", "8192", "--max-num-seqs", "2" if MODELS[model]['vision'] else "1",
                   "--max-num-batched-tokens", "2048" if MODELS[model]['vision'] else "256",
                   "--gpu-memory-utilization", "0.68", "--kv-cache-memory-bytes", "805306368" if MODELS[model]['vision'] else "1207959552",
                   "--structured-outputs-config", json.dumps({'backend':'xgrammar','disable_any_whitespace':True}),
                   "--disable-log-requests"]
        if MODELS[model]['vision']:
            command+=['--mm-processor-cache-gb','0']
        if not MODELS[model]['vision']:
            command += ['--additional-config',json.dumps({'turboquant':True,'k_quant':'q8_0','v_quant':'q8_0'})]
        _log = open(DATA / "vllm.log", "ab", buffering=0)
        _log_start = _log.tell()
        _process = subprocess.Popen(command, cwd=DATA.parent, env=env, stdin=subprocess.DEVNULL,
                                    stdout=_log, stderr=_log, start_new_session=True)
        _record(status="loading", model=model, pid=_process.pid, started=time.time())
        started = time.time()
        while time.time() - started < 240:
            if cancelled():
                stop()
                raise RuntimeError("Cancelled")
            if _process.poll() is not None:
                _record(status="failed", error="vLLM stopped during startup. Check data/vllm.log.")
                raise RuntimeError(_state["error"])
            try:
                with urllib.request.urlopen(BASE_URL + "/v1/models", timeout=2) as response:
                    available = json.load(response)
                if any(x.get("id") == model for x in available.get("data", [])):
                    _model = model
                    _record(status="ready", load_seconds=round(time.time() - started, 2))
                    return
            except (OSError, ValueError):
                pass
            time.sleep(.3)
        stop()
        raise RuntimeError("vLLM startup timed out. Check data/vllm.log; no alternative server was used.")


def validate_schema_features(value):
    """Reject a known pinned-backend incompatibility before loading any model."""
    if isinstance(value,dict):
        if value.get('type')=='string' and ('pattern' in value or 'format' in value) and ('minLength' in value or 'maxLength' in value):
            raise ValueError('This vLLM schema must express string length inside its pattern, rather than mixing pattern and length constraints.')
        for item in value.values():validate_schema_features(item)
    elif isinstance(value,list):
        for item in value:validate_schema_features(item)


def payload(model, system, prompt, schema, images, predict):
    validate_schema_features(schema)
    if model not in MODELS:
        raise ValueError("Choose an approved local MLX model.")
    if images and not MODELS[model]["vision"]:
        raise ValueError("Image input needs the vision model.")
    content = [{"type": "text", "text": prompt}]
    for path in images or []:
        data = base64.b64encode(Path(path).read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data}})
    schema = deepcopy(schema)
    def close_objects(value):
        if isinstance(value, dict):
            if value.get('type') == 'object' and 'properties' in value:
                value['additionalProperties'] = False
            for item in value.values():
                close_objects(item)
        elif isinstance(value, list):
            for item in value:
                close_objects(item)
    close_objects(schema)
    return {"model": model, "messages": [{"role": "system", "content": system},
                {"role": "user", "content": content if images else prompt}],
            "stream": True, "stream_options": {"include_usage": True},
            "temperature": .2, "seed": 41, "max_tokens": predict,
            "chat_template_kwargs": {"enable_thinking": False},
            "structured_outputs": {"json": schema, "disable_any_whitespace": True}}


def fit_context(body):
    """Reserve the whole response using the served model's multimodal tokenizer.

    Shrink only analysis-image previews if necessary, retaining every image and
    all source text. Model context, GPU settings and rendered video are untouched.
    """
    def count():
        raw={key:body[key] for key in ('model','messages','chat_template_kwargs')}
        request=urllib.request.Request(BASE_URL+'/tokenize',data=json.dumps(raw).encode(),
                                       headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=120) as response:
            return json.load(response)
    resized=0
    for attempt in range(5):
        measured=count()
        tokens,limit=int(measured['count']),int(measured['max_model_len'])
        if tokens+body['max_tokens']+32<=limit:
            return {'prompt_tokens':tokens,'reserved_output_tokens':body['max_tokens'],
                    'max_model_len':limit,'image_resize_rounds':resized}
        content=body['messages'][1]['content']
        images=[item for item in content if item.get('type')=='image_url'] if isinstance(content,list) else []
        if not images or attempt==4:
            raise RuntimeError(f'The AI evidence packet needs {tokens} input tokens plus {body["max_tokens"]} response tokens; its context limit is {limit}. Source text was preserved.')
        from io import BytesIO
        from PIL import Image
        changed=False
        for item in images:
            url=item['image_url']['url']
            with Image.open(BytesIO(base64.b64decode(url.split(',',1)[1]))) as source:
                size=(max(160,round(source.width*.8)),max(160,round(source.height*.8)))
                if size[0]>=source.width or size[1]>=source.height:continue
                output=BytesIO()
                source.convert('RGB').resize(size,Image.Resampling.LANCZOS).save(output,format='JPEG',quality=88)
            item['image_url']['url']='data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()
            changed=True
        if not changed:
            raise RuntimeError('The AI evidence packet is too large even with bounded analysis images. Source text was preserved.')
        resized+=1


def stream(body, cancelled, register, unregister):
    request = urllib.request.Request(BASE_URL + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(request, timeout=1800)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("vLLM request failed: " + exc.read(2000).decode(errors="replace")) from exc
    pieces, usage, finish = [], {}, None
    with response:
        register(response)
        try:
            for line in response:
                if cancelled():
                    raise RuntimeError("Cancelled")
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    break
                item = json.loads(data)
                if item.get("error"):
                    raise RuntimeError("vLLM generation failed: " + str(item["error"])[:1200])
                for choice in item.get("choices", []):
                    pieces.append(choice.get("delta", {}).get("content") or "")
                    finish = choice.get("finish_reason") or finish
                usage = item.get("usage") or usage
        finally:
            unregister()
    if cancelled():
        raise RuntimeError("Cancelled")
    if finish == "length":
        raise IncompleteResponse("vLLM reached its output limit. The incomplete response was not accepted.", ''.join(pieces), usage)
    if finish != "stop":
        raise RuntimeError("vLLM stream ended without a complete response. Resume this stage to retry.")
    try:
        return json.loads("".join(pieces)), usage
    except ValueError as exc:
        raise IncompleteResponse("vLLM returned incomplete JSON. Resume this stage to retry.", ''.join(pieces), usage) from exc
