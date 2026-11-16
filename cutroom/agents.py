"""Bounded editor-agent handoffs and a deterministic supervising judge.

Roles share the existing local GPU models; these are not concurrent model
replicas. Model outputs are validated data. Only the pipeline runs tools.
"""
import hashlib
import json
import math
from . import runtime

VERSION = 1
ROLES = {
    'scout': {'responsibility': 'Propose source moments, never certify them.', 'tools': ['propose_moments']},
    'observer': {'responsibility': 'Inspect timestamped source evidence.', 'tools': ['inspect_source']},
    'director': {'responsibility': 'Choose measured cuts, story and finishing per event.', 'tools': ['create_edit_plan']},
    'framer': {'responsibility': 'Preserve source text and subjects scene by scene.', 'tools': ['compile_layouts']},
    'critic': {'responsibility': 'Inspect the actual draft, story and technical measurements.', 'tools': ['review_draft']},
    'lead': {'responsibility': 'Enforce evidence, distinctness and revision limits.',
             'tools': ['qualify_source', 'export', 'revise_plan', 'apply_fixes', 'replace_candidate']},
    'renderer': {'responsibility': 'Execute the validated edit and export a local MP4.', 'tools': ['render_video']},
}


def record(folder, candidate_id, role, tool, evidence, result, revision=0):
    if role not in ROLES or tool not in ROLES[role]['tools']:
        raise ValueError('This editor agent cannot invoke that tool.')
    payload = {'version': VERSION, 'candidate_id': candidate_id, 'role': role, 'tool': tool,
               'revision': revision, 'evidence': evidence, 'result': result}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    path = folder/'agent-workflow.json'
    document = json.loads(path.read_text()) if path.exists() else {'version': VERSION, 'roles': ROLES, 'handoffs': []}
    if not any(item.get('id') == signature for item in document['handoffs']):
        document['handoffs'].append({'id': signature, **payload})
        runtime.atomic_json(path, document)
    return payload


def source_intervals(plan):
    spans = plan.get('spans') or [{'start': plan['start'], 'end': plan['end'], 'kind': 'normal'}]
    merged = []
    for a, b in sorted((s['start'], s['end']) for s in spans if s.get('kind', 'normal') == 'normal'):
        if not math.isfinite(a+b) or b <= a:
            raise ValueError('Invalid source interval in collection check.')
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def collection_conflict(plan, clips):
    """Compare original source unions, not titles, crops or replay durations."""
    own = source_intervals(plan)
    own_seconds = sum(b-a for a, b in own)
    for clip in clips:
        if clip.get('id') == plan.get('id'):
            continue
        other = source_intervals(clip.get('edit_plan') or clip)
        shared = sum(max(0, min(b, d)-max(a, c)) for a, b in own for c, d in other)
        ratio = shared/max(.001, min(own_seconds, sum(d-c for c, d in other)))
        if ratio > .20:
            return {'clip_id': clip['id'], 'shared_source_seconds': round(shared, 3), 'overlap_fraction': round(ratio, 4)}
    return None


def judge_review(review, passed, can_revise):
    """Choose one allowed action from evidence, not a free-form tool command."""
    if passed:
        return {'action': 'export', 'reason': 'Editorial, source and technical gates passed.'}
    if review.get('entertainment_passed') is False or review.get('raw_source_has_standout') is False:
        return {'action': 'replace_candidate', 'reason': 'Finishing cannot repair an ordinary source moment.'}
    if not can_revise:
        return {'action': 'replace_candidate', 'reason': 'The two automatic revision rounds are exhausted.'}
    actions = {p['action'] for p in review.get('problems', [])}-{ 'none' }
    mechanical = {'fit_frame', 'move_captions', 'less_music', 'less_sfx', 'less_overlays'}
    if (actions and actions <= mechanical and not review.get('integrity_problems')
            and review.get('structure_passed', True) and
            all(review.get('metrics', {}).get(k, 3) >= 3 for k in ('hook', 'clarity', 'payoff'))):
        return {'action': 'apply_fixes', 'reason': 'Apply the critic’s specific framing, text or mix corrections.'}
    return {'action': 'revise_plan', 'reason': 'The source cuts, hook or story need a new validated plan.'}
