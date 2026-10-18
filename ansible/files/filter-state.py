#!/usr/bin/python3
import os
from pathlib import Path
import shutil

native = Path('/var/lib/rspamd')
target = Path('/srv/mail-cloud/data/rspamd')
snapshot = Path('/srv/mail-cloud/state/rspamd-original')
if native.is_symlink():
    if native.resolve() != target:
        raise SystemExit('Unexpected filter state symlink')
elif native.exists():
    if snapshot.exists():
        raise SystemExit('Conflicting filter state; do not overwrite either copy')
    shutil.copytree(native, target, dirs_exist_ok=True)
    os.rename(native, snapshot)
    native.symlink_to(target, target_is_directory=True)
elif snapshot.is_dir() and target.is_dir():
    # Interrupted after rename; no daemon has been enabled yet.
    native.symlink_to(target, target_is_directory=True)
else:
    raise SystemExit('Missing native filter state; inspect package installation')
