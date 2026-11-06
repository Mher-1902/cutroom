"""Bounded broad-pass sampling; semantic selection still uses speech and vision."""
import math

WINDOW_SECONDS = 60


def positions(start, end, frame_count, cuts=(), sounds=(), hint=None):
    low = max(0, int(start))
    high = min(frame_count - 1, math.ceil(end) - 1)
    if high < low:
        return []
    if high - low < 12:
        return list(range(low, high + 1))
    # Uniform anchors cover the whole interval even in quiet, speech-free scenes.
    uniform = {round(low + i * (high - low) / 11) for i in range(12)}
    anchors = [(float(t) + .5, .2) for t in cuts if start <= t < end]
    for cue in sounds:
        at, kind = float(cue.get('at', -1)), cue.get('kind', '')
        if start <= at < end and kind != 'music':
            anchors.append((at, 1 + float(cue.get('confidence', 0))))
    if hint is not None and start <= hint < end:
        anchors.append((float(hint), 10))
    selected = set(uniform)
    # Extra event glimpses are distributed through the window; they do not
    # replace the quiet intervals or decide which moments become clips.
    for part in range(6):
        a = start + (end - start) * part / 6
        b = start + (end - start) * (part + 1) / 6
        options = [(score, at) for at, score in anchors if a <= at < b
                   and all(abs(at - old) >= .75 for old in selected)]
        if options:
            _, at = max(options)
            selected.add(max(low, min(high, round(at))))
    return sorted(selected)


def legacy_window(blocks, start, end):
    """Reuse complete already-inspected intervals without claiming a new run."""
    included = sorted([b for b in blocks if b['end'] > start and b['start'] < end], key=lambda b:b['start'])
    cursor = start
    for block in included:
        if block['start'] > cursor + .1:
            return None
        cursor = max(cursor, min(end, block['end']))
    if not included or cursor < end - .1:
        return None
    modes = [b['mode'] for b in included]
    regions = {round(r['at'], 3):r for b in included for r in b.get('regions', []) if start <= r['at'] < end}
    return {'start':start, 'end':end, 'summary':' '.join(b['summary'] for b in included),
            'mode':max(set(modes), key=modes.count), 'events':[e for b in included for e in b['events']
                if start <= e['at'] and e['end'] <= end + .1],
            'focus':[0,0,1,1], 'facecam':next((b.get('facecam') for b in included if b.get('facecam')), []),
            'existing_captions':any(b.get('existing_captions') for b in included),
            'frame_count':len(regions), 'regions':[regions[t] for t in sorted(regions)],
            'analysis_runtime':'cached-previous-engine', 'reused_dense_blocks':len(included)}


def compact_regions(regions, times):
    result = []
    seen = set()
    for at, region in zip(times, regions):
        faces = [[round(v,3) for v in face] for face in region.get('faces', [])[:4]]
        texts = []
        for text in region.get('texts', []):
            key = (str(text.get('text','')).strip(), tuple(round(v,1) for v in text['rect']))
            if key in seen or not key[0]:
                continue
            seen.add(key)
            texts.append({'text':key[0][:100], 'rect':[round(v,3) for v in text['rect']]})
        if faces or texts:
            result.append({'at':at, 'faces':faces, 'texts':texts[:6]})
    return result
