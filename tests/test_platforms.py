import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest.mock import patch
from test_bootstrap import ROOT, w, module

class Profiles(unittest.TestCase):
    def test_ubuntu_defaults(self):
        p=w.detect_platform({'ID':'ubuntu','VERSION_ID':'"24.04"'})
        self.assertEqual((p['php_version'],p['dovecot_series'],p['postfix_compat']),('8.3','2.3','3.6'))
    def test_debian_retained(self):
        p=w.detect_platform({'ID':'debian','VERSION_ID':'13'})
        self.assertEqual((p['php_version'],p['dovecot_series']),('8.4','2.4'))
    def test_reject_derivatives_and_versions(self):
        for ident,version in [('ubuntu','22.04'),('ubuntu','26.04'),('linuxmint','24.04'),('debian','12')]:
            with self.subTest(os=ident,version=version):
                with self.assertRaises(ValueError): w.detect_platform({'ID':ident,'VERSION_ID':version,'ID_LIKE':'debian'})
    def test_profile_resume_is_exact(self):
        u=w.detect_platform({'ID':'ubuntu','VERSION_ID':'24.04'})
        d=w.detect_platform({'ID':'debian','VERSION_ID':'13'})
        w.validate_resume_platform({'platform':u},u)
        with self.assertRaisesRegex(ValueError,'profile changed'): w.validate_resume_platform({'platform':u},d)
        with self.assertRaisesRegex(ValueError,'profile changed'): w.validate_resume_platform({'platform':{**u,'php_version':'8.4'}},u)
    def test_legacy_debian_only(self):
        d=w.detect_platform({'ID':'debian','VERSION_ID':'13'})
        u=w.detect_platform({'ID':'ubuntu','VERSION_ID':'24.04'})
        w.validate_resume_platform({},d)
        with self.assertRaisesRegex(ValueError,'Legacy'): w.validate_resume_platform({},u)
    def test_every_php_execution_uses_profile(self):
        for p in (ROOT/'ansible/files').glob('*.py'):
            if p.name=='mc_runtime.py': continue
            self.assertNotIn('php8.4',p.read_text(),str(p))
            self.assertNotIn('php8.3',p.read_text(),str(p))
        s=(ROOT/'ansible/tasks/runtime.yml').read_text()
        self.assertIn('/usr/sbin/php-fpm{{ php_version }}',s)
        self.assertIn('/usr/bin/php{{ php_version }}',(ROOT/'ansible/tasks/cloud.yml').read_text())
    def test_ubuntu23_is_not_24_syntax(self):
        text=(ROOT/'ansible/templates/dovecot-2.3.conf.j2').read_text()
        for value in ('ssl_cert = <','ssl_key = <','auth_username_format = %Lu','mail_location = maildir:~/Maildir','driver = ldap'):
            self.assertIn(value,text)
        for value in ('dovecot_config_version','ssl_server_cert_file','auth_allow_cleartext','%{user}'):
            self.assertNotIn(value,text)
        ldap=(ROOT/'ansible/templates/dovecot-ldap-2.3.conf.j2').read_text()
        self.assertIn('auth_bind = yes',ldap)
        self.assertIn('mail=%u',ldap)
        self.assertIn('mail=home=/srv/mail-cloud/data/mail/%$',ldap)
    def test_no_ppa_or_upgrade(self):
        code=(ROOT/'installer/wizard.py').read_text()
        self.assertIn("'universe'",code)
        self.assertNotIn('ppa:',code)
        self.assertNotIn("'dist-upgrade'",code)
        self.assertNotIn("'full-upgrade'",code)
    def test_runtime_binary_sanitized(self):
        m=module('mc_runtime',ROOT/'ansible/files/mc_runtime.py')
        for key, p in json.loads((ROOT/'platforms.json').read_text())['os_profiles'].items():
            with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
                f=Path(d)/'profile.json'; f.write_text(json.dumps(p))
                info=types.SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0)
                with patch.object(Path,'lstat',return_value=info):
                    self.assertEqual(m.php_binary(f),'/usr/bin/php'+p['php_version'])
                    f.write_text(json.dumps({**p,'php_version':'8.3;id'}))
                    with self.assertRaises(ValueError): m.php_binary(f)
                info.st_mode=stat.S_IFLNK|0o777
                with patch.object(Path,'lstat',return_value=info):
                    with self.assertRaises(ValueError): m.php_binary(f)

    def test_apparmor_targeted_not_globally_disabled(self):
        aa=(ROOT/'ansible/tasks/apparmor.yml').read_text()
        self.assertIn('/etc/apparmor.d/local/usr.sbin.slapd',aa)
        self.assertIn('/srv/mail-cloud/identity/data/** rwk',aa)
        self.assertIn('apparmor_active.stat.exists',aa)
        profile=(ROOT/'ansible/templates/apparmor-code.j2').read_text()
        self.assertIn('Collabora_Online.AppImage',profile)
        self.assertIn('userns,',profile)
        for path in list((ROOT/'ansible').rglob('*.yml'))+list((ROOT/'installer').glob('*.py')):
            self.assertNotIn('apparmor_restrict_unprivileged_userns=0',path.read_text())

    def test_local_app_copy_normalizes_restrictive_clone_modes(self):
        import yaml
        task=yaml.safe_load((ROOT/'ansible/tasks/pool.yml').read_text())[0]['ansible.builtin.copy']
        self.assertEqual(task['mode'],'u=rwX,g=rX,o=rX')
        self.assertEqual(task['directory_mode'],'0755')
        self.assertEqual(task['owner'],'root')
        self.assertEqual(task['group'],'root')
