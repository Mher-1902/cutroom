#!/usr/bin/env python3
"""Local tools for Cutroom's lead AI and developer; no external model service."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cutroom import remotion_knowledge as knowledge
from cutroom.remotion_bridge import available

p=argparse.ArgumentParser(description=__doc__)
commands=p.add_subparsers(dest='command',required=True)
commands.add_parser('status')
setup=commands.add_parser('import-skills');setup.add_argument('directory',type=Path)
search=commands.add_parser('search');search.add_argument('query')
read=commands.add_parser('read');read.add_argument('document');read.add_argument('--limit',type=int,default=6000)
guide=commands.add_parser('guide');guide.add_argument('role',choices=list(knowledge.ROLES))
args=p.parse_args();data=ROOT/'data'
if args.command=='status':
    manifest=knowledge.library(data)/'manifest.json'
    library=json.loads(manifest.read_text()) if manifest.exists() else {}
    print(json.dumps({'runtime_ready':available(ROOT),'runtime_version':knowledge.RUNTIME_VERSION,
                      'skills':len(library.get('files',{})),'workflows':library.get('workflows',[])},indent=2))
elif args.command=='import-skills':
    result=knowledge.install(data,args.directory)
    print(f"Imported {len(result['files'])} files across {len(result['workflows'])} workflows locally.")
elif args.command=='search':print('\n'.join(knowledge.search(data,args.query)))
elif args.command=='read':print(knowledge.read(data,args.document,args.limit))
elif args.command=='guide':print(knowledge.DIRECTOR+'\n'+knowledge.guidance(data,args.role))
