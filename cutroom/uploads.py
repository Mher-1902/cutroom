"""Bounded resumable local uploads; offsets prevent duplicate chunks on retries."""
import json
from pathlib import Path
import re
import shutil
import threading
import uuid

from . import runtime

CHUNK_BYTES=8*1024**2
MAX_BYTES=64*1024**3
RESERVE_BYTES=4*1024**3
EXTENSIONS={'.mp4','.mov','.mkv','.webm','.m4v','.mp3','.m4a','.wav','.ogg','.aac'}


class UploadStore:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.lock=threading.RLock()

    def record(self,ident):
        if not re.fullmatch('[a-f0-9]{32}',str(ident)):raise ValueError('Upload not found.')
        path=self.folder/(ident+'.upload.json')
        if not path.exists():raise ValueError('Upload not found.')
        return json.loads(path.read_text())

    def status(self,ident):
        with self.lock:
            value=self.record(ident)
            path=self.folder/(ident+value['extension'])
            partial=self.folder/(ident+'.partial')
            # Recover a crash between the final chunk and its rename.
            if not path.exists() and partial.exists() and partial.stat().st_size==value['bytes']:
                partial.replace(path)
            complete=path.is_file()
            offset=path.stat().st_size if complete else partial.stat().st_size if partial.exists() else 0
            return {'id':ident,'name':value['name'],'bytes':value['bytes'],'offset':offset,
                    'complete':complete,'chunk_bytes':CHUNK_BYTES}

    def create(self,name,size):
        name=Path(str(name)).name;extension=Path(name).suffix.lower()
        if extension not in EXTENSIONS:raise ValueError('Choose a video file or a music track.')
        if type(size) is not int or not 0<size<=MAX_BYTES:raise ValueError('Choose a file up to 64 GiB.')
        if shutil.disk_usage(self.folder).free<size+RESERVE_BYTES:
            raise ValueError('Not enough disk space for this upload and 4 GiB of working space.')
        ident=uuid.uuid4().hex
        runtime.atomic_json(self.folder/(ident+'.upload.json'),{'name':name[:255],'extension':extension,'bytes':size})
        return self.status(ident)

    def append(self,ident,offset,length,stream):
        with self.lock:
            value=self.record(ident);current=self.status(ident)
            if not 0<length<=CHUNK_BYTES:raise ValueError('Upload chunks must be at most 8 MiB.')
            if offset!=current['offset'] or current['complete']:
                # The caller must drain this body before reusing HTTP/1.1.
                return current,False
            if offset+length>value['bytes']:raise ValueError('Upload exceeds its declared size.')
            if shutil.disk_usage(self.folder).free<length+RESERVE_BYTES:
                raise ValueError('Disk space is low. Upload progress is saved; free working space before resuming.')
            path=self.folder/(ident+'.partial')
            with path.open('ab') as target:
                remaining=length
                while remaining:
                    block=stream.read(min(1024**2,remaining))
                    if not block:raise ValueError('Upload interrupted. Select the same file to resume.')
                    target.write(block);remaining-=len(block)
            return self.status(ident),True
