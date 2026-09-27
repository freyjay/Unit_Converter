#!/usr/bin/env python3
"""Verify the received package before editing it. This checks bytes, not authorship."""
from pathlib import Path, PurePosixPath
import hashlib,json,sys

ROOT=Path(__file__).resolve().parent.parent

def verify(root):
    root=Path(root).resolve();seen=set();failures=[]
    for line in (root/'PACKAGE-CONTENTS.sha256').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);relative=PurePosixPath(name)
        if not re_digest(digest) or relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError('Invalid checksum entry')
        if name.casefold() in seen:raise ValueError('Duplicate checksum entry')
        seen.add(name.casefold());path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Checksum path escapes package')
        if not path.is_file():failures.append('Missing: '+name)
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=digest:failures.append('Changed: '+name)
    if not seen:raise ValueError('Empty checksum inventory')
    return {'passed':not failures,'listed_files':len(seen),'failures':failures,
            'scope':'Listed-file identity for this received package; new files are not covered. Intentional edits will change checksums.'}

def re_digest(value):return len(value)==64 and all(c in '0123456789abcdef' for c in value)

if __name__=='__main__':
    try:
        result=verify(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT)
        print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
    except (OSError,ValueError) as exc:print(json.dumps({'passed':False,'error':str(exc)}));sys.exit(2)
