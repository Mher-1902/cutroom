"""Pure-data editor schemas, shared with offline training without loading models."""
from .contracts import REVIEW_WEIGHTS
from .post_copy import MAX_CHARACTERS, TONES
from .story_structure import BRIEF_SCHEMA

CANDIDATES_SCHEMA = {"type": "object", "properties": {"clips": {"type": "array", "maxItems":6,"items": {"type": "object", "properties": {
    "start": {"type": "number"}, "end": {"type": "number"}, "title": {"type": "string"},
    "setup": {"type": "string"}, "payoff": {"type": "string"}, "event_key": {"type": "string"},
    "score": {"type": "integer", "minimum": 1, "maximum": 5}, "reason": {"type": "string"}},
    "required": ["start", "end", "title", "setup", "payoff", "event_key", "score", "reason"]}}}, "required": ["clips"]}

RANK_SCHEMA = {"type": "object", "properties": {"ordered_ids": {"type": "array", "items": {"type": "string"}},
    "duplicate_ids": {"type": "array", "items": {"type": "string"}}, "reason": {"type": "string"}},
    "required": ["ordered_ids", "duplicate_ids", "reason"]}

PLAN_SCHEMA = {"type": "object", "properties": {
    "story_brief": BRIEF_SCHEMA,
    "audience_angle":{"type":"string","enum":["visual_wow","stakes","surprise","humor","story","useful_tip","emotional"]},
    "screen_hook": {"type":"object", "properties":{"enabled":{"type":"boolean"},
        "text":{"type":"string","maxLength":75}, "style":{"type":"string","enum":["hype","clean"]},
        "emphasis":{"type":"string","maxLength":18}}, "required":["enabled","text","style"]},
    "caption_style": {"type":"string", "enum":["kinetic","clean","none"]},
    "editing_strategy": {"type":"object", "properties":{
        "content_type":{"type":"string","enum":["creator","challenge","reaction","gameplay","conversation","tutorial","story","mixed"]},
        "pacing":{"type":"string","enum":["patient","balanced","brisk","varied"]},
        "tone":{"type":"string","enum":sorted(TONES)},
        "reason":{"type":"string"}}, "required":["content_type","pacing","reason"]},
    "title": {"type": "string", "minLength":4}, "hook": {"type": "string"}, "post_caption": {"type": "string", "minLength":8, "maxLength": MAX_CHARACTERS}, "reason": {"type": "string"},
    "spans": {"type": "array", "minItems": 1, "maxItems": 12, "items": {"type": "object", "properties": {
        "start": {"type": "number"}, "end": {"type": "number"}, "kind": {"type": "string", "enum": ["normal", "replay", "freeze", "teaser"]},
        "speed": {"type": "number"}, "duration": {"type": "number"},
        "layout": {"type": "string", "enum": ["fit", "crop"]},
        "focus": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}}}, "required": ["start", "end", "kind", "speed", "duration"]}},
    "layout": {"type": "string", "enum": ["fit", "crop", "split"]},
    "focus": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
    "facecam": {"type": "array", "maxItems": 4, "items": {"type": "number"}},
    "music_mood": {"type": "string", "enum": ["action", "tension", "comedy", "relaxed", "none"]},
    "overlays": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
        "at": {"type": "number"}, "duration": {"type": "number"}, "text": {"type": "string"},
        "kind": {"type": "string", "enum": ["hook", "callout", "label"]}}, "required": ["at", "duration", "text", "kind"]}},
    "zooms": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
        "at": {"type": "number"}, "duration": {"type": "number"}, "scale": {"type": "number"}}, "required": ["at", "duration", "scale"]}},
    "sfx": {"type": "array", "maxItems": 10, "items": {"type": "object", "properties": {
        "at": {"type": "number"}, "kind": {"type": "string", "enum": ["impact", "whoosh", "tick"]}}, "required": ["at", "kind"]}},
    }, "required": ["story_brief", "title", "hook", "screen_hook", "audience_angle", "post_caption", "reason", "spans", "layout", "focus", "facecam", "music_mood", "overlays", "zooms", "sfx", "caption_style", "editing_strategy"]}

REVIEW_SCHEMA = {"type": "object", "properties": {
    "structure_passed":{"type":"boolean"},
    **{k: {"type": "integer", "minimum": 1, "maximum": 5} for k in REVIEW_WEIGHTS},
    "reason": {"type": "string", "maxLength": 650}, "weakness": {"type": "string", "maxLength": 300}, "reject": {"type": "boolean"},
    "problems": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
        "at": {"type": "number"}, "issue": {"type": "string", "maxLength": 200}, "action": {"type": "string", "enum": [
            "none", "fit_frame", "move_captions", "less_music", "less_sfx", "less_overlays", "tighten", "more_context"]}},
        "required": ["at", "issue", "action"]}}}, "required": ["structure_passed", *REVIEW_WEIGHTS, "reason", "weakness", "reject", "problems"]}
