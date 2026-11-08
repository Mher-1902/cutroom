"""Shared source limits and automatic long-recording routing."""
import math

MAX_SOURCE_SECONDS = 12 * 60 * 60
LONG_SOURCE_SECONDS = 3 * 60 * 60
SCOUT_SECONDS = 30 * 60
CONTEXT_SECONDS = 30
ASR_SECONDS = 5 * 60


def strategy(duration):
    duration = float(duration)
    if not math.isfinite(duration) or not 5 < duration <= MAX_SOURCE_SECONDS:
        raise ValueError("Choose a completed video longer than 5 seconds and up to 12 hours.")
    long = duration > LONG_SOURCE_SECONDS
    return {"mode": "long_stream" if long else "standard", "automatic": True,
            "scout_count": math.ceil(duration / SCOUT_SECONDS) if long else 0,
            "scout_seconds": SCOUT_SECONDS, "concurrent_heavy_tasks": 1,
            "threshold_seconds": LONG_SOURCE_SECONDS}


def scout_chunks(duration):
    strategy(duration)
    return [{"id": f"scout-{i:03}", "start": i * SCOUT_SECONDS,
             "end": min(duration, (i + 1) * SCOUT_SECONDS),
             "context_start": max(0, min(i * SCOUT_SECONDS - CONTEXT_SECONDS, min(duration, (i+1)*SCOUT_SECONDS)-180)),
             "context_end": min(duration, (i + 1) * SCOUT_SECONDS + CONTEXT_SECONDS)}
            for i in range(math.ceil(duration / SCOUT_SECONDS))]
