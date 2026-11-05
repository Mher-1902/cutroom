"""Original-language imports with global source caching and explicit local auth."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from .core import youtube_url
from .local_models import binary


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
    try:
        raw = json.loads(run(base + ["--skip-download", "--dump-single-json", "--", url]))
        duration = float(raw.get("duration") or 0)
        if not 5 < duration <= 7200 or raw.get("is_live"):
            raise ValueError("Choose a completed video up to two hours long.")
        audio = select_audio(raw)
        selector = f"bv[height<=1080]+{audio}/b[height<=1080]" if audio else "bv[height<=1080]+ba/b[height<=1080]"
        studio.event(job, "Downloading the original-language video and audio tracks.")
        run(base + ["--max-filesize", "4G", "-f", selector, "--merge-output-format", "mp4", "-o", str(cache / "source.%(ext)s"), "--", url])
    except RuntimeError as exc:
        error = str(exc)
        if any(term in error.lower() for term in ("confirm your age", "sign in", "cookies", "private video", "not a bot")):
            raise RuntimeError("YouTube requires an authorized session for this video. In Advanced settings, explicitly enable your local browser session, or upload an accessible original file. No browser cookies were read automatically.") from exc
        raise
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
