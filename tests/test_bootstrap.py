import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

w = module('wizard', ROOT / 'installer/wizard.py')
f = module('fetch', ROOT / 'ansible/files/fetch.py')

class Validation(unittest.TestCase):
    def setUp(self): self.c = json.loads((ROOT / 'example.json').read_text())
    def test_defaults(self):
        c = w.validate(self.c)
        self.assertEqual(c['cloud_host'], 'disk.example.org')
        self.assertEqual(c['mail_host'], 'mail.example.org')
    def test_no_mutation(self):
        old = dict(self.c); w.validate(self.c); self.assertEqual(old, self.c)
    def test_hosts(self):
        self.c['cloud_host'] = 'portal.example.org'; self.assertEqual(w.validate(self.c)['cloud_host'], 'portal.example.org')
    def test_bad_inputs(self):
        bad = [('domain', 'x;reboot.org'), ('domain', '-a.org'), ('domain', 'x.org\n'), ('domain', 'X.org'),
               ('domain', '../a.org'), ('domain', 'localhost'), ('ipv4', '127.0.0.1'), ('ipv4', '10.0.0.1'),
               ('ipv4', '::1'), ('ipv4', '1.1.1.1;id'), ('acme_email', 'a@b.org\n'), ('acme_email', 'a\'@b.org'),
               ('users', []), ('users', ['root']), ('users', ['abuse']), ('users', ['a', 'a']), ('users', ['a;id']),
               ('users', ['../a']), ('users', ['a\n']), ('users', 'alice'), ('pool_gib', 0), ('pool_gib', True),
               ('pool_gib', '80'), ('cloud_host', 'example.org'), ('mail_host', 'disk.example.org'), ('token', 'no')]
        for k, v in bad:
            with self.subTest(key=k, value=v):
                with self.assertRaises((ValueError, TypeError)): w.validate({**self.c, k:v})
    def test_plan_no_writes_or_network(self):
        r = subprocess.run([str(ROOT / 'install.sh'), '--plan', '--config', str(ROOT / 'example.json')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['users'], ['alice', 'bob'])
    def test_bad_plan_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d) / 'input'; p.write_text('{"domain":"bad"}')
            r = subprocess.run([str(ROOT / 'install.sh'), '--plan', '--config', str(p)], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

class State(unittest.TestCase):
    def test_atomic_permissions_and_keep_secrets(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d) / 'config.json'; w.atomic_json(p, {'secret': 'fixture'})
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertEqual(w.private_load(p)['secret'], 'fixture')
            self.assertFalse(p.with_suffix('.tmp').exists())
    def test_unsafe_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d) / 'config.json'; p.write_text('{}'); p.chmod(0o644)
            with self.assertRaises(ValueError): w.private_load(p)
    def test_symlink_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d) / 'actual'; p.write_text('{}'); p.chmod(0o600)
            link = Path(d) / 'link'; link.symlink_to(p)
            with self.assertRaises(ValueError): w.private_load(link)
    def test_atomic_does_not_follow_temp_symlink(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d) / 'config.json'; victim = Path(d) / 'victim'; victim.write_text('intact')
            p.with_suffix('.tmp').symlink_to(victim)
            with self.assertRaises(FileExistsError): w.atomic_json(p, {})
            self.assertEqual(victim.read_text(), 'intact')

class Extraction(unittest.TestCase):
    def archive(self, path, kind):
        with tarfile.open(path, 'w') as t:
            x = tarfile.TarInfo('app/file')
            data = b'synthetic'
            if kind == 'traversal': x.name = 'app/../../outside'
            if kind == 'absolute': x.name = '/etc/evil'
            if kind == 'wrong': x.name = 'other/file'
            if kind == 'symlink': x.type = tarfile.SYMTYPE; x.linkname = '/etc/passwd'
            if kind == 'hardlink': x.type = tarfile.LNKTYPE; x.linkname = '/etc/passwd'
            if kind == 'fifo': x.type = tarfile.FIFOTYPE
            if kind == 'device': x.type = tarfile.CHRTYPE
            if kind == 'huge': x.size = 3*1024**3
            else: x.size = len(data) if x.isfile() else 0
            if kind == 'huge':
                # Header size bound tested via mocked TarFile, no giant fixture.
                return x
            t.addfile(x, io.BytesIO(data) if x.isfile() else None)
    def test_safe(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
            p = Path(d); self.archive(p/'a.tar','safe'); f.extract(p/'a.tar',p/'out','app')
            self.assertEqual((p/'out/app/file').read_bytes(), b'synthetic')
    def test_unsafe(self):
        for kind in ('traversal','absolute','wrong','symlink','hardlink','fifo','device'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=ROOT / 'tests') as d:
                p = Path(d); self.archive(p/'a.tar',kind)
                with self.assertRaises(ValueError): f.extract(p/'a.tar',p/'out','app')
                self.assertFalse((p/'out').exists())
    def test_huge(self):
        x = tarfile.TarInfo('app/huge'); x.size = 3*1024**3
        with patch.object(tarfile, 'open') as op:
            op.return_value.__enter__.return_value.getmembers.return_value = [x]
            with self.assertRaises(ValueError): f.extract('unused', 'unused', 'app')

class SourceContracts(unittest.TestCase):
    def test_yaml(self):
        import yaml
        for p in (ROOT/'ansible').rglob('*.yml'):
            with self.subTest(path=p): self.assertIsInstance(yaml.safe_load(p.read_text()), list)
    def test_render_templates(self):
        import jinja2
        c = w.validate(json.loads((ROOT/'example.json').read_text()))
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        profiles=json.loads((ROOT/'platforms.json').read_text())['os_profiles']
        for profile in profiles.values():
            for p in (ROOT/'ansible/templates').glob('*.j2'):
                with self.subTest(profile=profile['os_id'],template=p.name):
                    item = 'mail-redis' if p.name == 'redis.service.j2' else None
                    out = env.from_string(p.read_text()).render(c=c, nc='/srv/mail-cloud/nextcloud', suffix='dc=example,dc=org', secrets={'ldap_mail':'fixture'}, item=item, runtime_profile=profile, php_version=profile['php_version'])
                    self.assertNotIn('{{',out)
                    self.assertNotIn('{%',out)
                    if p.name == 'virtual-aliases.j2': self.assertIn(r'example\.org',out)
                    if p.name == 'mc_outbound.lua.j2': self.assertIn("['alice@example.org']=true",out)
                    if p.name == 'main.cf.j2': self.assertIn('compatibility_level = '+profile['postfix_compat'],out)
    def test_no_owner_data_or_fonts(self):
        forbidden = ['/home/', 'GITHUB_TOKEN=', 'BEGIN OPENSSH PRIVATE KEY', '@font-face']
        for folder in ('ansible','installer','docs'):
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:
                    raw=p.read_text()
                    for token in forbidden:
                        self.assertNotIn(token,raw,str(p))
        self.assertEqual(list((ROOT/'ansible').rglob('*.ttf')), [])
    def test_mfa_only_enabled_providers(self):
        m = module('mfa', ROOT/'ansible/files/mfa.py')
        good='Two-factor authentication is enabled\nEnabled providers:\n- backup_codes\n- totp\nDisabled providers:\n- other\n'
        self.assertEqual(m.enabled(good), {'backup_codes','totp'})
        self.assertEqual(m.enabled('Enabled providers:\n- backup_codes\nDisabled providers:\n- totp\n'), {'backup_codes'})
        self.assertEqual(m.enabled('totp backup_codes'), set())
    def test_safety_contracts(self):
        storage=(ROOT/'ansible/files/storage.py').read_text()
        self.assertIn('NEVER automatically reformat/delete',storage)
        self.assertIn('O_EXCL',storage)
        mail=(ROOT/'ansible/templates/main.cf.j2').read_text()
        self.assertIn('milter_default_action = tempfail',mail)
        self.assertIn('reject_unauth_destination',mail)
        self.assertIn('smtpd_sasl_auth_enable = no',mail)
        ngx=(ROOT/'ansible/templates/nginx.conf.j2').read_text()
        self.assertIn('location = /custom_apps/richdocumentscode/proxy.php',ngx)
        self.assertIn('mjs',ngx)
        self.assertIn('mail-cloud-access.conf',ngx)
        for name in ('redis.service.j2','office.service.j2'):
            self.assertIn('BindsTo=',(ROOT/'ansible/templates'/name).read_text())
        self.assertIn('127.0.0.1:6380',(ROOT/'ansible/templates/rspamd-redis.conf.j2').read_text())
        self.assertIn('loopback',(ROOT/'ansible/templates/office.service.j2').read_text())


class StorageResume(unittest.TestCase):
    def test_existing_sealed_volume_is_not_formatted(self):
        m = module('storage', ROOT/'ansible/files/storage.py')
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d); image=p/'image'; image.write_bytes(b'x'*4096)
            seal=p/'seal'; seal.write_text(json.dumps({'bytes':4096,'uuid':'fixture'}))
            with patch.object(m,'cmd',return_value='fixture'),patch.object(m.subprocess,'run') as runner:
                self.assertEqual(m.ensure_image(image,seal,4096),'VERIFIED')
                runner.assert_not_called()
    def test_partial_image_never_formats(self):
        m=module('storage', ROOT/'ansible/files/storage.py')
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d); image=p/'image'; image.write_bytes(b'preserve')
            with patch.object(m.subprocess,'run') as runner:
                with self.assertRaisesRegex(ValueError,'NEVER'): m.ensure_image(image,p/'absent',4096)
                runner.assert_not_called()
            self.assertEqual(image.read_bytes(),b'preserve')
    def test_mismatch_stops_before_commands(self):
        m=module('storage', ROOT/'ansible/files/storage.py')
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d); image=p/'image'; image.write_bytes(b'preserve'); seal=p/'seal'
            seal.write_text(json.dumps({'bytes':4096,'uuid':'fixture'}))
            with patch.object(m.subprocess,'run') as runner:
                with self.assertRaisesRegex(ValueError,'mismatch'): m.ensure_image(image,seal,4096)
                runner.assert_not_called()
    def test_symlink_volume_stops(self):
        m=module('storage', ROOT/'ansible/files/storage.py')
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d); image=p/'image'; image.symlink_to(p/'nonexistent')
            with self.assertRaisesRegex(ValueError,'Unsafe'): m.ensure_image(image,p/'seal',4096)

class Preflight(unittest.TestCase):
    def setUp(self):
        self.c=w.validate(json.loads((ROOT/'example.json').read_text()))
        self.original_read=Path.read_text
        self.release='ID=debian\nVERSION_ID="13"\n'
    def host(self, path):
        if str(path)=='/etc/os-release': return self.release
        if str(path)=='/proc/meminfo': return 'MemTotal: 2048000 kB\nSwapTotal: 4194304 kB\n'
        return self.original_read(path)
    def test_foreign_config_rejected(self):
        with patch.object(Path,'read_text',lambda p: self.host(p)),patch.object(Path,'is_dir',return_value=True),patch.object(Path,'exists',lambda p: str(p)=='/etc/postfix'),patch.object(Path,'is_symlink',return_value=False):
            with self.assertRaisesRegex(ValueError,'Not a clean host'): w.preflight(self.c,False)
    def test_wrong_os_rejected(self):
        self.release='ID=ubuntu\nVERSION_ID=22.04\n'
        with patch.object(Path,'read_text',lambda p: self.host(p)):
            with self.assertRaisesRegex(ValueError,'Only Ubuntu'): w.preflight(self.c,False)
    def test_occupied_port_rejected(self):
        with patch.object(Path,'read_text',lambda p: self.host(p)),patch.object(Path,'is_dir',return_value=True),patch.object(Path,'exists',return_value=False),patch.object(Path,'is_symlink',return_value=False),patch.object(w.socket,'socket') as sock:
            sock.return_value.__enter__.return_value.bind.side_effect=OSError('busy')
            with self.assertRaisesRegex(ValueError,'occupied'): w.preflight(self.c,False)
    def test_disk_shortage_on_resume(self):
        with patch.object(Path,'read_text',lambda p: self.host(p)),patch.object(Path,'is_dir',return_value=True),patch.object(w.shutil,'disk_usage') as usage:
            usage.return_value.free=1
            with self.assertRaisesRegex(ValueError,'>=5 GiB'): w.preflight(self.c,True)

if __name__ == '__main__': unittest.main()
