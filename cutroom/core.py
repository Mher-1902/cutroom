"""Validation, clip selection, and subtitle timelines. No network or side effects."""
import math
import re
from urllib.parse import urlparse

CRITERIA = {"hook": 0.25, "clarity": 0.20, "payoff": 0.25, "emotion": 0.15, "shareability": 0.15}


def youtube_url(value):
    value = str(value).strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"
    } or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Paste an https://youtube.com or https://youtu.be video link.")
    return value


def settings(raw):
    count = int(raw.get("count", 10))
    low, high = float(raw.get("min_duration", 61)), float(raw.get("max_duration", 120))
    if not 1 <= count <= 10 or not 15 <= low <= high <= 180:
        raise ValueError("Choose 1–10 clips and a duration between 15 and 180 seconds.")
    result = {
        "count": count, "min_duration": low, "max_duration": high,
        "brief": str(raw.get("brief", ""))[:2500],
        "style": raw.get("style", "auto"), "layout": raw.get("layout", "auto"),
        "music": raw.get("music", "auto"), "sfx": bool(raw.get("sfx", True)),
        "language": str(raw.get("language", "auto")),
        "model": str(raw.get("model", "qwen3:4b")),
        "judge_model": str(raw.get("judge_model", raw.get("model", "qwen3:4b"))),
        "resolution": int(raw.get("resolution", 1080)),
        "min_score": int(raw.get("min_score", 70)),
        "watermark_text": str(raw.get("watermark_text", "")).strip()[:64],
        "watermark_position": raw.get("watermark_position", "top-right"),
        "watermark_opacity": float(raw.get("watermark_opacity", .20)),
    }
    if result["style"] not in {"auto", "kinetic", "clean", "none"} or result["layout"] not in {"auto", "fit", "crop", "split"}:
        raise ValueError("Unknown caption style or layout.")
    if result["music"] not in {"auto", "ambient", "none", "upload"} or result["resolution"] not in {720, 1080}:
        raise ValueError("Unknown soundtrack or resolution.")
    if not 0 <= result["min_score"] <= 100:
        raise ValueError("Minimum editorial score must be between 0 and 100.")
    if result["watermark_position"] not in {"top-left","top-right","bottom-left","bottom-right"} or not .10 <= result["watermark_opacity"] <= .65:
        raise ValueError("Choose a valid watermark position and opacity between 10% and 65%.")
    if any(ord(c)<32 for c in result["watermark_text"]):
        raise ValueError("Keep the watermark on one line.")
    if not re.fullmatch(r"auto|[a-z]{2,3}", result["language"]):
        raise ValueError("Language must be auto or a two/three-letter language code.")
    for key in ("model", "judge_model"):
        if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,160}", result[key]) or "cloud" in result[key].lower():
            raise ValueError("Select a downloaded local model.")
    return result


def parse_whisper(payload):
    """whisper.cpp full JSON uses integer millisecond offsets."""
    segments = []
    for item in payload.get("transcription", []):
        offsets = item.get("offsets", {})
        start, end = offsets.get("from", 0) / 1000, offsets.get("to", 0) / 1000
        text = str(item.get("text", "")).strip()
        if not text or text.startswith("[_") or end <= start:
            continue
        words = []
        for token in item.get("tokens", []):
            token_text = str(token.get("text", ""))
            if not token_text.strip() or token_text.startswith("[_") or token.get("id", 0) >= 50256:
                continue
            off = token.get("offsets", {})
            a, b = off.get("from", -1) / 1000, off.get("to", -1) / 1000
            if a >= 0 and b > a:
                if words and not token_text.startswith(" "):
                    words[-1]["text"] += token_text
                    words[-1]["end"] = b
                else:
                    words.append({"start": a, "end": b, "text": token_text.strip()})
        segments.append({"id": len(segments), "start": start, "end": end, "text": text, "words": words})
    return segments


def transcript_chunks(segments, seconds=480, overlap=150):
    """Bound model context while allowing a 120s idea to cross a chunk boundary."""
    if not segments:
        return []
    chunks, cursor = [], 0.0
    last = segments[-1]["end"]
    while cursor < last:
        chunk = [s for s in segments if s["end"] > cursor and s["start"] < cursor + seconds]
        if chunk:
            chunks.append(chunk)
        if cursor + seconds >= last:
            break
        cursor += seconds - overlap
    return chunks


def validate_candidate(raw, segments, low, high):
    """The model chooses segment IDs, never untrusted invented timecodes."""
    try:
        if type(raw["start_id"]) is not int or type(raw["end_id"]) is not int:
            return None
        a, b = raw["start_id"], raw["end_id"]
        if a < 0 or b < a or b >= len(segments):
            return None
        start, end = segments[a]["start"], segments[b]["end"]
        if not low - 0.05 <= end - start <= high + 0.05:
            return None
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    return {
        "start_id": a, "end_id": b, "start": start, "end": end,
        "title": str(raw.get("title", "Untitled moment"))[:120],
        "reason": str(raw.get("reason", ""))[:600],
        "transcript": " ".join(s["text"] for s in segments[a:b + 1]),
    }


def score_judgment(raw):
    metrics = {}
    for key in CRITERIA:
        if isinstance(raw[key], bool):
            raise ValueError("Judge returned a boolean in place of a score.")
        value = float(raw[key])
        if not math.isfinite(value) or not 1 <= value <= 5:
            raise ValueError("Judge returned an invalid rubric score.")
        metrics[key] = value
    # 1/5 -> 20, 5/5 -> 100. This is a rubric score, not a probability.
    return round(sum(metrics[k] * CRITERIA[k] for k in CRITERIA) * 20), metrics


def overlap_fraction(a, b):
    intersection = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return intersection / max(0.001, min(a["end"] - a["start"], b["end"] - b["start"]))


def choose_clips(candidates, count, min_score=60):
    chosen = []
    for candidate in sorted(candidates, key=lambda c: c["score"], reverse=True):
        if candidate.get("reject") or candidate["score"] < min_score:
            continue
        if any(overlap_fraction(candidate, previous) > 0.2 for previous in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) == count:
            break
    return chosen


def ass_time(seconds):
    centiseconds = max(0, round(seconds * 100))
    hours, centiseconds = divmod(centiseconds, 360000)
    minutes, centiseconds = divmod(centiseconds, 6000)
    secs, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centiseconds:02}"


def ass_escape(text):
    # Strip override controls rather than allowing transcript text to inject ASS.
    return str(text).replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def caption_groups(segments, clip, max_words=4):
    words = []
    for segment in segments:
        if segment["end"] <= clip["start"] or segment["start"] >= clip["end"]:
            continue
        aligned = segment.get("words", [])
        if not aligned:
            # Explicit fallback when the ASR cannot align words; do not fabricate
            # a word-highlighting sequence from even spacing.
            words.append({"start": segment["start"], "end": segment["end"], "text": segment["text"]})
        else:
            words.extend(aligned)
    groups, current = [], []
    for word in words:
        if current and (len(current) >= max_words or word["start"] - current[-1]["end"] > 0.45):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def make_ass(segments, clip, style="kinetic"):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,76,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,85,85,430,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for group in caption_groups(segments, clip):
        start, end = max(0, group[0]["start"] - clip["start"]), min(clip["end"] - clip["start"], group[-1]["end"] - clip["start"])
        if end <= start:
            continue
        if style == "clean":
            text = " ".join(ass_escape(w["text"]) for w in group)
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{{\\fs64\\fad(60,60)}}{text}")
        else:
            for i, word in enumerate(group):
                a = max(start, word["start"] - clip["start"])
                b = min(end, group[i + 1]["start"] - clip["start"]) if i + 1 < len(group) else end
                if b <= a:
                    continue
                text = " ".join(("{\\c&H67F5B9&}" if j == i else "{\\c&HFFFFFF&}") + ass_escape(w["text"]) for j, w in enumerate(group))
                events.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"
