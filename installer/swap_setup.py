"""Opt-in, additive swap preparation; never reformats/adopts an existing file."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

GIB = 1024**3
MIN_SWAP = 4095 * 1024**2
DIRECTORY = Path('/var/lib/mail-cloud-installer')
FSTAB = Path('/etc/fstab')


def memory():
    return {r.split(':', 1)[0]: int(r.split()[1]) * 1024
            for r in Path('/proc/meminfo').read_text().splitlines()
            if r.startswith(('MemTotal:', 'SwapTotal:'))}


def needed_bytes(total):
    return 0 if total >= MIN_SWAP else ((4 * GIB - total + GIB - 1) // GIB) * GIB


def checked(path, directory=False, private=False):
    s = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(s.st_mode) or s.st_uid != 0 or s.st_mode & (0o077 if private else 0o022):
        raise ValueError(f'Unsafe swap preparation path: {path}')
    return s


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def exclusive_write(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def fstab_update(swapfile):
    before = checked(FSTAB)
    if before.st_size > 1024**2:
        raise ValueError('Unexpectedly large fstab; inspect manually')
    data = FSTAB.read_bytes()
    entry = f'{swapfile} none swap sw,nofail 0 0'
    entries = [r.split() for r in data.decode().splitlines()
               if r.strip() and not r.lstrip().startswith('#') and r.split()[0] == str(swapfile)]
    if entries:
        if entries != [entry.split()]:
            raise ValueError('Existing managed swap fstab entry differs; refusing to overwrite')
        return
    backup = DIRECTORY / 'fstab.before-swap'
    if not backup.exists():
        exclusive_write(backup, data)
    else:
        checked(backup, private=True)
    tmp = FSTAB.with_name('.mail-cloud-fstab.tmp')
    exclusive_write(tmp, data + (b'\n' if data and not data.endswith(b'\n') else b'') +
                    ('# mail-cloud-office: additive managed swap\n' + entry + '\n').encode())
    os.chmod(tmp, stat.S_IMODE(before.st_mode))
    os.chown(tmp, before.st_uid, before.st_gid)
    now = checked(FSTAB)
    if (now.st_dev, now.st_ino, now.st_mtime_ns, now.st_size) != (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size):
        raise ValueError('fstab changed concurrently; inspect temporary file and rerun')
    os.replace(tmp, FSTAB)
    fd = os.open(FSTAB.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def active(swapfile):
    return str(swapfile) in {line.split()[0] for line in Path('/proc/swaps').read_text().splitlines()[1:]}


def verify_file(swapfile, manifest):
    checked(manifest, private=True)
    state = json.loads(manifest.read_text())
    s = checked(swapfile, private=True)
    if (state.get('version') != 1 or type(state.get('bytes')) is not int or
            not 0 < state['bytes'] <= 4 * GIB or
            (s.st_dev, s.st_ino, s.st_size) != (state.get('device'), state.get('inode'), state['bytes']) or
            s.st_nlink != 1 or s.st_blocks * 512 < s.st_size):
        raise ValueError('Managed swap identity/size/density mismatch; no reformat or deletion')
    if command('blkid', '-p', '-s', 'TYPE', '-o', 'value', str(swapfile)) != 'swap' or command('blkid', '-p', '-s', 'UUID', '-o', 'value', str(swapfile)) != state.get('uuid'):
        raise ValueError('Managed swap signature mismatch; no reformat or deletion')


def prepare_swap(pool_free_requirement):
    info = memory()
    print('SWAP / Подкачка: disk-backed memory reserve helps Office survive RAM peaks; '
          'it is slower than RAM, not a RAM upgrade. / Резерв на диске снижает риск OOM, но не заменяет RAM.')
    print(f"Active SWAP: {info['SwapTotal'] / GIB:.2f} GiB; required: 4 GiB. / Требуется 4 ГиБ.")
    swapfile = DIRECTORY / 'swapfile'
    manifest = DIRECTORY / 'swap.json'
    managed = DIRECTORY.exists() or DIRECTORY.is_symlink()
    if managed:
        checked(DIRECTORY, directory=True, private=True)
        if swapfile.exists() or swapfile.is_symlink() or manifest.exists() or manifest.is_symlink():
            if not swapfile.exists() or not manifest.exists():
                raise ValueError(f'Interrupted/unsealed swap at {DIRECTORY}; inspect manually. No automatic deletion/reformat.')
            verify_file(swapfile, manifest)
            if not active(swapfile):
                command('swapon', str(swapfile))
            fstab_update(swapfile)
            if memory()['SwapTotal'] < MIN_SWAP:
                raise ValueError('Managed swap is active but total is insufficient; inspect other swap manually')
            print(f'Managed SWAP verified; no recreation: {swapfile}')
            return
    amount = needed_bytes(info['SwapTotal'])
    if not amount:
        print('Existing SWAP is sufficient; unchanged. / Имеющейся подкачки достаточно, ничего не меняю.')
        return
    for tool in ('findmnt', 'mkswap', 'swapon', 'blkid'):
        if not shutil.which(tool):
            raise ValueError(f'Install native util-linux/mount first: missing {tool}')
    for parent in (DIRECTORY.parent.parent, DIRECTORY.parent):
        checked(parent, directory=True)
    fs = command('findmnt', '-n', '-o', 'FSTYPE', '--target', str(DIRECTORY.parent))
    if fs not in ('ext4', 'xfs'):
        raise ValueError('Automatic SWAP supports ext4/XFS only; prepare 4GiB swap with filesystem-specific tools and rerun')
    checked(FSTAB)
    # Preserve the full original pool reserve, in addition to new swap allocation.
    same_device = os.stat('/srv').st_dev == os.stat(DIRECTORY.parent).st_dev
    minimum = pool_free_requirement if same_device else 5 * GIB
    if shutil.disk_usage(DIRECTORY.parent).free < minimum + amount:
        raise ValueError('Insufficient disk for additional SWAP plus unchanged system/pool reserve')
    print(f'Create additional {amount // GIB} GiB at {swapfile}, root-only0600; keep existing swap. '
          f'Add one fstab entry for reboot; backup: {DIRECTORY / "fstab.before-swap"}.')
    if input('Создать SWAP? / Create SWAP? Type CREATE SWAP to agree: ').strip() != 'CREATE SWAP':
        raise ValueError('SWAP creation declined; no swap/fstab changes. Prepare 4GiB swap and rerun.')
    DIRECTORY.mkdir(mode=0o700, exist_ok=True)
    checked(DIRECTORY, directory=True, private=True)
    # Write actual zero blocks (not truncate/fallocate/CoW); never touch an existing file.
    fd = os.open(swapfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        block = bytes(1024**2)
        for _ in range(amount // len(block)):
            f.write(block)
        f.flush()
        os.fsync(f.fileno())
    command('mkswap', str(swapfile))
    uuid = command('blkid', '-p', '-s', 'UUID', '-o', 'value', str(swapfile))
    s = checked(swapfile, private=True)
    exclusive_write(manifest, json.dumps({'version': 1, 'device': s.st_dev, 'inode': s.st_ino,
                                         'bytes': amount, 'uuid': uuid}).encode())
    verify_file(swapfile, manifest)
    command('swapon', str(swapfile))
    if not active(swapfile) or memory()['SwapTotal'] < MIN_SWAP:
        raise ValueError('SWAP activation did not meet requirements; inspect managed file, no automatic deletion')
    fstab_update(swapfile)
    print(f'SWAP ready and persistent / SWAP готов: {swapfile}; backup: {DIRECTORY / "fstab.before-swap"}')
