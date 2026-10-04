"""Byte/topology checks for private copies; this is not pnpm metadata."""
import hashlib
import os
from pathlib import Path
import shutil
import stat


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as f:
        h = hashlib.sha256()
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(value):
    p = Path(value)
    require(not p.is_absolute() and value not in ('', '.') and
            all(x not in ('', '.', '..') for x in value.split('/')), 'unsafe relative path: ' + value)
    return p


def entries(root):
    root = Path(root)
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            yield Path(directory) / name


def inventory(root, omit=()):
    root = Path(root)
    result = {}
    for p in entries(root):
        rel = str(p.relative_to(root))
        if any(rel == x or rel.startswith(x + '/') for x in omit):
            continue
        mode = p.lstat().st_mode
        if stat.S_ISLNK(mode):
            result[rel] = {'type': 'link', 'target': os.readlink(p)}
        elif stat.S_ISREG(mode):
            result[rel] = {'type': 'file', 'sha256': digest(p), 'executable': bool(mode & 0o111),
                           'bytes': p.stat().st_size}
        elif stat.S_ISDIR(mode):
            result[rel] = {'type': 'directory'}
        else:
            raise ValueError('unsupported entry: ' + rel)
    return result


def verify(root, expected, exceptions=(), exact=True):
    root = Path(root)
    actual = inventory(root)
    require(not exact or set(actual) == set(expected), 'tree topology differs: ' + str(root))
    for rel, row in expected.items():
        relative(rel)
        if rel not in exceptions:
            require(actual.get(rel) == row, 'tree entry differs: ' + rel)
    for rel, row in actual.items():
        if row['type'] == 'link':
            p = root / rel
            require(not Path(row['target']).is_absolute(), 'absolute link: ' + rel)
            require(p.resolve(strict=True).is_relative_to(root), 'external link: ' + rel)
    return actual


def copy_private(source, target, check=lambda: None):
    source, target = Path(source), Path(target)
    def copying(a, b):
        check()
        return shutil.copy2(a, b)
    shutil.copytree(source, target, symlinks=True, copy_function=copying)
    for p in [target, *entries(target)]:
        if not p.is_symlink():
            p.chmod(p.stat().st_mode | 0o200)
        if p.is_file() and not p.is_symlink():
            a, b = (source / p.relative_to(target)).stat(), p.stat()
            require((a.st_dev, a.st_ino) != (b.st_dev, b.st_ino), 'copy shares inode: ' + str(p))
