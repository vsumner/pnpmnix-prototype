"""Deterministic SHA256(pkg-id UTF8) prefix partitions, capped at64 archives."""
import hashlib

def assign(package_ids, limit=64):
    ids = sorted(package_ids)
    assert limit > 0 and len(ids) == len(set(ids))
    rows = [(pkg, format(int.from_bytes(hashlib.sha256(pkg.encode('utf8')).digest(), 'big'), '0256b'))
            for pkg in ids]
    groups = {}
    def split(rows, prefix=''):
        if not rows: return
        if len(rows) <= limit:
            groups[f'b{len(prefix)}-{int(prefix or "0", 2):x}'] = [pkg for pkg, _ in rows]
            return
        assert len(prefix) < 256, 'unpartitionable SHA256 collision'
        for bit in '01':
            split([row for row in rows if row[1][len(prefix)] == bit], prefix + bit)
    split(rows)
    assert sorted(pkg for group in groups.values() for pkg in group) == ids
    assert all(0 < len(group) <= limit for group in groups.values())
    return dict(sorted(groups.items()))
