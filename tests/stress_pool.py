#!/usr/bin/env python3
"""Opt-in real disk fixture test. No mail sent, no existing files changed.
Run as root only on an authorised TEST VPS after mounting the data pool.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pressure', ROOT / 'ansible/files/pressure_guard.py')
pressure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pressure)
GIB = 1024**3
MIB = 1024**2


def run(gib):
    pool = Path('/srv/mail-cloud/data')
    if os.geteuid() != 0 or not pool.is_mount() or pool.is_symlink():
        raise ValueError('Requires root and the mounted project test pool')
    state = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())
    if state.get('test_low_headroom') is not True:
        raise ValueError('Not a persisted low-headroom TEST installation')
    pressure.check()
    started = time.monotonic()
    written = 0
    # Only this uniquely created directory is ever removed, including on failure.
    with tempfile.TemporaryDirectory(prefix='.stress-fixture-', dir=pool) as work:
        os.chmod(work, 0o700)
        block = os.urandom(MIB)
        expected = hashlib.sha256()
        path = Path(work) / 'payload'
        with path.open('xb') as f:
            for _ in range(gib * 1024):
                if written % (64 * MIB) == 0:
                    pressure.check()
                    if shutil.disk_usage(pool).free < GIB + 64 * MIB:
                        break
                f.write(block)
                expected.update(block)
                written += MIB
            f.flush()
            os.fsync(f.fileno())
        if not written:
            raise ValueError('Pool reserve reached before any fixture write')
        actual = hashlib.sha256()
        with path.open('rb') as f:
            while data := f.read(8 * MIB):
                pressure.check()
                actual.update(data)
        if actual.digest() != expected.digest():
            raise ValueError('Fixture readback checksum mismatch')
        result = {'bytes_written_read_verified': written, 'seconds': round(time.monotonic() - started, 2), 'requested_gib': gib, 'pool_free_at_peak': shutil.disk_usage(pool).free, **pressure.check()}
    result['fixture_cleanup'] = not Path(work).exists()
    result['pool_free_after_cleanup'] = shutil.disk_usage(pool).free
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gib', type=int, default=2)
    ap.add_argument('--confirm-test-vps', action='store_true', required=True)
    args = ap.parse_args()
    if not 1 <= args.gib <= 80:
        ap.error('--gib must be 1..80; 1 GiB pool reserve is always retained')
    run(args.gib)
