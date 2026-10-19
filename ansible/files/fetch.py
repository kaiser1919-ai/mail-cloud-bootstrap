#!/usr/bin/python3
"""Pinned HTTPS download with bounded safe extraction. No shell/tar path escape."""
import hashlib
import os
import posixpath
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse


def require_space(path, extra=0):
    if shutil.disk_usage(path).free < 2 * 1024**3 + extra:
        raise ValueError('Pressure stop: archive operation would consume the 2 GiB system reserve')


def validate_members(members, root):
    if not 1 <= len(members) <= 50000 or sum(m.size for m in members) > 2 * 1024**3:
        raise ValueError('Archive bounds exceeded')
    entries = {}
    for m in members:
        p = PurePosixPath(m.name)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != root or not (m.isfile() or m.isdir() or m.issym()):
            raise ValueError('Unsafe archive member')
        name = str(p)
        if name in entries:
            raise ValueError('Duplicate archive member')
        entries[name] = m
    for name, m in entries.items():
        # No archive member may be written through a file or link ancestor.
        for parent in PurePosixPath(name).parents:
            if str(parent) in entries and not entries[str(parent)].isdir():
                raise ValueError('Unsafe archive ancestor')
        if not m.issym():
            continue
        # Upstream includes relative licence links, occasionally in chains.
        # Resolve only against this validated member table, never the host FS.
        current, seen = name, set()
        while True:
            if current in seen or len(seen) >= 32 or current not in entries:
                raise ValueError('Cyclic, dangling or excessive archive link')
            seen.add(current)
            target = entries[current]
            for parent in PurePosixPath(current).parents:
                if str(parent) in entries and not entries[str(parent)].isdir():
                    raise ValueError('Unsafe link ancestor')
            if not target.issym():
                if not target.isfile():
                    raise ValueError('Archive link must end at a regular file')
                break
            if PurePosixPath(target.linkname).is_absolute():
                raise ValueError('Absolute archive link')
            current = posixpath.normpath(posixpath.join(str(PurePosixPath(current).parent), target.linkname))
            if not current.startswith(root + '/'):
                raise ValueError('Archive link escapes application root')


def normalize_fresh_code(root):
    # data_filter intentionally ignores archive directory modes; umask077
    # would otherwise leave a valid root extraction unreadable to PHP/nginx.
    for directory, dirs, files in os.walk(root, followlinks=False):
        Path(directory).chmod(0o755)
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o755 if path.stat().st_mode & 0o100 else 0o644)


def repair_core_directories(root=Path('/srv/mail-cloud/nextcloud')):
    # Compatibility with interrupted preview extractions. Only known PUBLIC
    # core-code directories: NEVER recurse through config/custom_apps/data
    # or chmod existing files (config.php contains installation secrets).
    if root.is_symlink() or not (root / 'version.php').is_file():
        raise ValueError('Not an installer core tree')
    root.chmod(0o755)
    for name in ('3rdparty', 'apps', 'core', 'dist', 'lib', 'ocs', 'ocs-provider', 'ocm-provider', 'resources', 'updater'):
        top = root / name
        if top.is_symlink():
            raise ValueError('Unexpected core directory symlink')
        if not top.exists():
            continue
        for directory, dirs, files in os.walk(top, followlinks=False):
            Path(directory).chmod(0o755)
            if any((Path(directory) / child).is_symlink() for child in dirs):
                raise ValueError('Unexpected nested core directory symlink')


def extract(archive, destination, root):
    with tarfile.open(archive) as t:
        members = t.getmembers()
        validate_members(members, root)
        # Account for filesystem blocks/inodes, not just logical tar sizes.
        require_space(archive.parent, sum(((m.size + 4095) // 4096 + 1) * 4096 for m in members))
        t.extractall(destination, filter='data')
        normalize_fresh_code(Path(destination) / root)


def main():
    url, root, sha, dest = sys.argv[1:]
    host = urllib.parse.urlparse(url)
    if host.scheme != 'https' or host.hostname not in ('download.nextcloud.com', 'github.com'):
        raise ValueError('Publisher not allowed')
    dest = Path(dest)
    if dest.exists():
        raise ValueError('Destination already exists; do not replace installed code')
    base = Path('/srv/mail-cloud/downloads')
    require_space(base, 1000000000)
    with tempfile.TemporaryDirectory(dir=base) as work:
        work = Path(work)
        archive = work / 'package.tar'
        subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error', '--http1.1', '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '20', '--speed-time', '90', '--speed-limit', '1024', '--max-time', '1800', '--retry', '2', '--max-filesize', '1000000000', '-o', str(archive), url], check=True)
        if sha != 'signature':
            with archive.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            if digest != sha:
                raise ValueError('Checksum mismatch')
        extract(archive, work / 'extract', root)
        if sha == 'signature' and not (work / 'extract' / root / 'appinfo/signature.json').is_file():
            raise ValueError('Missing Nextcloud application signature')
        # Signature MUST subsequently pass occ integrity:check-app before enable.
        os.rename(work / 'extract' / root, dest)


if __name__ == '__main__':
    if sys.argv[1:] == ['--repair-core-directories']:
        repair_core_directories()
    else:
        main()
