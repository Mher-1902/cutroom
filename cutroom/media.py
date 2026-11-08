"""Deterministic media rendering. Models never produce executable commands."""
import array
import json
import math
from pathlib import Path
import re
import wave

from .core import make_ass
from .local_models import binary
from .source_policy import MAX_SOURCE_SECONDS


def probe(path, run):
    payload = json.loads(run([binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    videos = [s for s in payload["streams"] if s["codec_type"] == "video"]
    audio = [s for s in payload["streams"] if s["codec_type"] == "audio"]
    if not videos or not audio:
        raise ValueError("The source needs both video and spoken audio.")
    duration = float(payload["format"].get("duration", 0))
    if not 5 < duration <= MAX_SOURCE_SECONDS:
        raise ValueError("Choose a video longer than 5 seconds and up to 12 hours.")
    return {"duration": duration, "width": videos[0]["width"], "height": videos[0]["height"]}


def make_soundtrack(path, duration, music=True, sfx=True):
    """An original, deliberately quiet synth bed and restrained transition accents."""
    rate = 22050
    notes = [(130.813, 164.814, 195.998), (110.0, 130.813, 164.814),
             (87.307, 110.0, 130.813), (97.999, 123.471, 146.832)]
    samples = array.array("h")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        for frame in range(int(duration * rate)):
            t = frame / rate
            value = 0.0
            if music:
                section = int(t / 8) % len(notes)
                phase = t % 8
                envelope = min(1, phase / 0.6, (8 - phase) / 0.6)
                value = sum(math.sin(2 * math.pi * freq * t) for freq in notes[section]) * 0.025 * envelope
            if sfx:
                # Two gentle accents, rather than effects on every sentence.
                for moment in (0.15, min(20.0, duration / 2)):
                    age = t - moment
                    if 0 <= age < 0.15:
                        value += 0.10 * math.exp(-age * 35) * math.sin(2 * math.pi * (700 * age - 900 * age * age))
            value *= min(1, t / 0.6, max(0, duration - t) / 1.2)
            samples.append(int(max(-1, min(1, value)) * 32767))
            if len(samples) == rate:
                out.writeframes(samples.tobytes())
                samples = array.array("h")
        out.writeframes(samples.tobytes())


def filter_path(path):
    # Filter arguments have their own escaping, independent of subprocess argv.
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")


def render(source, clip, segments, config, folder, run, music_file=None):
    duration = clip["end"] - clip["start"]
    width = config["resolution"]
    height = width * 16 // 9
    height += height % 2
    target = folder / f"clip-{clip['rank']:02}.mp4"
    ass = folder / f"clip-{clip['rank']:02}.ass"
    ass.write_text(make_ass(segments, clip, config["style"]), encoding="utf-8")
    common = f"fps=30,setsar=1"
    if config["layout"] == "fit":
        video = (f"[0:v]{common},split=2[bg][fg];"
                 f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=30:2[back];"
                 f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[front];"
                 f"[back][front]overlay=(W-w)/2:(H-h)/2[frame]")
    else:
        video = f"[0:v]{common},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[frame]"
    if config["style"] != "none":
        video += f";[frame]subtitles=filename='{filter_path(ass)}'[outv]"
    else:
        video += ";[frame]null[outv]"
    command = [binary("ffmpeg"), "-hide_banner", "-y", "-ss", str(clip["start"]), "-t", str(duration), "-i", str(source)]
    has_generated = config["music"] == "ambient" or config["sfx"]
    tracks = []
    next_input = 1
    if has_generated:
        generated = folder / f"bed-{clip['rank']:02}.wav"
        make_soundtrack(generated, duration, config["music"] == "ambient", config["sfx"])
        command += ["-i", str(generated)]
        tracks.append(f"[{next_input}:a]")
        next_input += 1
    if config["music"] == "upload":
        if not music_file:
            raise ValueError("Upload a music track or choose a different soundtrack.")
        command += ["-stream_loop", "-1", "-i", str(music_file)]
        video += f";[{next_input}:a]volume=0.12[uploaded]"
        tracks.append("[uploaded]")
    if tracks:
        video += ";[0:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[voice][key]"
        if len(tracks) == 1:
            video += f";{tracks[0]}anull[bed]"
        else:
            video += ";" + "".join(tracks) + f"amix=inputs={len(tracks)}:normalize=0[bed]"
        video += ";[bed][key]sidechaincompress=threshold=0.025:ratio=6:attack=20:release=300[ducked]"
        video += ";[voice][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[outa]"
    else:
        video += ";[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[outa]"
    command += ["-filter_complex", video, "-map", "[outv]", "-map", "[outa]", "-t", str(duration),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(target)]
    run(command)
    thumbnail = folder / f"clip-{clip['rank']:02}.jpg"
    run([binary("ffmpeg"), "-hide_banner", "-y", "-ss", "1", "-i", str(target), "-frames:v", "1", "-q:v", "3", str(thumbnail)])
    return target, thumbnail
