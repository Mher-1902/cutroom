#!/usr/bin/env python3
"""Run with python3 app.py. Standard-library local server; no Python packages needed."""
import argparse
import atexit
import fcntl
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
import uuid
import webbrowser

from cutroom.engine import Studio
from cutroom import local_models, runtime

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
STUDIO = None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def json_response(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host", "") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.valid_host():
            self.json_response({"error": "Invalid host"}, 403)
            return
        path = urlparse(self.path).path
        try:
            if path == "/api/ping":
                self.json_response({"app": "Cutroom", "version": 2, "pid": os.getpid(),
                                    "installation": hashlib.sha256(str(ROOT).encode()).hexdigest()})
            elif path == "/api/state":
                self.json_response({"token": TOKEN, "version":2,"health": runtime.health(STUDIO.data),
                                    "setup": STUDIO.setup_state, "jobs": STUDIO.list_jobs()})
            elif path.startswith("/api/jobs/"):
                self.json_response(STUDIO.get(path.split("/")[-1]))
            elif path.startswith("/files/"):
                parts = path.split("/")
                if len(parts) != 4 or not re.fullmatch(r"[a-f0-9]{32}", parts[2]):
                    raise ValueError("File not found")
                name = unquote(parts[3])
                if not re.fullmatch(r"clip-\d{2}\.(mp4|jpg|ass)|c-[a-f0-9]{32}-r\d+-(draft|final)\.(mp4|jpg|srt|ass)|clips\.zip|analysis\.json", name):
                    raise ValueError("File not found")
                self.serve_file(STUDIO.jobs_dir / parts[2] / name, download=parse_qs(urlparse(self.path).query).get("download"))
            else:
                name = "index.html" if path == "/" else path.lstrip("/")
                file = (ROOT / "static" / name).resolve()
                if not file.is_relative_to(ROOT / "static"):
                    raise ValueError("File not found")
                self.serve_file(file)
        except (ValueError, FileNotFoundError):
            self.json_response({"error": "Not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.valid_host() or self.headers.get("X-Cutroom-Token") != TOKEN:
            self.json_response({"error": "Reload the app before making changes."}, 403)
            return
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            self.json_response({"error": "Invalid origin"}, 403)
            return
        try:
            path = urlparse(self.path).path
            if path == "/api/upload":
                self.upload()
                return
            length = int(self.headers.get("Content-Length", 0))
            if length > 20000:
                raise ValueError("Request is too large.")
            raw = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/jobs":
                self.json_response(STUDIO.create(raw), 201)
            elif path == "/api/setup":
                STUDIO.start_setup()
                self.json_response({"ok": True})
            elif path.endswith("/cancel") and path.startswith("/api/jobs/"):
                STUDIO.cancel(path.split("/")[-2])
                self.json_response({"ok": True})
            elif re.fullmatch(r"/api/jobs/[a-f0-9]{32}/resume",path):
                self.json_response(STUDIO.resume(path.split("/")[3]))
            elif re.fullmatch(r"/api/jobs/[a-f0-9]{32}/clips/[a-f0-9]{32}/refine",path):
                parts=path.split("/")
                self.json_response(STUDIO.refine(parts[3],parts[5],raw.get("notes","")))
            else:
                self.json_response({"error": "Not found"}, 404)
        except (ValueError, TypeError, KeyError) as exc:
            self.close_connection = True
            self.json_response({"error": str(exc)}, 400)
        except Exception as exc:
            self.close_connection = True
            self.json_response({"error": str(exc)}, 500)

    def upload(self):
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= 4 * 1024 ** 3:
            raise ValueError("Choose a file smaller than 4 GB.")
        name = parse_qs(urlparse(self.path).query).get("name", ["video.mp4"])[0]
        extension = Path(name).suffix.lower()
        if extension not in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".mp3", ".m4a", ".wav", ".ogg", ".aac"}:
            raise ValueError("Choose a video file or a music track.")
        ident = uuid.uuid4().hex
        target = STUDIO.uploads / (ident + extension)
        try:
            with open(target, "wb") as out:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Upload was interrupted. Try again.")
                    out.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.json_response({"id": ident, "name": name})

    def serve_file(self, path, download=False):
        if not path.is_file():
            raise FileNotFoundError()
        size = path.stat().st_size
        start, end, partial = 0, size - 1, False
        range_header = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        if match and size:
            a, b = match.groups()
            if not a and b:
                start = max(0, size - int(b))
            elif a:
                start = int(a)
                end = min(end, int(b)) if b else end
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(max(0, end - start + 1)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        if path.suffix == ".html":
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(path, "rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    global STUDIO
    parser = argparse.ArgumentParser(description="Cutroom local short-video studio")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Acquire the installation lock and bind before reading/mutating job state.
    # A second launch must never mark the first process's live jobs interrupted.
    (ROOT / "data").mkdir(exist_ok=True)
    instance_lock = open(ROOT / "data" / "studio.lock", "a")
    try:
        fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Cutroom is already running. Open http://127.0.0.1:8765", flush=True)
        instance_lock.close()
        return
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(f"Cannot open port {args.port}: {exc}", flush=True)
        instance_lock.close()
        return
    STUDIO = Studio(ROOT)
    server.daemon_threads = True
    atexit.register(STUDIO.close)
    try:
        runtime.initialize(STUDIO.data)
    except (RuntimeError, OSError) as exc:
        print("Model setup: " + str(exc), flush=True)
    url = f"http://127.0.0.1:{args.port}"
    print("Cutroom is running at " + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    def stop(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosing Cutroom.", flush=True)
    finally:
        server.server_close()
        STUDIO.close()
        instance_lock.close()


if __name__ == "__main__":
    main()
