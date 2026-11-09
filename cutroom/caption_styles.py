"""Bundled caption presets and safe styling; no inference or font downloads."""
from copy import deepcopy
import math
from pathlib import Path
import re

from . import core

FONTS = {"sans": "Cutroom Sans", "studio": "Cutroom Studio"}
PRESETS = {
    "focus": {"font": "sans", "size": 82, "accent": "#B5FF73", "max_words": 3,
              "case": "preserve", "position": "auto", "animation": "highlight"},
    "clean": {"font": "studio", "size": 78, "accent": "#FFFFFF", "max_words": 4,
              "case": "preserve", "position": "auto", "animation": "fade"},
    "punch": {"font": "sans", "size": 88, "accent": "#FFD65C", "max_words": 2,
              "case": "uppercase", "position": "auto", "animation": "highlight"},
}


def settings(raw=None):
    raw = raw or {}
    if not isinstance(raw, dict) or set(raw)-{"preset", "font", "size", "accent", "max_words", "case", "position", "animation"}:
        raise ValueError("Unknown caption setting.")
    preset = raw.get("preset", "focus")
    if preset not in PRESETS:
        raise ValueError("Choose Focus, Clean or Punch captions.")
    result = {"preset": preset, **PRESETS[preset], **raw}
    if result["font"] not in FONTS or result["case"] not in {"preserve", "uppercase"} or result["position"] not in {"auto", "upper", "middle", "lower"} or result["animation"] not in {"highlight", "fade"}:
        raise ValueError("Choose a supported caption font, position and animation.")
    if type(result["size"]) not in (int, float) or not math.isfinite(result["size"]) or not 54 <= result["size"] <= 110:
        raise ValueError("Caption size must be between 54 and 110.")
    if type(result["max_words"]) is not int or not 1 <= result["max_words"] <= 4:
        raise ValueError("Choose one to four words per caption.")
    if not isinstance(result["accent"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", result["accent"]):
        raise ValueError("Choose a six-digit caption color.")
    result["accent"] = result["accent"].upper()
    return result


def color(hex_value):
    return hex_value[5:7]+hex_value[3:5]+hex_value[1:3]


def words(mapped):
    """Stable output IDs, including separate occurrences of replayed words."""
    return [{"id": f"w{i}", **word} for i, word in enumerate(
        word for segment in mapped for word in (segment.get("words") or [
            {k: segment[k] for k in ("start", "end", "text")}]))]


def corrections(mapped, edits):
    if not isinstance(edits, dict) or len(edits) > 300:
        raise ValueError("Correct up to 300 caption words at a time.")
    valid = {word["id"] for word in words(mapped)}
    for ident, text in edits.items():
        if ident not in valid or not isinstance(text, str) or not 1 <= len(text.strip()) <= 60 or any(ord(c)<32 for c in text):
            raise ValueError("Caption corrections must refer to existing words and stay on one line (1–60 characters).")
    result = deepcopy(mapped)
    i = 0
    for segment in result:
        for word in segment.get("words") or [segment]:
            if f"w{i}" in edits:
                word["text"] = edits[f"w{i}"].strip()
            i += 1
        if segment.get("words"):
            segment["text"] = " ".join(w["text"] for w in segment["words"])
    return result


def font_measure(font, size):
    try:
        from PIL import ImageFont
        name = "CutroomSans-ExtraBold.ttf" if font == "sans" else "CutroomStudio-Bold.ttf"
        face = ImageFont.truetype(str(Path(__file__).resolve().parents[1]/"static/fonts/captions"/name), round(size))
        return face.getlength
    except (ImportError, OSError):
        return lambda text: len(text)*size*.62


def wrap(text, font, size, width=860):
    measure = font_measure(font, size)
    lines, line = [], ""
    for word in text.split():
        trial = (line+" "+word).strip()
        if line and measure(trial) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def make_ass(plan, mapped, suppressed, config, caption_mode="auto"):
    prefs = settings(plan.get("caption_settings", config.get("caption_settings")))
    font, size, accent = FONTS[prefs["font"]], prefs["size"], color(prefs["accent"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Captions,{font},{size},&H00FFFFFF,&H00FFFFFF,&H30201816,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,100,100,510,1
Style: Story,{font},68,&H00FFFFFF,&H00FFFFFF,&H30201816,&H80000000,-1,0,0,0,100,100,0,0,1,3,1.5,5,100,100,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    def emit(layer, start, end, name, text):
        if end > start:
            events.append(f"Dialogue: {layer},{core.ass_time(start)},{core.ass_time(end)},{name},,0,0,0,,{text}")
    position = prefs["position"]
    y = {"lower": 1450, "middle": 1130, "upper": 570}.get(position, 1400 if plan.get("layout")=="fit" else 1330)
    transform = str.upper if prefs["case"] == "uppercase" else str
    if caption_mode != "none":
        groups, current = [], []
        measure = font_measure(prefs["font"], size)
        for word in words(mapped):
            if current and (len(current)>=prefs["max_words"] or word["start"]-current[-1]["end"]>.4 or
                            re.search(r"[.!?。！？]$", current[-1]["text"]) or
                            measure(transform(" ".join(w["text"] for w in current+[word])))>850):
                groups.append(current)
                current=[]
            current.append(word)
        if current:
            groups.append(current)
        for group in groups:
            start, end = max(0,group[0]["start"]), min(plan["duration"],group[-1]["end"])
            if end<=start or any(max(start,a)<min(end,b) for a,b in suppressed):
                continue
            # Unaligned phrases fade as a whole: do not invent word timings.
            if prefs["animation"] == "fade" or len(group)==1:
                text = "\\N".join(core.ass_escape(line) for line in wrap(transform(" ".join(w["text"] for w in group)),prefs["font"],size))
                emit(0,start,end,"Captions",f"{{\\an2\\pos(540,{y})\\fad(45,65)}}"+text)
            else:
                for i, word in enumerate(group):
                    a = max(start,word["start"])
                    b = min(end,group[i+1]["start"]) if i+1<len(group) else end
                    # Do not hold a highlight through a long unspoken gap.
                    b = min(b,word["end"]+.12)
                    text = " ".join((f"{{\\c&H{accent}&}}" if j==i else "{\\c&HFFFFFF&}")+core.ass_escape(transform(w["text"])) for j,w in enumerate(group))
                    pop = "\\fscx97\\fscy97\\t(0,75,\\fscx100\\fscy100)" if i==0 else ""
                    emit(0,a,b,"Captions",f"{{\\an2\\pos(540,{y}){pop}}}"+text)
    for overlay in plan["overlays"]:
        text = overlay["text"]
        # Headlines keep natural casing and use a restrained two/three-line treatment.
        heading_size = 72 if overlay["kind"]=="hook" else 62
        lines = wrap(text,prefs["font"],heading_size)
        while len(lines)>3 and heading_size>48:
            heading_size-=4
            lines=wrap(text,prefs["font"],heading_size)
        fit = plan.get("layout")=="fit"
        heading_y = 432 if fit else 370
        if position=="upper":
            heading_y=1530
        text = "\\N".join(core.ass_escape(line) for line in lines)
        emit(1,overlay["at"],min(plan["duration"],overlay["at"]+overlay["duration"]),"Story",
             f"{{\\pos(540,{heading_y})\\fs{heading_size}\\fad(90,120)}}"+text)
    for span in plan["spans"]:
        if span["kind"]=="replay":
            emit(2,span["out_start"],span["out_end"],"Story","{\\an7\\pos(85,180)\\fs36}REPLAY")
    if config.get("watermark_text"):
        position=config.get("watermark_position","top-right")
        left,top=position.endswith("left"),position.startswith("top")
        alpha=round(255*(1-config.get("watermark_opacity",.20)))
        emit(3,0,plan["duration"],"Story",f"{{\\an{(7 if left else 9) if top else (1 if left else 3)}\\pos({65 if left else 1015},{115 if top else 1720})\\fs28\\fnCutroom Studio\\bord0.6\\shad1\\alpha&H{alpha:02X}&}}"+core.ass_escape(config["watermark_text"]))
    return header+"\n".join(events)+"\n"
