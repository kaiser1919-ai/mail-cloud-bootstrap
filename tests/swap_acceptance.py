#!/usr/bin/env python3
"""Own16MiB swap fixture only; explicit opt-in. Never modifies real /etc/fstab."""
import argparse
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--native-only',action='store_true',help='Ephemeral CI: real mkswap/fstab, simulated kernel activation')
    group.add_argument('--confirm-test-vps',action='store_true',help='Authorised disposable VPS: actual own16MiB swapon/swapoff')
    args=parser.parse_args()
    if os.geteuid()!=0 or (args.native_only and os.environ.get('MAIL_CLOUD_EPHEMERAL_CI')!='1'):
        parser.error('root and explicit authorised test environment required')
    spec=importlib.util.spec_from_file_location('acceptance_swap',ROOT/'installer/swap_setup.py')
    swap=importlib.util.module_from_spec(spec);spec.loader.exec_module(swap)
    runtime=ROOT/'.runtime';runtime.mkdir(mode=0o700,exist_ok=True)
    if any(ch.isspace() for ch in str(ROOT)):
        parser.error('Use a test checkout path without whitespace')
    size=16*1024**2;original_command=swap.command;original_memory=swap.memory;fake_active=False
    baseline=original_memory()['SwapTotal']
    base=Path(tempfile.mkdtemp(prefix='swap-acceptance-',dir=runtime))
    file=base/'managed'/'swapfile'
    try:
        managed=base/'managed';fstab=base/'fstab'
        initial=b'# private test fixture: existing entry must survive\n/dev/fixture none swap sw 0 0\n'
        fstab.write_bytes(initial);fstab.chmod(0o600)
        def command(*argv):
            nonlocal fake_active
            # CI container is overlayfs and lacks swapon capability. Only the
            # kernel/filesystem activation boundary is simulated there; the
            # explicit VPS mode uses actual findmnt, swapon and swapoff.
            if argv[0]=='findmnt' and args.native_only:
                return 'ext4'
            if argv[0]=='swapon' and args.native_only:
                assert argv==('swapon',str(file));fake_active=True;return ''
            return original_command(*argv)
        def active(path):
            assert path==file
            return fake_active if args.native_only else str(file) in {line.split()[0] for line in Path('/proc/swaps').read_text().splitlines()[1:]}
        def memory():
            # Force the insufficient-swap branch WITHOUT disabling existing host swap.
            return {'SwapTotal':size-4096 if active(file) else 0}
        try:
            with patch.object(swap,'DIRECTORY',managed),patch.object(swap,'FSTAB',fstab),patch.object(swap,'needed_bytes',return_value=size),patch.object(swap,'MIN_SWAP',size-4096),patch.object(swap,'memory',side_effect=memory),patch.object(swap,'active',side_effect=active),patch.object(swap,'command',side_effect=command),patch('builtins.input',return_value='CREATE SWAP') as ask:
                swap.prepare_swap(2*swap.GIB)
                assert active(file) and file.stat().st_size==size and file.stat().st_mode&0o777==0o600
                first=json.loads((managed/'swap.json').read_text());once=fstab.read_bytes()
                assert first['uuid'] and first['bytes']==size and once.startswith(initial)
                assert (managed/'fstab.before-swap').read_bytes()==initial
                assert once.count(str(file).encode())==1
                swap.prepare_swap(2*swap.GIB)
                assert ask.call_count==1 and fstab.read_bytes()==once
                assert json.loads((managed/'swap.json').read_text())==first
                if args.confirm_test_vps:
                    assert original_memory()['SwapTotal']>=baseline+size-4096
                print('native_mkswap_uuid_density_permissions_fstab_backup_repeat_PASS',flush=True)
                print('kernel_swapon_PASS' if args.confirm_test_vps else 'kernel_swapon_NOT_TESTED_in_CI',flush=True)
        finally:
            if args.confirm_test_vps and file.exists() and str(file) in {line.split()[0] for line in Path('/proc/swaps').read_text().splitlines()[1:]}:
                subprocess.run(['swapoff',str(file)],check=True)
        assert original_memory()['SwapTotal']==baseline
    finally:
        if args.confirm_test_vps and str(file) in {line.split()[0] for line in Path('/proc/swaps').read_text().splitlines()[1:]}:
            raise RuntimeError('Own swap still active; fixture retained for operator inspection')
        shutil.rmtree(base)
    print('own_fixture_removed_existing_swap_unchanged',True,flush=True)


if __name__=='__main__':main()
