"""Verify Nix-realized exact raw archives, then retain an immutable path map."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir()
started = time.monotonic(); total = 0; hashes = {}
for pkg_id, value in spec['archive_map'].items():
    archive = Path(value['archive'])
    with archive.open('rb') as file: actual = 'sha512-' + base64.b64encode(hashlib.file_digest(file, 'sha512').digest()).decode()
    assert actual == value['integrity'], pkg_id
    size = archive.stat().st_size; total += size
    hashes[pkg_id] = {'bytes': size, 'archive': str(archive), 'integrity': actual}
(out / 'archive-map.json').write_text(json.dumps(spec['archive_map'], sort_keys=True, indent=2) + '\n')
(out / 'acquisition.json').write_text(json.dumps({'passed': True, 'archives': len(hashes),
    'raw_bytes': total, 'verification_seconds': time.monotonic() - started, 'hashes': hashes,
    'method': 'per-package Nix fetchurl flat SHA512; no package store or host package fetcher',
    'all_locked_registry_records': True}, indent=2) + '\n')
print(json.dumps({'archives_verified': len(hashes), 'raw_bytes': total, 'verification_seconds': time.monotonic() - started}), flush=True)
