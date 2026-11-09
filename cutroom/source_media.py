"""Original-language imports with global source caching and explicit local auth."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import shutil
from urllib.parse import parse_qs, urlparse

from .core import youtube_url
from .local_models import binary
from .source_policy import strategy


def normalize_url(url):
    url = youtube_url(url)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    ident = parsed.path.strip("/").split("/")[-1] if parsed.hostname == "youtu.be" else query.get("v", [""])[0]
    if not ident and parsed.path.startswith(("/shorts/", "/live/")):
        ident = parsed.path.strip("/").split("/")[-1]
    if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", ident):
        raise ValueError("Paste a direct YouTube video link.")
    raw_hint = query.get("t", query.get("start", ["0"]))[0]
    if raw_hint.rstrip("s").isdigit():
        hint = float(raw_hint.rstrip("s"))
    else:
        match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", raw_hint)
        hint = sum(int(v or 0) * factor for v, factor in zip(match.groups(), (3600, 60, 1))) if match else 0
    return f"https://www.youtube.com/watch?v={ident}", hint


def auth_arguments(config):
    auth = config.get("youtube_auth") or {}
    if not auth:
        return []
    if auth.get("consent") is not True or auth.get("browser") not in {"chrome", "safari", "firefox", "edge", "brave"}:
        raise ValueError("Browser authentication requires explicit consent and a supported browser.")
    return ["--cookies-from-browser", auth["browser"]]


def import_error(error,config):
    """Distinguish consent, OS access, and YouTube rejection without leaking cookies."""
    lower=str(error).lower()
    auth=config.get('youtube_auth') or {}
    browser=str(auth.get('browser','browser')).capitalize()
    authorized=auth.get('consent') is True
    if authorized and any(term in lower for term in ('operation not permitted','permission denied')) and any(term in lower for term in ('cookies','safari')):
        return f'{browser} authorization was saved, but macOS blocked access to protected browser data. Browser imports need permission for the Cutroom desktop app in System Settings → Privacy & Security → Full Disk Access. This grants broader file access. After enabling it, restart the local studio before retrying. Alternatively, upload an accessible video file. Your authorization checkbox is not the problem.'
    if authorized and any(term in lower for term in ('could not find','no such file')) and 'cookie' in lower:
        return f'No usable cookie file was found for {browser}. Choose the browser where you are signed into YouTube and can play this video, or upload an accessible video file.'
    if authorized and any(term in lower for term in ('keychain','decrypt')):
        return f'macOS could not unlock the selected {browser} session. Choose another explicitly authorized browser session, or upload an accessible video file.'
    if any(term in lower for term in ('confirm your age','sign in','cookies','private video','not a bot')):
        if authorized:
            return f'An authorized {browser} import was attempted, but YouTube did not accept that session for this video. Check that this video plays while signed into that browser, or upload an accessible video file.'
        return 'YouTube requires an authorized session for this video. In Make it yours → Restricted YouTube video?, explicitly enable your signed-in browser session, or upload an accessible video file. No browser cookies were read automatically.'
    return str(error)


def browser_access_preflight(config):
    # yt-dlp's directory walk can hide an OS denial as "database not found".
    # Check directory access only, for the browser explicitly authorized here.
    auth=config.get('youtube_auth') or {}
    if sys.platform!='darwin' or auth.get('consent') is not True or auth.get('browser')!='chrome':return
    folder=Path.home()/'Library/Application Support/Google/Chrome'
    try:
        with os.scandir(folder):pass
    except PermissionError as exc:
        raise RuntimeError(import_error('Permission denied accessing Chrome cookies',config)) from exc
    except FileNotFoundError:
        pass


def select_audio(metadata):
    original = str(metadata.get("language") or "").split("-")[0]
    formats = [f for f in metadata.get("formats", []) if f.get("vcodec") == "none" and f.get("acodec") not in {None, "none"}]
    if not formats:
        return None
    def order(f):
        note = str(f.get("format_note", "")).lower()
        language = str(f.get("language") or "").split("-")[0]
        return ("original" in note, bool(original and language == original), f.get("language_preference") or -10,
                "description" not in note, f.get("abr") or f.get("tbr") or 0)
    return max(formats, key=order)["format_id"]


def import_source(studio, job):
    run = lambda args: studio.run(job, args)
    if "upload_id" in job["source"]:
        return studio.uploaded(job["source"]["upload_id"])
    url, hint = normalize_url(job["source"]["url"])
    job["source"]["attention_hint"] = hint
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    cache = studio.data / "cache" / "sources" / key
    cache.mkdir(parents=True, exist_ok=True)
    record = cache / "source.json"
    if record.exists():
        metadata = json.loads(record.read_text())
        target = cache / metadata["filename"]
        if target.exists():
            studio.update(job, name=metadata["title"], source_metadata=metadata)
            return target
    executable = binary("yt-dlp")
    base = [executable, "--ignore-config", "--no-playlist", "--no-progress", *auth_arguments(job["config"])]
    browser_access_preflight(job['config'])
    try:
        raw = json.loads(run(base + ["--skip-download", "--dump-single-json", "--", url]))
        duration = float(raw.get("duration") or 0)
        processing = strategy(duration)
        if raw.get("is_live"):
            raise ValueError("Choose a completed recording; ongoing live streams are not supported.")
        studio.update(job, processing_strategy=processing)
        if processing['mode']=='long_stream':
            studio.event(job, f"Long-stream mode enabled automatically: {processing['scout_count']} half-hour scout tasks, sharing one model sequentially.")
        audio = select_audio(raw)
        selector = f"bv[height<=1080]+{audio}/b[height<=1080]" if audio else "bv[height<=1080]+ba/b[height<=1080]"
        studio.event(job, "Downloading the original-language video and audio tracks.")
        free = shutil.disk_usage(cache).free
        reserve = 4 * 1024 ** 3
        if free <= reserve:
            raise ValueError('Free at least 4 GB of working space before importing a video.')
        budget = min(64 * 1024 ** 3, free-reserve)
        run(base + ["--max-filesize", str(budget), "-f", selector, "--merge-output-format", "mp4", "-o", str(cache / "source.%(ext)s"), "--", url])
    except RuntimeError as exc:
        raise RuntimeError(import_error(exc,job['config'])) from exc
    files = [p for p in cache.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not files:
        raise RuntimeError("The source was not downloaded.")
    target = files[0]
    metadata = {"filename": target.name, "title": str(raw.get("title", "YouTube project"))[:180],
                "duration": duration, "language": raw.get("language") or "auto", "uploader": raw.get("uploader", ""),
                "url": url, "audio_format": audio}
    record.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    studio.update(job, name=metadata["title"], source_metadata=metadata)
    return target
