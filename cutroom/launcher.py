"""Start and stop the local studio independently of an agent or terminal session."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8765"
DATA = ROOT / "data"


def probe():
    try:
        with urllib.request.urlopen(URL + "/api/ping", timeout=3) as response:
            state = json.load(response)
        if state.get("app") != "Cutroom":
            raise RuntimeError("Port 8765 is being used by another application.")
        if state.get("installation") != hashlib.sha256(str(ROOT).encode()).hexdigest():
            raise RuntimeError("Another Cutroom installation is using port 8765.")
        return state
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"Port 8765 returned HTTP {exc.code}.") from exc
        # Compatibility with a studio opened before the launcher was installed.
        with urllib.request.urlopen(URL + "/api/state", timeout=15) as response:
            state = json.load(response)
        if state.get("version") == 2 and "jobs" in state and "health" in state:
            return {"app": "Cutroom", "legacy_launch": True}
        raise RuntimeError("Port 8765 is being used by another application.")
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def verified_pid(state):
    pid = state.get("pid")
    if not isinstance(pid, int) or pid <= 1:
        raise RuntimeError("This studio was opened before the launcher update. Stop its original terminal once, then use cutroom.command.")
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=True)
    if str(ROOT / "app.py") not in shlex.split(result.stdout.strip()):
        raise RuntimeError("The studio process identity could not be verified; it was not stopped.")
    return pid


def keep_awake(state):
    pid = verified_pid(state)
    # Prevent idle sleep for this process's lifetime; display sleep is allowed.
    subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(pid)], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def installation_idle():
    with open(DATA / 'studio.lock','a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False


def start(open_browser=True, awake=False):
    DATA.mkdir(exist_ok=True)
    with open(DATA / "launcher.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = probe()
        if state is None:
            for _ in range(60):
                if installation_idle():break
                time.sleep(.5)
            else:
                raise RuntimeError('The previous studio is still closing. Retry shortly; saved progress is preserved.')
            python = ROOT / "data/venv/bin/python"
            if not python.is_file():
                python = Path(sys.executable)
            env = dict(os.environ, PYTHONUNBUFFERED="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
            with open(DATA / "studio.log", "ab", buffering=0) as log:
                process = subprocess.Popen([str(python), str(ROOT / "app.py"), "--no-browser"], cwd=ROOT,
                                           env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                           start_new_session=True)
            for _ in range(180):
                if process.poll() is not None:
                    raise RuntimeError(f"Cutroom stopped during startup. Read {DATA / 'studio.log'}")
                state = probe()
                if state:
                    break
                time.sleep(.5)
            else:
                raise RuntimeError(f"Startup is taking longer than expected. Check {DATA / 'studio.log'} before retrying.")
        if awake:
            keep_awake(state)
        print(f"Cutroom is running: {URL}\nYou can close this terminal. Logs: {DATA / 'studio.log'}")
        if open_browser:
            webbrowser.open(URL)


def stop():
    state = probe()
    if state is None:
        print("Cutroom is already stopped.")
        return
    pid = verified_pid(state)
    os.kill(pid, signal.SIGTERM)
    for _ in range(60):
        if probe() is None and installation_idle():
            print("Cutroom stopped. Resume interrupted projects from Your projects after starting again.")
            return
        time.sleep(.5)
    raise RuntimeError("The studio is still closing. Check its log before starting another instance.")


def main():
    parser = argparse.ArgumentParser(description="Manage your local Cutroom studio")
    parser.add_argument("action", nargs="?", choices=["start", "open", "stop", "status", "logs"], default="start")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--keep-awake", action="store_true", help="Prevent idle sleep while the studio runs; use on power")
    args = parser.parse_args()
    try:
        if args.action in {"start", "open"}:
            start(not args.no_browser, args.keep_awake)
        elif args.action == "stop":
            stop()
        elif args.action == "status":
            print(f"Running: {URL}" if probe() else "Cutroom is stopped.")
        else:
            log = DATA / "studio.log"
            if not log.exists():
                print("No background studio log yet.")
            else:
                with open(log, "rb") as source:
                    source.seek(max(0, log.stat().st_size - 20000))
                    print(source.read().decode(errors="replace"))
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
