import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wizard_ux',ROOT/'installer/wizard.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
s=w.prepare_swap.__globals__
import swap_setup as swap

class WizardUX(unittest.TestCase):
    def test_explicit_mailbox_count_and_logins(self):
        with patch('builtins.input',side_effect=['2','alice','bob']) as ask:
            self.assertEqual(w.ask_mailboxes(),['alice','bob'])
            self.assertEqual(ask.call_count,3)
    def test_invalid_count_logins_and_duplicates(self):
        for answers in [['0'],['21'],['-1'],['2;id'],['1','root'],['1','alice@example.org'],['1','a;id'],['2','alice','alice']]:
            with self.subTest(answers=answers),patch('builtins.input',side_effect=answers):
                with self.assertRaises(ValueError):w.ask_mailboxes()
    def test_each_credential_location_without_passwords(self):
        c=w.validate(json.loads((ROOT/'example.json').read_text()));out=io.StringIO()
        with contextlib.redirect_stdout(out):w.credential_locations(c,Path('/root-private/config.json'))
        for user in c['users']:
            self.assertIn(user+'@'+c['domain'],out.getvalue())
            self.assertIn('passwords["'+user+'"]',out.getvalue())
        self.assertIn('/root-private/config.json',out.getvalue())
        self.assertIn('secrets["recovery"]',out.getvalue())
    def test_plan_does_not_prepare_swap(self):
        with patch.object(w,'prepare_swap') as prepare,patch.object(w.sys,'argv',['wizard','--plan','--config',str(ROOT/'example.json')]),contextlib.redirect_stdout(io.StringIO()):w.main()
        prepare.assert_not_called()
    def test_readonly_modes_do_not_offer_swap(self):
        source=(ROOT/'installer/wizard.py').read_text()
        self.assertIn('require_swap=not install',source)
        self.assertIn("if install:\n        prepare_swap",source)
        self.assertIn("if install:\n        credential_locations",source)
    def test_documentation_first_screen(self):
        for name,heading in [('README.md','## Minimum server requirements'),('README.ru.md','## Минимальные требования к серверу')]:
            source=(ROOT/name).read_text()
            self.assertLess(source.index('bash install.sh'),source.index(heading))
            self.assertLess(source.index(heading),source.index('## Stack' if name=='README.md' else '## Что внутри'))

class SwapSetup(unittest.TestCase):
    def test_add_only_deficit_in_gib(self):
        for total,amount in [(0,4),(swap.GIB,3),(3*swap.GIB,1),(swap.MIN_SWAP,0),(8*swap.GIB,0)]:
            self.assertEqual(swap.needed_bytes(total),amount*swap.GIB)
    def test_sufficient_existing_swap_no_writes_or_prompt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'DIRECTORY',Path(d)/'absent'),patch.object(swap,'memory',return_value={'SwapTotal':4*swap.GIB}),patch.object(swap,'command') as command,patch('builtins.input') as ask,contextlib.redirect_stdout(io.StringIO()):
            swap.prepare_swap(105*swap.GIB);ask.assert_not_called();command.assert_not_called()
            self.assertFalse((Path(d)/'absent').exists())
    def test_decline_no_file_or_fstab_change(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'DIRECTORY',Path(d)/'absent'),patch.object(swap,'memory',return_value={'SwapTotal':0}),patch.object(swap,'checked'),patch.object(swap,'command',return_value='ext4'),patch.object(swap.shutil,'which',return_value='native'),patch.object(swap.shutil,'disk_usage') as disk,patch('builtins.input',return_value='NO'),contextlib.redirect_stdout(io.StringIO()):
            disk.return_value.free=1000*swap.GIB
            with self.assertRaisesRegex(ValueError,'declined'):swap.prepare_swap(105*swap.GIB)
            self.assertFalse((Path(d)/'absent').exists())
    def test_disk_reserve_is_not_consumed_by_swap(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'DIRECTORY',Path(d)/'absent'),patch.object(swap,'memory',return_value={'SwapTotal':0}),patch.object(swap,'checked'),patch.object(swap,'command',return_value='ext4'),patch.object(swap.shutil,'which',return_value='native'),patch.object(swap.shutil,'disk_usage') as disk,patch('builtins.input') as ask,contextlib.redirect_stdout(io.StringIO()):
            disk.return_value.free=108*swap.GIB
            with self.assertRaisesRegex(ValueError,'Insufficient disk'):swap.prepare_swap(105*swap.GIB)
            ask.assert_not_called()
    def test_unsupported_filesystem_does_not_write(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'DIRECTORY',Path(d)/'absent'),patch.object(swap,'memory',return_value={'SwapTotal':0}),patch.object(swap,'checked'),patch.object(swap,'command',return_value='btrfs'),patch.object(swap.shutil,'which',return_value='native'),patch('builtins.input') as ask,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'ext4/XFS'):swap.prepare_swap(105*swap.GIB)
            ask.assert_not_called()
    def test_exclusive_creation_does_not_overwrite_or_follow_symlink(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d);victim=p/'victim';victim.write_bytes(b'preserve');link=p/'link';link.symlink_to(victim)
            for target in [victim,link]:
                with self.assertRaises(FileExistsError):swap.exclusive_write(target,b'new')
            self.assertEqual(victim.read_bytes(),b'preserve')
    def test_fstab_preserves_content_backup_and_deduplicates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'checked',side_effect=lambda p,**kw:p.lstat()),patch.object(swap.os,'chown'):
            p=Path(d);fstab=p/'fstab';initial=b'# keep\n/dev/old none swap sw 0 0\n';fstab.write_bytes(initial)
            with patch.object(swap,'DIRECTORY',p),patch.object(swap,'FSTAB',fstab):
                swap.fstab_update(p/'swapfile');once=fstab.read_bytes();swap.fstab_update(p/'swapfile')
                self.assertEqual(fstab.read_bytes(),once)
                self.assertEqual((p/'fstab.before-swap').read_bytes(),initial)
                self.assertTrue(once.startswith(initial))
                self.assertEqual(once.count(str(p/'swapfile').encode()),1)
    def test_fstab_conflict_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'checked',side_effect=lambda p,**kw:p.lstat()),patch.object(swap.os,'chown'):
            p=Path(d);fstab=p/'fstab';content=f'{p}/swapfile none swap pri=10 0 0\n'.encode();fstab.write_bytes(content)
            with patch.object(swap,'DIRECTORY',p),patch.object(swap,'FSTAB',fstab):
                with self.assertRaisesRegex(ValueError,'differs'):swap.fstab_update(p/'swapfile')
                self.assertEqual(fstab.read_bytes(),content)
    def test_sparse_or_replaced_swap_refuses_before_commands(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'checked',side_effect=lambda p,**kw:p.lstat()),patch.object(swap,'command') as command:
            p=Path(d);file=p/'swapfile';file.write_bytes(b'own');manifest=p/'swap.json';manifest.write_text(json.dumps({'version':1,'bytes':4096,'device':file.stat().st_dev,'inode':file.stat().st_ino}))
            with self.assertRaisesRegex(ValueError,'mismatch'):swap.verify_file(file,manifest)
            command.assert_not_called()
    def test_partial_file_not_reformatted(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d,patch.object(swap,'DIRECTORY',Path(d)),patch.object(swap,'checked',side_effect=lambda p,**kw:p.lstat()),patch.object(swap,'memory',return_value={'SwapTotal':0}),patch.object(swap,'command') as command,contextlib.redirect_stdout(io.StringIO()):
            file=Path(d)/'swapfile';file.write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError,'Interrupted/unsealed'):swap.prepare_swap(0)
            command.assert_not_called();self.assertEqual(file.read_bytes(),b'preserve')
