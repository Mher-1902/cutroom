"""Validated multi-span edits, animated typography, licensed audio and technical QC."""
import json
import hashlib
import math
from pathlib import Path
import re
import time

from . import core, local_models, runtime
from .contracts import remap_words
from .media import filter_path


def audio_catalog(root):
    path = Path(root) / "assets" / "audio" / "manifest.json"
    if not path.exists():
        raise RuntimeError("The CC0 audio catalog is missing. Run local setup.")
    catalog = json.loads(path.read_text())
    return catalog["assets"]


def asset_path(root, item):
    base = (Path(root) / "assets" / "audio").resolve()
    target = (base / item["path"]).resolve()
    if not target.is_relative_to(base) or not target.is_file() or item.get("license") != "CC0-1.0":
        raise ValueError("Audio asset is not an approved local CC0 file.")
    return target


def choose_music(root, mood, seed):
    choices = [a for a in audio_catalog(root) if a["kind"] == "music" and mood in a.get("moods", [a.get("mood")])]
    if not choices:
        raise RuntimeError("No licensed music is available for " + mood)
    return choices[int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % len(choices)]


def choose_sfx(root, kind):
    catalog = audio_catalog(root)
    preferred = {"impact": "sfx-impact-soft", "whoosh": "sfx-whoosh-soft", "tick": "sfx-pluck"}
    return next(a for a in catalog if a["id"] == preferred[kind])


def source_caption_intervals(index, plan):
    intervals = []
    for block in index["blocks"]:
        if not block.get("existing_captions"):
            continue
        for sample in block.get("regions", []):
            has_caption = any(t["rect"][1] > .48 and t["rect"][2] > .16 and len(t["text"]) > 4
                              and t.get("confidence", 0) > .4 for t in sample.get("texts", []))
            if not has_caption:
                continue
            for span in plan["spans"]:
                if span["kind"] != "freeze" and span["start"] <= sample["at"] < span["end"]:
                    at = span["out_start"] + (sample["at"] - span["start"]) / span["speed"]
                    intervals.append((max(span["out_start"], at-.45), min(span["out_end"], at+.65)))
    return intervals


def overlay_lines(text, size, width=860):
    """Wrap using the bundled rendered font, not a character-count guess."""
    try:
        from PIL import ImageFont
        font=ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'static/fonts/anton/Anton-Regular.ttf'),size)
        measure=font.getlength
    except (ImportError,OSError):
        measure=lambda value:len(value)*size*.55
    lines=[];line=''
    for word in text.split():
        trial=(line+' '+word).strip()
        if line and measure(trial)>width:
            lines.append(line);line=word
        else:line=trial
    if line:lines.append(line)
    return lines


def make_ass(plan, segments, index, style="kinetic",watermark=None):
    if style=='auto':
        style=plan.get('caption_style','kinetic')
    mapped = remap_words(segments, plan)
    suppressed = source_caption_intervals(index, plan)
    if plan.get('caption_settings') or (watermark or {}).get('caption_settings'):
        from . import caption_styles
        mapped=caption_styles.corrections(mapped,plan.get('caption_edits',{}))
        visible=plan.get('caption_enabled',style!='none')
        return caption_styles.make_ass(plan,mapped,suppressed,watermark or {},'auto' if visible else 'none'),mapped,len(suppressed)
    # Keep captions out of the source action and the upper story graphics.
    upper=plan.get('caption_position')=='upper' and plan.get('layout')!='fit'
    margin = 1320 if upper else 410
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Captions,Barlow Condensed,84,&H00FFFFFF,&H00FFFFFF,&H20120A0D,&H70120914,-1,0,0,0,100,100,0,0,3,10,0,2,100,100,{margin},1
Style: Hook,Anton,76,&H00D6F1FF,&H00D6F1FF,&H00190B13,&H70190B13,0,0,0,0,100,100,1,0,3,12,0,8,100,100,240,1
Style: Callout,Anton,69,&H00A68BF0,&H00A68BF0,&H00190B13,&H70190B13,0,0,0,0,100,100,1,0,1,4,2,8,100,100,330,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    if style != "none":
        for group in core.caption_groups(mapped, {"start": 0, "end": plan["duration"]}, 4):
            start, end = max(0, group[0]["start"]), min(plan["duration"], group[-1]["end"])
            if end <= start or any(max(start, a) < min(end, b) for a,b in suppressed):
                continue
            occupied=any(max(start,o['at'])<min(end,o['at']+o['duration']) for o in plan['overlays'])
            lane='{\\an2\\pos(540,1510)}' if upper and occupied else ''
            if style == "clean" or len(group) == 1:
                text = " ".join(core.ass_escape(w["text"]) for w in group)
                events.append(f"Dialogue: 0,{core.ass_time(start)},{core.ass_time(end)},Captions,,0,0,0,,{lane}{{\\fad(55,55)}}{text}")
            else:
                for i, word in enumerate(group):
                    a = max(start, word["start"])
                    b = min(end, group[i+1]["start"]) if i+1 < len(group) else end
                    if b <= a:
                        continue
                    text = " ".join(("{\\c&HA68BF0&}" if j == i else "{\\c&HFFFFFF&}") + core.ass_escape(w["text"]) for j,w in enumerate(group))
                    animate = "{\\fscx96\\fscy96\\t(0,85,\\fscx100\\fscy100)}" if i == 0 else ""
                    events.append(f"Dialogue: 0,{core.ass_time(a)},{core.ass_time(b)},Captions,,0,0,0,,{lane}{animate}{text}")
    for overlay in plan["overlays"]:
        hype=plan.get('screen_hook',{}).get('style')=='hype' and overlay['kind']!='label'
        size=(122 if overlay['kind']=='hook' else 94) if hype else (76 if overlay['kind']=='hook' else 69)
        visible=overlay['text'].upper() if hype else overlay['text']
        lines=overlay_lines(visible,size)
        while len(lines)>3 and size>72:
            size-=10;lines=overlay_lines(visible,size)
        emphasis=plan.get('screen_hook',{}).get('emphasis','').upper().strip('.,!?…')
        painted=[]
        for line in lines:
            words=[]
            for word in line.split():
                escaped=core.ass_escape(word)
                if hype and emphasis and word.strip('.,!?…').upper()==emphasis:
                    escaped='{\\c&HA68BF0&}'+escaped+'{\\c&HFFFFFF&}'
                words.append(escaped)
            painted.append(' '.join(words))
        text = "\\N".join(painted)
        name = "Hook" if overlay["kind"] == "hook" else "Callout"
        a, b = overlay["at"], min(plan["duration"], overlay["at"]+overlay["duration"])
        animation = (f"{{\\fs{size}\\bord6\\shad3\\fad(40,100)\\fscx82\\fscy82\\t(0,100,\\fscx108\\fscy108)\\t(100,190,\\fscx100\\fscy100)}}" if hype else
                     f"{{\\fs{size}\\fad(90,130)\\fscx88\\fscy88\\t(0,160,\\fscx100\\fscy100)}}")
        events.append(f"Dialogue: 1,{core.ass_time(a)},{core.ass_time(b)},{name},,0,0,0,,{animation}{text}")
    for span in plan["spans"]:
        if span["kind"] == "replay":
            events.append(f"Dialogue: 2,{core.ass_time(span['out_start'])},{core.ass_time(span['out_end'])},Callout,,0,0,0,,{{\\an7\\pos(80,180)\\fs48}}REPLAY")
    if watermark and watermark.get("watermark_text"):
        position=watermark.get("watermark_position","top-right")
        left=position.endswith("left")
        top=position.startswith("top")
        alpha=round(255*(1-watermark.get("watermark_opacity",.20)))
        x,y=(65 if left else 1015),(115 if top else 1720)
        anchor=(7 if left else 9) if top else (1 if left else 3)
        text=core.ass_escape(watermark["watermark_text"])
        tag=f"{{\\an{anchor}\\pos({x},{y})\\fs28\\fnBarlow Condensed\\bord0.6\\shad1\\blur0.3\\alpha&H{alpha:02X}&\\c&HFFFFFF&}}"
        events.append(f"Dialogue: 3,0:00:00.00,{core.ass_time(plan['duration'])},Captions,,0,0,0,,{tag}{text}")
    return header + "\n".join(events) + "\n", mapped, len(suppressed)


def srt(mapped):
    def stamp(t):
        ms = max(0, round(t*1000))
        hour, ms = divmod(ms, 3600000)
        minute, ms = divmod(ms, 60000)
        second, ms = divmod(ms, 1000)
        return f"{hour:02}:{minute:02}:{second:02},{ms:03}"
    lines = []
    for i, group in enumerate(core.caption_groups(mapped, {"start": 0, "end": 10000}, 6), 1):
        lines.append(f"{i}\n{stamp(group[0]['start'])} --> {stamp(group[-1]['end'])}\n" + " ".join(w["text"] for w in group) + "\n")
    return "\n".join(lines)


def crop_keyframes(index, span, focus, metadata):
    if metadata["width"] <= metadata["height"]:
        return []
    x, y, w, h = focus
    frames = []
    for block in index["blocks"]:
        if block["end"] <= span["start"] or block["start"] >= span["end"]:
            continue
        for sample in block.get("regions", []):
            if not span["start"] <= sample["at"] <= span["end"]:
                continue
            faces = sample.get("faces", [])
            candidates = [r for r in faces if x-.15 <= r[0]+r[2]/2 <= x+w+.15]
            if candidates:
                face = max(candidates, key=lambda r:r[2]*r[3])
                cx = face[0]+face[2]/2
                at = (sample["at"]-span["start"])/span["speed"]
                if not frames or at - frames[-1][0] >= 2:
                    frames.append((at, cx))
    return frames[:30]


def layout_filter(label, out, plan, width, height, index, span, metadata):
    layout = span.get("layout", plan["layout"])
    focus = span.get("focus", plan["focus"])
    portrait_fraction = min(1, (width/height)/(metadata["width"]/metadata["height"]))
    if layout == "crop" and focus[2] > portrait_fraction * 1.4:
        layout = "fit"
    if layout == "split" and not plan.get("facecam"):
        layout = "fit"
    if layout == "crop":
        center = focus[0] + focus[2]/2
        keyframes = crop_keyframes(index, span, focus, metadata) if index.get("mode") != "gameplay" else []
        expression = f"{center:.5f}"
        for (a, x), (b, y) in reversed(list(zip(keyframes, keyframes[1:]))):
            expression = f"if(between(t,{a:.3f},{b:.3f}),{x:.5f}+({y-x:.5f})*(t-{a:.3f})/{max(.01,b-a):.3f},{expression})"
        return f"{label}scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:x='max(0,min(iw-ow,iw*({expression})-ow/2))':y='max(0,min(ih-oh,ih*{focus[1]+focus[3]/2:.5f}-oh/2))',setsar=1{out}"
    if layout == "split":
        x,y,w,h = plan["facecam"]
        if h > .45 or y > .4 and y+h < .65:
            layout = "fit"
        else:
            top = round(height*.32/2)*2
            game_y, game_h = (y+h+.015, 1-y-h-.015) if y < .4 else (0, y-.015)
            if game_h < .45:
                layout = "fit"
            else:
                stem = out.strip("[]")
                return (f"{label}split=2[{stem}face][{stem}game];"
                        f"[{stem}face]crop=iw*{w:.5f}:ih*{h:.5f}:iw*{x:.5f}:ih*{y:.5f},scale={width}:{top}:force_original_aspect_ratio=increase,crop={width}:{top},setsar=1[{stem}top];"
                        f"[{stem}game]crop=iw:ih*{game_h:.5f}:0:ih*{game_y:.5f},scale={width}:{height-top}:force_original_aspect_ratio=decrease,pad={width}:{height-top}:(ow-iw)/2:(oh-ih)/2:color=0x190b13,setsar=1[{stem}bottom];"
                        f"[{stem}top][{stem}bottom]vstack=inputs=2{out}")
    stem = out.strip("[]")
    backdrop="brightness=-.24:saturation=.65" if plan.get('caption_settings') else "brightness=-.12"
    return (f"{label}split=2[{stem}bg][{stem}fg];"
            f"[{stem}bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=24:2,eq={backdrop}[{stem}back];"
            f"[{stem}fg]scale={width}:{height}:force_original_aspect_ratio=decrease[{stem}front];"
            f"[{stem}back][{stem}front]overlay=(W-w)/2:(H-h)/2,setsar=1{out}")


def encoder_options(encoder,final,width,threads=6):
    if encoder=='h264_videotoolbox':
        bitrate='16M' if width>=1080 else '8M'
        return ['-c:v','h264_videotoolbox','-allow_sw','0','-profile:v','high','-b:v',bitrate,
                '-realtime','0','-prio_speed','0','-pix_fmt','yuv420p']
    return ['-c:v','libx264','-threads',str(threads),'-preset','slow' if final else 'veryfast',
            '-crf','18' if final else '25','-pix_fmt','yuv420p']


def render(studio, job, source, plan, segments, index, metadata, folder, revision=0, final=False):
    run = lambda args: studio.run(job, args)
    stem = f"c-{plan['id']}-r{revision}-{'final' if final else 'draft'}"
    target = folder / (stem + ".mp4")
    ass_path, srt_path = folder / (stem + ".ass"), folder / (stem + ".srt")
    ass, mapped, preserved = make_ass(plan, segments, index, job["config"].get("style", "kinetic"),job["config"])
    ass_path.write_text(ass)
    srt_path.write_text(srt(mapped))
    marker = folder / (stem + ".complete.json")
    encoder=job['config'].get('video_encoder','libx264')
    if encoder=='auto':
        profile=studio.data/'render-profile.json'
        settings=json.loads(profile.read_text()) if profile.exists() else {}
        encoder='h264_videotoolbox' if final and settings.get('verified') and settings.get('encoder')=='h264_videotoolbox' else 'libx264'
    fingerprint = hashlib.sha256(json.dumps({"renderer_version":4,"encoder":encoder,"plan":plan,"config":job["config"],"ass":ass,
        "source":[str(source),source.stat().st_size,source.stat().st_mtime_ns]},sort_keys=True).encode()).hexdigest()
    completed=json.loads(marker.read_text()) if marker.exists() else {}
    if target.exists() and completed.get("fingerprint") == fingerprint and completed.get("bytes")==target.stat().st_size:
        return {"path": target, "ass": ass_path, "srt": srt_path, "mapped": mapped, "preserved_caption_intervals": preserved,
                'render_seconds':0,'cache_hit':True,'encoder':completed.get('encoder')}
    started=time.monotonic()
    marker.unlink(missing_ok=True)
    for suffix in ('.review.json', '.visual-review.json', '.story-review.json'):
        (folder/(stem+suffix)).unlink(missing_ok=True)
    temporary = folder / (stem + ".partial.mp4")
    width = job["config"].get("resolution", 1080) if final else 720
    height = round(width*16/9/2)*2
    left = min(s["start"] for s in plan["spans"])
    right = max(s["end"] if s["kind"] != "freeze" else s["start"]+.1 for s in plan["spans"])
    cool=job.get('processing_strategy',{}).get('mode')=='long_stream'
    command = [local_models.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-filter_complex_threads", "2" if cool else "4", "-y", "-ss", str(left), "-t", str(right-left+.25), "-i", str(source),
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    filters, inputs = [], []
    for i, span in enumerate(plan["spans"]):
        a, b = span["start"]-left, span["end"]-left
        raw = f"[raw{i}]"
        if span["kind"] == "freeze":
            filters.append(f"[0:v]trim=start={a:.5f}:end={a+.06:.5f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={span['duration']:.5f},trim=duration={span['duration']:.5f},fps=30{raw}")
            filters.append(f"[1:a]atrim=duration={span['duration']:.5f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            filters.append(f"[0:v]trim=start={a:.5f}:end={b:.5f},setpts=(PTS-STARTPTS)/{span['speed']:.5f},fps=30{raw}")
            if span.get('mute'):
                filters.append(f"[1:a]atrim=duration={span['duration']:.5f},asetpts=PTS-STARTPTS[a{i}]")
            else:
                audio = "[0:a]" if metadata["has_audio"] else "[1:a]"
                filters.append(f"{audio}atrim=start={a:.5f}:end={b:.5f},asetpts=PTS-STARTPTS,atempo={span['speed']:.5f},aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
        filters.append(layout_filter(raw, f"[v{i}]", plan, width, height, index, span, metadata))
        inputs.append(f"[v{i}][a{i}]")
    filters.append("".join(inputs) + f"concat=n={len(inputs)}:v=1:a=1[cutv][cuta]")
    if plan["zooms"]:
        expression = "1"
        for cue in plan["zooms"]:
            a,b = cue["at"],cue["at"]+cue["duration"]
            expression += f"+if(between(on/30,{a:.4f},{b:.4f}),{cue['scale']-1:.5f}*sin(PI*(on/30-{a:.4f})/{cue['duration']:.4f}),0)"
        filters.append(f"[cutv]zoompan=z='{expression}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=30[motion]")
    else:
        filters.append("[cutv]null[motion]")
    fontdir = studio.root / "static" / "fonts" / "captions"
    filters.append(f"[motion]subtitles=filename='{filter_path(ass_path)}':fontsdir='{filter_path(fontdir)}'[outv]")
    used, audio_labels, next_input = [], [], 2
    mood = plan["music_mood"]
    if job["config"].get("music") == "upload":
        music = studio.uploaded(job["source"]["music_upload"])
        command += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{next_input}:a]atrim=duration={plan['duration']:.5f},asetpts=PTS-STARTPTS,volume={plan.get('music_gain',.10)},afade=t=out:st={max(0,plan['duration']-1):.4f}:d=1[music]")
        next_input += 1
        audio_labels.append("[music]")
        used.append({"id": "user-music", "license": "User supplied"})
    elif mood != "none":
        item = choose_music(studio.root, mood, plan["id"])
        command += ["-stream_loop", "-1", "-i", str(asset_path(studio.root, item))]
        gain = plan.get("music_gain", .10)
        filters.append(f"[{next_input}:a]atrim=duration={plan['duration']:.5f},asetpts=PTS-STARTPTS,volume={gain},afade=t=in:d=0.35,afade=t=out:st={max(0,plan['duration']-1):.4f}:d=1[music]")
        audio_labels.append("[music]")
        next_input += 1
        used.append(item)
    effects = []
    for i, cue in enumerate(plan["sfx"]):
        item = choose_sfx(studio.root, cue["kind"])
        command += ["-i", str(asset_path(studio.root, item))]
        delay = round(cue["at"]*1000)
        filters.append(f"[{next_input}:a]volume=.18,adelay={delay}|{delay}[fx{i}]")
        effects.append(f"[fx{i}]")
        next_input += 1
        used.append(item)
    filters.append("[cuta]loudnorm=I=-16:TP=-2:LRA=11,aresample=48000,asplit=2[voice][key]")
    if audio_labels:
        filters.append("[music][key]sidechaincompress=threshold=.025:ratio=6:attack=15:release=250[ducked]")
        mix = ["[voice]", "[ducked]", *effects]
    else:
        filters.append("[key]anullsink")
        mix = ["[voice]", *effects]
    filters.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=.89[outa]")
    command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", "[outa]", "-t", str(plan["duration"])]
    video_start=len(command)
    command+=encoder_options(encoder,final,width,2 if cool else 6)
    video_end=len(command)
    command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(temporary)]
    try:
        try:
            run(command)
        except RuntimeError as exc:
            from .resources import ResourcePause
            if isinstance(exc,ResourcePause):raise
            if encoder!='h264_videotoolbox':raise
            studio.event(job,'Hardware encoding could not finish; retrying this render with the CPU encoder.')
            command=command[:video_start]+encoder_options('libx264',final,width,2 if cool else 6)+command[video_end:]
            encoder='libx264';run(command)
        probe=json.loads(run([local_models.binary("ffprobe"),"-v","error","-show_format","-of","json",str(temporary)]))
        if abs(float(probe["format"]["duration"])-plan["duration"])>.25:
            raise RuntimeError("Incomplete rendered duration; this draft will be retried on resume.")
        temporary.replace(target)
        runtime.atomic_json(marker,{"fingerprint":fingerprint,"bytes":target.stat().st_size,'encoder':encoder,
                                   'render_seconds':round(time.monotonic()-started,2)})
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    runtime.atomic_json(folder / (stem + ".assets.json"), {"assets": used, "caption_intervals_preserved": preserved})
    return {"path": target, "ass": ass_path, "srt": srt_path, "mapped": mapped, "assets": used, "preserved_caption_intervals": preserved,
            'render_seconds':round(time.monotonic()-started,2),'cache_hit':False,'encoder':encoder}


def technical_qc(studio, job, video, expected_duration, resolution):
    data = json.loads(studio.run(job, [local_models.binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)]))
    streams = data["streams"]
    picture = next(s for s in streams if s["codec_type"] == "video")
    duration = float(data["format"]["duration"])
    # loudnorm emits its analysis on stderr; Studio.run can return both streams.
    measurement = studio.run(job, [local_models.binary("ffmpeg"), "-hide_banner", "-i", str(video), "-vn", "-af",
                                   "loudnorm=I=-16:TP=-2:LRA=11:print_format=json", "-f", "null", "-"], include_stderr=True)
    chunks = re.findall(r'\{\s*"input_i".*?\}', measurement, flags=re.S)
    audio = json.loads(chunks[-1]) if chunks else {}
    peak = float(audio.get("input_tp", "inf"))
    loudness = float(audio.get("input_i", "-inf"))
    failures = []
    minimum=job['config'].get('min_duration',61)
    maximum=job['config'].get('max_duration',120)
    if duration<minimum-.05 or duration>maximum+.05:
        failures.append('Rendered duration is outside the chosen length range')
    if minimum>60 and duration<=60:
        failures.append('The chosen over-one-minute preset needs a video longer than 60 seconds')
    if abs(duration-expected_duration) > .25:
        failures.append("Rendered duration does not match the edit plan")
    expected_height = round(resolution*16/9/2)*2
    if picture["width"] != resolution or picture["height"] != expected_height:
        failures.append("Unexpected output dimensions")
    if not any(s["codec_type"] == "audio" for s in streams):
        failures.append("Missing audio track")
    if peak > -.15:
        failures.append("Audio true peak is too close to clipping")
    # Silent visual-only footage is legitimate; disclose it instead of inventing speech.
    return {"passed": not failures, "failures": failures, "duration": duration, "width": picture["width"], "height": picture["height"],
            "true_peak_dbtp": peak if math.isfinite(peak) else None, "integrated_lufs": loudness if math.isfinite(loudness) else None,
            "audio_measurement": audio}


def review_positions(frame_count,fps,plan=None,maximum=48):
    if frame_count<1:
        return []
    uniform_count=min(32,maximum,frame_count)
    positions=set(round(i*(frame_count-1)/max(1,uniform_count-1)) for i in range(uniform_count))
    cues=[]
    for cue in (plan or {}).get('zooms',[])+(plan or {}).get('overlays',[]):
        cues.append(min(frame_count-1,max(0,round((cue['at']+min(.35,cue['duration']/2))*fps))))
    for span in (plan or {}).get('spans',[]):
        if span['kind'] in {'replay','freeze'}:
            cues.append(min(frame_count-1,max(0,round((span['out_start']+span['duration']/2)*fps))))
    cues=sorted(set(cues));budget=max(0,maximum-len(positions))
    if budget and len(cues)>budget:
        cues=[cues[round(i*(len(cues)-1)/max(1,budget-1))] for i in range(budget)]
    return sorted(positions|set(cues[:budget]))


def review_images(studio, job, video, folder, stem, duration, maximum=48,plan=None):
    from .analysis import contact_sheet
    directory = folder / (stem + '-review')
    directory.mkdir(exist_ok=True)
    for old in directory.glob('f-*.jpg'):
        old.unlink()
    fps = 4
    studio.run(job, [local_models.binary('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(video),
                     '-vf', f'fps={fps:.8f}:round=up,scale=720:-2', '-q:v', '4', str(directory / 'f-%04d.jpg')])
    all_paths = sorted(directory.glob('f-*.jpg'))
    if len(all_paths)<max(1,int(duration*fps)-2):
        raise RuntimeError('Draft image extraction did not cover the full output timeline.')
    positions=review_positions(len(all_paths),fps,plan,maximum)
    paths = [all_paths[i] for i in positions]
    sheets = []
    for i in range(0, len(paths), 12):
        at = [n/fps for n in positions[i:i+12]]
        sheets.append(contact_sheet(paths[i:i+12], at, directory / f'sheet-{i//12}.jpg', tile_width=192,columns=4,label_prefix='OUTPUT'))
    return sheets


def create_cover(studio, job, video, title, path):
    from PIL import Image, ImageDraw, ImageFont
    studio.run(job, [local_models.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", str(path)])
    image = Image.open(path).convert("RGB")
    width, height = image.size
    shade = Image.new("RGBA", image.size)
    pen = ImageDraw.Draw(shade)
    for y in range(height//2, height):
        pen.line((0,y,width,y), fill=(31,9,20,int(220*(y-height/2)/(height/2))))
    image = Image.alpha_composite(image.convert("RGBA"), shade)
    pen = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(studio.root / "static/fonts/barlowcondensed/BarlowCondensed-Bold.ttf"), max(32, round(width*.085)))
    words, lines, line = title.split(), [], ""
    for word in words:
        trial = (line+" "+word).strip()
        if pen.textlength(trial, font=font) > width*.84 and line:
            lines.append(line);line=word
        else:
            line=trial
    if line:
        lines.append(line)
    text = "\n".join(lines[:4])
    pen.multiline_text((width*.08,height*.76), text, font=font, fill="#fff1d6", spacing=4, stroke_width=1, stroke_fill="#210b17")
    image.convert("RGB").save(path, quality=93)
