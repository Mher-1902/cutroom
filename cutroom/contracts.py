"""Versioned, bounded editing records. Model output is data, never executable code."""
from copy import deepcopy
from dataclasses import dataclass
import math
import uuid

VERSION = 2
MOODS = {"action", "tension", "comedy", "relaxed", "none"}
LAYOUTS = {"fit", "crop", "split"}
REVIEW_WEIGHTS = {"hook": .20, "clarity": .15, "payoff": .20, "pacing": .15,
                  "visual_coherence": .10, "caption_readability": .10, "sound_balance": .10}


def number(value, low, high, name):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {name}")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be in {low}–{high}")
    return value


def rect(raw):
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("A region needs x, y, width, height")
    x, y, w, h = [number(v, 0, 1, "region") for v in raw]
    if w <= 0 or h <= 0 or x + w > 1.001 or y + h > 1.001:
        raise ValueError("Region lies outside the frame")
    return [x, y, w, h]


@dataclass
class SceneIndex:
    duration: float
    blocks: list
    audio_events: list
    cuts: list
    language: str = "auto"
    mode: str = "creator"

    def to_dict(self):
        return {"version": VERSION, **self.__dict__}

    def validate(self):
        number(self.duration, 5, 7200, "source duration")
        cursor = 0.0
        for block in self.blocks:
            a = number(block["start"], 0, self.duration, "block start")
            b = number(block["end"], a, self.duration, "block end")
            if a > cursor + 1.1 or b <= a:
                raise ValueError("Scene index has an uncovered interval")
            cursor = max(cursor, b)
        if cursor < self.duration - 1.1:
            raise ValueError("Scene index does not cover the full source")
        return self


@dataclass
class ClipEditPlan:
    data: dict

    @classmethod
    def parse(cls, raw, source_duration, minimum=61, maximum=120, bounds=None):
        raw = deepcopy(raw)
        spans, cursor, mapping = [], 0.0, []
        for item in raw.get("spans", [])[:12]:
            kind = item.get("kind", "normal")
            if kind not in {"normal", "replay", "freeze"}:
                raise ValueError("Unknown source span kind")
            a = number(item["start"], 0, source_duration, "span start")
            b = number(item.get("end", a), a, source_duration, "span end")
            if bounds and (a < bounds[0] - .05 or b > bounds[1] + .05):
                raise ValueError("Edit leaves its verified source event")
            speed = number(item.get("speed", 1), .8, 1.25, "speed")
            duration = number(item.get("duration", .8), .25, 1.5, "freeze duration") if kind == "freeze" else (b - a) / speed
            if duration <= 0 or (kind == "replay" and duration > 4):
                raise ValueError("Empty span or overly long replay")
            previous_normal = [s for s in spans if s["kind"] == "normal"]
            if kind == "normal" and previous_normal and a < max(s["end"] for s in previous_normal) - .01:
                raise ValueError("Normal story sections must retain source order")
            span = {"start": a, "end": b, "kind": kind, "speed": speed, "duration": duration,
                    "out_start": cursor, "out_end": cursor + duration}
            if "layout" in item:
                if item["layout"] not in {"fit", "crop"}:
                    raise ValueError("Shot layout must be fit or crop")
                span["layout"] = item["layout"]
            if "focus" in item:
                span["focus"] = rect(item["focus"])
            spans.append(span)
            mapping.append({k: span[k] for k in ("start", "end", "kind", "speed", "out_start", "out_end")})
            cursor += duration
        if not spans or not any(s["kind"] == "normal" for s in spans):
            raise ValueError("An edit needs original footage")
        number(cursor, minimum - .05, maximum + .05, "finished clip duration")
        normal = [s for s in spans if s["kind"] == "normal"]
        layout = raw.get("layout", "fit")
        if layout not in LAYOUTS:
            raise ValueError("Unsupported layout")
        mood = raw.get("music_mood", "action")
        if mood not in MOODS:
            raise ValueError("Unsupported soundtrack mood")
        overlays = []
        for item in raw.get("overlays", [])[:8]:
            at = number(item["at"], 0, cursor, "overlay time")
            duration = number(item.get("duration", 2), .4, min(5, cursor - at), "overlay duration")
            kind = item.get("kind", "callout")
            if kind not in {"hook", "callout", "label"}:
                raise ValueError("Unsupported overlay kind")
            text = str(item.get("text", "")).strip()[:90]
            if text:
                overlays.append({"at": at, "duration": duration, "kind": kind, "text": text})
        zooms = []
        for item in raw.get("zooms", [])[:8]:
            at = number(item["at"], 0, cursor, "zoom time")
            duration = number(item.get("duration", 1), .3, min(4, cursor - at), "zoom duration")
            zooms.append({"at": at, "duration": duration, "scale": number(item.get("scale", 1.08), 1, 1.18, "zoom scale")})
        sfx = []
        for item in raw.get("sfx", [])[:10]:
            at = number(item["at"], 0, max(0, cursor - .15), "effect time")
            kind = item.get("kind", "impact")
            if kind not in {"impact", "whoosh", "tick"}:
                raise ValueError("Unsupported sound effect")
            sfx.append({"at": at, "kind": kind})
        result = {"version": VERSION, "id": str(raw.get("id") or uuid.uuid4().hex),
                  "title": str(raw.get("title", "Untitled moment"))[:120], "hook": str(raw.get("hook", ""))[:160],
                  "post_caption": str(raw.get("post_caption", ""))[:700], "spans": spans, "mapping": mapping,
                  "duration": cursor, "start": min(s["start"] for s in normal), "end": max(s["end"] for s in normal),
                  "layout": layout, "focus": rect(raw.get("focus", [.1, .05, .8, .9])),
                  "facecam": rect(raw["facecam"]) if raw.get("facecam") else None,
                  "music_mood": mood, "overlays": overlays, "zooms": zooms, "sfx": sfx,
                  "reason": str(raw.get("reason", ""))[:1000]}
        style=raw.get('caption_style','kinetic')
        if style not in {'kinetic','clean','none'}:
            raise ValueError('Unsupported automatic caption style')
        result['caption_style']=style
        if raw.get('editing_strategy'):
            strategy=raw['editing_strategy']
            if strategy.get('content_type') not in {'creator','challenge','reaction','gameplay','conversation','tutorial','story','mixed'} or strategy.get('pacing') not in {'patient','balanced','brisk','varied'}:
                raise ValueError('Unknown editorial strategy')
            result['editing_strategy']={k:str(strategy.get(k,''))[:700] for k in ('content_type','pacing','reason')}
        return cls(result)

    def to_dict(self):
        return deepcopy(self.data)


@dataclass
class DraftReview:
    data: dict

    @classmethod
    def parse(cls, raw, duration):
        metrics = {k: number(raw[k], 1, 5, k) for k in REVIEW_WEIGHTS}
        problems = []
        for item in raw.get("problems", [])[:8]:
            action = item.get("action", "none")
            if action not in {"none", "fit_frame", "move_captions", "less_music", "less_sfx", "less_overlays", "tighten", "more_context"}:
                raise ValueError("Unknown revision action")
            problems.append({"at": number(item.get("at", 0), 0, duration, "review timestamp"),
                             "issue": str(item.get("issue", ""))[:400], "action": action})
        return cls({"version": VERSION, "score": round(sum(metrics[k] * REVIEW_WEIGHTS[k] for k in metrics) * 20),
                    "metrics": metrics, "reason": str(raw.get("reason", ""))[:1500],
                    "weakness": str(raw.get("weakness", ""))[:1000], "reject": bool(raw.get("reject", False)),
                    "problems": problems})

    def to_dict(self):
        return deepcopy(self.data)


def remap_words(segments, plan):
    """Map speech into rendered time, including speed changes and explicit replays."""
    result = []
    for span in plan["spans"]:
        if span["kind"] == "freeze":
            continue
        for segment in segments:
            if segment["end"] <= span["start"] or segment["start"] >= span["end"]:
                continue
            a, b = max(segment["start"], span["start"]), min(segment["end"], span["end"])
            def convert(t):
                return span["out_start"] + (t - span["start"]) / span["speed"]
            words = [{"text": w["text"], "start": convert(max(span["start"], w["start"])),
                      "end": convert(min(span["end"], w["end"]))}
                     for w in segment.get("words", []) if w["end"] > span["start"] and w["start"] < span["end"]]
            if words:
                text = " ".join(w["text"].strip() for w in words).strip()
            elif a <= segment["start"] + .01 and b >= segment["end"] - .01:
                text = segment["text"]
            else:
                # A partial unaligned phrase cannot safely be captioned or judged
                # as if its removed words were still spoken.
                continue
            result.append({"start": convert(a), "end": convert(b), "text": text, "words": words})
    return result
