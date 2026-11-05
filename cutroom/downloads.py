"""Download approved v2 models without loading them. Persistent progress for the UI."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATUS = DATA / "bootstrap-v2.json"
lock = threading.Lock()
state = {"running": True, "models": {}, "events": [], "errors": []}
def report(name, status, **details):
    with lock:
        state["models"][name] = {"status": status, **details}
        state["updated"] = time.time()
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(STATUS)
        print(name, status, flush=True)

def pull(name):
    for attempt in range(3):
        try:
            req = urllib.request.Request("http://127.0.0.1:11439/api/pull", data=json.dumps({"model": name, "stream": True}).encode(), headers={"Content-Type": "application/json"})
            last = None
            with urllib.request.urlopen(req, timeout=7200) as response:
                for line in response:
                    item = json.loads(line)
                    if item.get("error"):
                        raise RuntimeError(item["error"])
                    message = item.get("status", "Downloading")
                    percent = round(item.get("completed", 0) / item["total"] * 100) if item.get("total") else None
                    key = (message, None if percent is None else percent // 10)
                    if key != last:
                        report(name, message + (f" {percent}%" if percent is not None else ""), percent=percent)
                        last = key
            report(name, "downloaded")
            return
        except Exception as exc:
            report(name, "Retrying: " + str(exc)[:200])
            time.sleep(3)
    raise RuntimeError("Could not download " + name)

def whisper():
    name = "ggml-large-v3-turbo.bin"
    target = DATA / "models" / name
    info = json.load(urllib.request.urlopen("https://huggingface.co/api/models/ggerganov/whisper.cpp/tree/main?limit=1000", timeout=60))
    metadata = next(x for x in info if x.get("path") == name)
    size, digest = metadata["size"], metadata["lfs"]["oid"]
    url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/" + name
    if target.exists() and target.stat().st_size == size:
        report(name, "downloaded")
        return
    parts = DATA / "models" / "turbo-download"
    parts.mkdir(exist_ok=True)
    block = 16 * 1024 * 1024
    count = (size + block - 1) // block
    def get(index):
        a, b = index * block, min(size - 1, (index + 1) * block - 1)
        path = parts / f"{index:04}.part"
        if path.exists() and path.stat().st_size == b - a + 1:
            return
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
                with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as out:
                    if r.headers.get("Content-Range") != f"bytes {a}-{b}/{size}":
                        raise ValueError("Incorrect byte range")
                    shutil.copyfileobj(r, out, 1024 * 1024)
                if path.stat().st_size != b - a + 1:
                    raise ValueError("Partial range")
                return
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(get, i) for i in range(count)]
        for done, future in enumerate(as_completed(futures), 1):
            future.result()
            if done % 8 == 0 or done == count:
                report(name, f"Downloading {round(done/count*100)}%", percent=round(done/count*100))
    temporary = target.with_suffix(".part")
    actual = hashlib.sha256()
    with open(temporary, "wb") as out:
        for i in range(count):
            with open(parts / f"{i:04}.part", "rb") as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    actual.update(chunk)
                    out.write(chunk)
    if actual.hexdigest() != digest:
        raise ValueError("Whisper checksum mismatch")
    temporary.replace(target)
    (target.with_suffix(".manifest.json")).write_text(json.dumps({"sha256": digest, "size": size, "url": url}))
    for part in parts.glob("*.part"):
        part.unlink()
    parts.rmdir()
    report(name, "downloaded")

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(pull, name) for name in ["qwen3.5:27b-q4_K_M", "qwen3.5:9b-q4_K_M"]]
        futures.append(pool.submit(whisper))
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                state["errors"].append(str(exc))
                print("ERROR", str(exc), flush=True)
    state["running"] = False
    STATUS.write_text(json.dumps(state, indent=2))
