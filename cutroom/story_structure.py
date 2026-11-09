"""Eight required editorial beats, compiled onto the actual finished timeline."""
from copy import deepcopy

STAGES=('hook','lead','body_1','open_loop_1','body_2','open_loop_2','body_3','cta')
LABELS=('Hook','Lead','Body 1','Open loop 1','Body 2','Open loop 2','Body 3','CTA')
BRIEF_SCHEMA={'type':'object','properties':{key:{'type':'string','minLength':1,'maxLength':75} for key in STAGES},
              'required':list(STAGES)}
for _key in ('open_loop_1','open_loop_2','cta'):
    # Simple bounded strings are reliable on the pinned Metal backend. Question
    # punctuation is validated in Python and repaired in a small copy-only call.
    BRIEF_SCHEMA['properties'][_key]={'type':'string','minLength':4,'maxLength':60}
DIRECTIVE=(
    'EVERY short must follow these eight beats in order: Hook, Lead, Body 1, Open loop 1, '
    'Body 2, Open loop 2, Body 3, CTA. Fill story_brief with specific source-grounded intent for EACH beat. '
    'Hook raises curiosity; Lead establishes context; Body 1 develops it; Open loop 1 raises a NEW '
    'specific question answered in Body 2; Open loop 2 raises a further question answered in Body 3; '
    'Both loops must advance DIFFERENT uncertainties, not paraphrase the hook or each other. '
    'The first loop asks about a SMALL intermediate development actually resolved in Body 2 '
    '(for example whether the first shot lands), not the overall winner when the contest is still ongoing. '
    'Body 3 earns the final payoff; CTA invites a new relevant viewer reaction or action, '
    'not a question whose answer the viewer has just seen. '
    'Do not invent a missing payoff. Lead and body text are internal edit intentions, not section labels '
    'to display. Hook, both open-loop questions and CTA appear as concise on-screen text; keep each '
    'under 10 words and in the source language. The compiler allocates Hook to the first min(3 seconds,10%); '
    'Lead ends at 16%; Body 1 ends at 34%; each open-loop transition lasts at most 2.4 seconds; '
    'Body 2 ends at 61%, followed immediately by the second short loop and Body 3. '
    'Body 3 to the last 1.5–3 seconds; then CTA. Choose footage whose actual progression fits these '
    'beats, including very short edits. Questions must be answered AFTER their loop appears. '
    'Write EVERY brief as a complete clause of 3–8 words, not a long sentence cut off at the character limit. '
    'Both loops are SHORT questions. CTA is a relevant NEW viewer question, such as '
    '"Would you challenge LeBron?" for basketball, not a quote from the footage. '
    'Change pacing and treatment with content without omitting any stage. '
)


def beat_boundaries(duration):
    transition=min(2.4,duration*.08)
    return [0,min(3,duration*.1),duration*.16,duration*.34,duration*.34+transition,
            duration*.61,duration*.61+transition,duration-min(3,duration*.1),duration]


def source_sections(plan,start,end):
    result=[]
    for span in plan['spans']:
        left,right=max(start,span['out_start']),min(end,span['out_end'])
        if right<=left:continue
        a=span['start'] if span['kind']=='freeze' else span['start']+(left-span['out_start'])*span['speed']
        b=a if span['kind']=='freeze' else a+(right-left)*span['speed']
        result.append({'start':round(a,4),'end':round(b,4),'kind':span['kind']})
    return result


def validate_brief(brief):
    brief=deepcopy(brief)
    if set(brief)!=set(STAGES):raise ValueError('Every short needs all eight story beats in order.')
    for key in STAGES:
        if not isinstance(brief[key],str) or not 0<len(brief[key].strip())<=75:
            raise ValueError(f'Invalid {key} story beat; use 1–75 characters.')
        brief[key]=brief[key].strip()
        if key in {'open_loop_1','open_loop_2','cta'} and (len(brief[key])>60 or brief[key][-1] not in '?？؟'):
            raise ValueError(f'{key} needs a concise viewer question ending in a question mark.')
    return brief


def compile_story(plan,brief):
    brief=validate_brief(brief)
    duration=plan['duration']
    boundaries=beat_boundaries(duration)
    beats=[]
    for i,(key,label) in enumerate(zip(STAGES,LABELS)):
        left,right=boundaries[i:i+2]
        if right<=left:raise ValueError('The eight story beats do not fit the finished duration.')
        beats.append({'key':key,'label':label,'start':round(left,4),'end':round(right,4),
                      'intent':brief[key],'source_sections':source_sections(plan,left,right)})
    overlays=[o for o in plan.get('overlays',[]) if not o.get('story_role') and o.get('kind')!='hook']
    for beat in beats:
        if beat['key'] in {'hook','open_loop_1','open_loop_2','cta'}:
            overlays.append({'at':beat['start'],'duration':min(3,beat['end']-beat['start']),
                             'text':beat['intent'],'kind':'hook' if beat['key']=='hook' else 'callout',
                             'story_role':beat['key']})
    required=[o for o in overlays if o.get('story_role')]
    overlays=[o for o in overlays if o.get('story_role') or
              not any(max(o['at'],r['at'])<min(o['at']+o['duration'],r['at']+r['duration']) for r in required)]
    plan['overlays']=sorted(overlays,key=lambda o:o['at'])
    plan['screen_hook']={**plan.get('screen_hook',{}),'enabled':True,'text':brief['hook'],
                         'style':plan.get('screen_hook',{}).get('style','clean')}
    plan['story_structure']=beats
    plan['story_structure_version']=1
    return plan
