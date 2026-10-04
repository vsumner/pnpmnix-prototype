"""Pack verified raw files into bounded sandbox inputs without changing bytes."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir()
started = time.monotonic(); receipt = {}; total = 0
for pkg_id, value in spec['archive_group'].items():
    source = Path(value['archive']); target = out / value['storeName']
    shutil.copyfile(source, target)
    with target.open('rb') as file:
        actual = 'sha512-' + base64.b64encode(hashlib.file_digest(file, 'sha512').digest()).decode()
    assert actual == value['integrity'], pkg_id
    size = target.stat().st_size; total += size
    receipt[pkg_id] = {'file': target.name, 'bytes': size, 'integrity': actual}
(out / 'group.json').write_text(json.dumps({'passed': True, 'archives': receipt,
    'raw_bytes': total, 'copy_and_verify_seconds': time.monotonic() - started}, indent=2) + '\n')
print(json.dumps({'group_count': len(receipt), 'bytes': total}), flush=True)
