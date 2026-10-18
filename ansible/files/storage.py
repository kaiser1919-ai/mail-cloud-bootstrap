#!/usr/bin/python3
"""Initial dense ext4 reservation with explicit interrupted-format safety stop."""
import json
import os
from pathlib import Path
import subprocess
import sys


def cmd(*a):
    return subprocess.check_output(a, text=True).strip()


def ensure_image(image, seal, size):
    if image.is_symlink() or seal.is_symlink():
        raise ValueError('Unsafe image/seal')
    if image.exists():
        if not seal.exists():
            raise ValueError('Interrupted image creation: inspect manually. NEVER automatically reformat/delete it.')
        expected = json.loads(seal.read_text())
        if image.stat().st_size != size or expected['bytes'] != size or cmd('blkid', '-s', 'UUID', '-o', 'value', str(image)) != expected['uuid']:
            raise ValueError('Image size/UUID mismatch; refusing to adopt/format')
        if image.stat().st_blocks * 512 < size:
            raise ValueError('Dense reservation lost, e.g. TRIM; inspect before further writes')
        return 'VERIFIED'
    # O_EXCL and a seal written only after successful mkfs: no destructive resume.
    fd = os.open(image, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    subprocess.run(['fallocate', '-l', str(size), str(image)], check=True)
    subprocess.run(['mkfs.ext4', '-q', '-m', '1', '-E', 'lazy_itable_init=0,lazy_journal_init=0,nodiscard', str(image)], check=True)
    subprocess.run(['fallocate', '--keep-size', '-l', str(size), str(image)], check=True)
    if image.stat().st_blocks * 512 < size:
        raise ValueError('Reservation failed')
    seal.write_text(json.dumps({'bytes': size, 'uuid': cmd('blkid', '-s', 'UUID', '-o', 'value', str(image))}) + '\n')
    seal.chmod(0o600)
    return 'CREATED'


if __name__ == '__main__':
    name = sys.argv[1]
    if name not in ('data', 'staging'):
        raise SystemExit('Bad volume name')
    try:
        print(ensure_image(Path('/srv/mail-cloud/images') / (name + '.ext4'),
                           Path('/srv/mail-cloud/state') / (name + '-storage.json'), int(sys.argv[2]) * 1024**3))
    except ValueError as e:
        raise SystemExit(str(e))
