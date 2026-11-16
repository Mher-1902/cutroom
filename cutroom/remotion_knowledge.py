"""Private, versioned skill library. Never publish the installed plugin corpus."""
import hashlib
import json
from pathlib import Path
import shutil

SKILL_VERSION = '4.0.534'
RUNTIME_VERSION = '4.0.542'
ROLES = {
    'director': ['remotion-markup/video-editing.md', 'remotion-markup/timing-props.md',
                 'remotion-captions/display-captions.md', 'remotion-interactivity/SKILL.md'],
    'renderer': ['remotion-render/SKILL.md', 'remotion-saas/rendering.md'],
    'studio': ['remotion-studio/SKILL.md', 'remotion-interactivity/SKILL.md'],
}
DIRECTOR = """
Remotion finishing tools are enabled. Your validated edit plan is compiled to a
real React/Remotion timeline: individual video spans, word-timed captions,
animated hook/open-loop/CTA titles, replay labels and a subtle watermark.
Use overlays {at,duration,kind,text,story_role} at OUTPUT seconds; captions use
the measured source-to-output mapping, including cuts, speed and replays.
Framing, zooms, freezes, music ducking and sound cues are prepared by the media
engine, then Remotion finishes typography. Choose the amount of text and timing
for THIS source: restrained fades for suspense/conversation, short emphasis for
comedy/gameplay. Keep graphics clear of important action and existing text.
Give each title time to read; do not repeat every spoken word in an extra title.
The workflow is plan -> prepare media -> compose layers -> preview -> render ->
visual/audio critique -> revise. Use the existing evidence and critique stages.
Only return the validated JSON schema. Never write JavaScript or shell commands.
Maps, remote stock, cloud rendering and new model downloads are not automatic
tools. The full installed skill library is available to local development tools;
only relevant bounded guidance belongs in a model request.
"""


def library(data):
    return Path(data)/'integrations'/'remotion'


def install(data, source):
    source=Path(source).resolve()
    if not (source/'remotion-best-practices'/'SKILL.md').is_file():
        raise ValueError('Select the installed Remotion skills directory.')
    target=library(data)
    target.mkdir(parents=True,exist_ok=True)
    files={}
    for file in sorted(source.rglob('*')):
        if file.is_file() and not file.is_symlink():
            name=file.relative_to(source).as_posix()
            dest=target/'skills'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,dest)
            files[name]=hashlib.sha256(file.read_bytes()).hexdigest()
    manifest={'skill_version':SKILL_VERSION,'runtime_version':RUNTIME_VERSION,'files':files,
              'workflows':sorted(p.name for p in source.iterdir() if p.is_dir()),'private':True}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def read(data, name, limit=6000):
    root=(library(data)/'skills').resolve()
    file=(root/name).resolve()
    if not file.is_relative_to(root) or file.suffix!='.md' or not file.is_file():
        raise ValueError('Choose a Markdown document inside the local skill library.')
    return file.read_text()[:max(0,min(int(limit),12000))]


def guidance(data, role='director', limit=3500):
    """Retrieve exact excerpts without filling the 8K director context."""
    excerpts=[]
    for name in ROLES.get(role,[]):
        try: excerpts.append(name+'\n'+read(data,name,900))
        except ValueError: pass
    return ('\n\n'.join(excerpts))[:limit]


def search(data, query):
    terms=query.lower().split()
    results=[]
    for file in (library(data)/'skills').rglob('*.md'):
        content=file.read_text()
        score=sum(content.lower().count(t) for t in terms)
        if score: results.append((score,file.relative_to(library(data)/'skills').as_posix()))
    return [name for _,name in sorted(results,reverse=True)[:12]]
