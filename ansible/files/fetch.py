#!/usr/bin/python3
"""Pinned HTTPS download with bounded safe extraction. No shell/tar path escape."""
import hashlib
import os
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


def extract(archive, destination, root):
    with tarfile.open(archive) as t:
        members = t.getmembers()
        if not 1 <= len(members) <= 50000 or sum(m.size for m in members) > 2 * 1024**3:
            raise ValueError('Archive bounds exceeded')
        for m in members:
            p = PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != root or not (m.isfile() or m.isdir()):
                raise ValueError('Unsafe archive member')
        # Account for filesystem blocks/inodes, not just logical tar sizes.
        require_space(archive.parent, sum(((m.size + 4095) // 4096 + 1) * 4096 for m in members))
        t.extractall(destination, filter='data')


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
    main()
