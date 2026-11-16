"""Compile source evidence into timed framing and shared graphics placement.

Inspired by OpenShorts' per-scene layouts and layout-range handoff (MIT core).
No model-authored coordinates, commands, new detectors or cloud calls are run.
The story EDL stays intact; rendering receives a separate derived shot list.
"""
from copy import deepcopy

VERSION = 1


def samples(index, start, end):
    return [sample for block in index.get('blocks', [])
            if block['end'] > start and block['start'] < end
            for sample in block.get('regions', []) if start <= sample['at'] < end]


def important_text(item):
    text = str(item.get('text', '')).strip()
    x, y, w, h = item.get('rect', [0, 0, 0, 0])
    return (item.get('confidence', 0) >= .55 and len(text) >= 6 and w >= .18
            and h >= .012 and not (y < .14 and w < .28))


def intersection(a, b):
    x, y = max(a[0], b[0]), max(a[1], b[1])
    w = max(0, min(a[0]+a[2], b[0]+b[2])-x)
    h = max(0, min(a[1]+a[3], b[1]+b[3])-y)
    return w*h


def crop_rect(focus, metadata, center=None):
    ratio = (9/16)/(metadata['width']/metadata['height'])
    if ratio >= 1:
        h = min(1, 1/ratio)
        return [0, max(0, min(1-h, focus[1]+focus[3]/2-h/2)), 1, h]
    cx = center if center is not None else focus[0]+focus[2]/2
    return [max(0, min(1-ratio, cx-ratio/2)), 0, ratio, 1]


def protected_boxes(shot_samples):
    boxes = []
    for sample in shot_samples:
        boxes.extend((rect, 'face') for rect in sample.get('faces', []))
        boxes.extend((item['rect'], 'text') for item in sample.get('texts', []) if important_text(item))
    return boxes


def projected(box, viewport, destination):
    """Visible source rectangle -> output rectangle, all normalized."""
    x, y = max(box[0], viewport[0]), max(box[1], viewport[1])
    right, bottom = min(box[0]+box[2], viewport[0]+viewport[2]), min(box[1]+box[3], viewport[1]+viewport[3])
    if right <= x or bottom <= y:
        return None
    dx, dy, dw, dh = destination
    return [dx+(x-viewport[0])/viewport[2]*dw, dy+(y-viewport[1])/viewport[3]*dh,
            (right-x)/viewport[2]*dw, (bottom-y)/viewport[3]*dh]


def compile_plan(plan, index, metadata, config):
    plan = deepcopy(plan)
    shots, ranges = [], []
    portrait = metadata['width']/metadata['height'] <= 9/16+.02
    for span in plan['spans']:
        # Quantize interior cut points on the OUTPUT clock, then map back.
        # This also works for replays, teasers and speed changes.
        points = [span['start']]
        if span['kind'] != 'freeze':
            for cut in index.get('cuts', []):
                out = round((span['out_start']+(cut-span['start'])/span['speed'])*30)/30
                source = span['start']+(out-span['out_start'])*span['speed']
                if points[-1]+1 <= source <= span['end']-1:
                    points.append(source)
        points.append(span['end'])
        # Avoid pathological filtergraphs on flash montages; still preserve
        # all frames and inspect the entire coarser interval for text loss.
        if len(points) > 33:
            points = [points[round(i*(len(points)-1)/32)] for i in range(33)]
        for a, b in zip(points, points[1:]):
            shot = deepcopy(span)
            shot.update(start=a, end=b)
            if span['kind'] != 'freeze':
                shot.update(out_start=span['out_start']+(a-span['start'])/span['speed'],
                            out_end=span['out_start']+(b-span['start'])/span['speed'], duration=(b-a)/span['speed'])
            layout, focus = span.get('layout', plan['layout']), span.get('focus', plan['focus'])
            reason = 'Director framing retained.'
            measured = samples(index, a, b if b > a else a+.1)
            boxes = protected_boxes(measured)
            viewport = crop_rect(focus, metadata)
            if portrait:
                layout, reason = 'fit', 'Portrait source preserved without a second crop.'
            elif layout=='crop' and focus[2] > min(1,(9/16)/(metadata['width']/metadata['height']))*1.4:
                layout, reason = 'fit', 'The requested subject region is wider than a safe portrait crop.'
            elif layout == 'crop':
                lost = any(kind == 'text' and intersection(box, viewport) < .92*box[2]*box[3]
                           for box, kind in boxes)
                multi = any(len(s.get('faces', [])) > 1 and any(
                    intersection(face, viewport) < .85*face[2]*face[3] for face in s['faces']) for s in measured)
                if (lost or multi) and not plan.get('framing_override'):
                    layout, reason = 'fit', ('Source text crosses the portrait crop.' if lost else 'The crop would lose a visible participant.')
            if layout == 'split' and not plan.get('facecam'):
                layout, reason = 'fit', 'No measured creator camera for a split.'
            shot.update(layout=layout, focus=focus)
            source_aspect = metadata['width']/metadata['height']
            if layout == 'fit':
                w, h = min(1, source_aspect/(9/16)), min(1, (9/16)/source_aspect)
                dest = [(1-w)/2, (1-h)/2, w, h]
                viewport = [0, 0, 1, 1]
            else:
                dest = [0, 0, 1, 1]
            protected = []
            if layout != 'split':
                for box, kind in boxes:
                    mapped = projected(box, viewport, dest)
                    if mapped and not any(intersection(mapped, p['rect']) > .9*mapped[2]*mapped[3] for p in protected):
                        protected.append({'rect': mapped, 'kind': kind})
            else:
                # The creator panel is real picture, not empty space for a hook.
                protected.append({'rect':[0,0,1,.32],'kind':'face'})
                x,y,w,h=plan['facecam']
                game_y,game_h=(y+h+.015,1-y-h-.015) if y<.4 else (0,y-.015)
                if h>.45 or (.4<y and y+h<.65) or game_h<.45:
                    shot['layout']=layout='fit'
                    wout,hout=min(1,source_aspect/(9/16)),min(1,(9/16)/source_aspect)
                    dest=[(1-wout)/2,(1-hout)/2,wout,hout]
                    protected=[{'rect':mapped,'kind':kind} for box,kind in boxes
                               if (mapped:=projected(box,[0,0,1,1],dest))]
                    reason='The measured camera cannot form a safe gameplay split.'
                else:
                    game_aspect=source_aspect/game_h
                    wout,hout=min(1,game_aspect*.68/(9/16)),min(.68,(9/16)/game_aspect)
                    dest=[(1-wout)/2,.32+(.68-hout)/2,wout,hout]
                    for box,kind in boxes:
                        mapped=projected(box,[0,game_y,1,game_h],dest)
                        if mapped:protected.append({'rect':mapped,'kind':kind})
            entry = {'start': shot['out_start'], 'end': shot['out_end'], 'source_start': a, 'source_end': b,
                     'layout': layout, 'reason': reason, 'protected': protected[:64]}
            if layout in {'fit','split'}:
                entry['content'] = dest
            # Merge equal neighboring derived shots, never across story spans.
            if shots and len(points) > 2 and shots[-1].get('_span') == id(span) and all(
                    shots[-1][key] == shot[key] for key in ('layout', 'focus', 'kind', 'speed')):
                shots[-1].update(end=b, out_end=shot['out_end'], duration=shot['out_end']-shots[-1]['out_start'])
            else:
                shot['_span'] = id(span)
                shots.append(shot)
            ranges.append(entry)
    for shot in shots:
        shot.pop('_span', None)
    # Zooming the composed frame would crop the very source text we protected.
    zooms = [cue for cue in plan.get('zooms', []) if not any(
        cue['at'] < r['end'] and cue['at']+cue['duration'] > r['start'] and
        (r['layout'] in {'fit', 'split'} or any(p['kind'] == 'text' for p in r['protected'])) for r in ranges)]
    plan.update(render_spans=shots, layout_ranges=ranges, layout_version=VERSION, zooms=zooms)
    return plan


def graphic_y(plan, at, duration, kind, height=160):
    """Shared ASS/Remotion safe lane, on the 1080x1920 authored canvas."""
    ranges = [r for r in plan.get('layout_ranges', []) if r['start'] < at+duration and r['end'] > at]
    if not ranges:
        return (432 if plan.get('layout') == 'fit' else 370) if kind == 'title' else (1400 if plan.get('layout') == 'fit' else 1330)
    preferred = .20 if kind == 'title' else (.36 if all(r['layout'] == 'split' for r in ranges) else .74)
    choices = [.16, .20, .24, .35, .43, .48, .52, .59, .70, .74, .78] if kind == 'title' else [.36, .43, .52, .61, .70, .74, .78]
    h = min(.24, height/1920)
    best = None
    for center in choices:
        # Captions use bottom alignment; titles use centered alignment.
        top = center-h/2 if kind == 'title' else center-h
        if top < .06 or top+h > .81:
            continue
        rect = [.10, top, .80, h]
        cost = abs(center-preferred)*.12
        if kind=='caption':
            for cue in plan.get('overlays',[]):
                if cue['at']<at+duration and cue['at']+cue['duration']>at:
                    title_y=graphic_y(plan,cue['at'],cue['duration'],'title',190)/1920
                    cost+=intersection(rect,[.10,title_y-.06,.8,.12])*12
        for r in ranges:
            weight = max(0, min(r['end'], at+duration)-max(r['start'], at))/max(duration, .001)
            cost += weight*sum(intersection(rect, p['rect'])/max(.001, p['rect'][2]*p['rect'][3]) for p in r.get('protected', []))
            if r.get('content'):
                cost += weight*intersection(rect, r['content'])*3
        if best is None or cost < best[0]:
            best = cost, center
    return round((best[1] if best else preferred)*1920)
