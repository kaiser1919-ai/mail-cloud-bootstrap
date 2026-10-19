import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

w = load('wizard_pressure', 'installer/wizard.py')
p = load('pressure', 'ansible/files/pressure_guard.py')
f = load('fetch_pressure', 'ansible/files/fetch.py')

class Pressure(unittest.TestCase):
    def test_production_defaults_unchanged(self):
        self.assertEqual(w.disk_requirement(80,False),105*w.GIB)
        self.assertEqual(w.disk_requirement(80,True),5*w.GIB)
    def test_explicit_test_limits(self):
        self.assertEqual(w.disk_requirement(80,False,True),88*w.GIB)
        self.assertEqual(w.disk_requirement(80,True,True),2*w.GIB)
    def test_mode_never_changes_on_resume(self):
        w.validate_test_mode({},False)
        w.validate_test_mode({'test_low_headroom':True},True)
        for previous, requested in (({},True),({'test_low_headroom':True},False),({'test_low_headroom':1},True)):
            with self.assertRaises(ValueError):w.validate_test_mode(previous,requested)
    def test_ldap_runtime_precedes_validation(self):
        import yaml
        tasks=yaml.safe_load((ROOT/'ansible/tasks/identity.yml').read_text())
        runtime=next(i for i,t in enumerate(tasks) if t.get('ansible.builtin.file',{}).get('path')=='/run/mail-cloud-ldap')
        configure=next(i for i,t in enumerate(tasks) if 'identity.py configure' in t.get('ansible.builtin.script',''))
        self.assertLess(runtime,configure)
    def test_pressure_boundary(self):
        memory={'MemAvailable':250*1024,'SwapFree':512*1024}
        self.assertEqual(p.check(meminfo=memory,free=2*p.GIB)['root_free_bytes'],2*p.GIB)
        for key in memory:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'Pressure stop'):
                p.check(meminfo={**memory,key:memory[key]-1},free=2*p.GIB)
        with self.assertRaisesRegex(ValueError,'Pressure stop'):p.check(meminfo=memory,free=2*p.GIB-1)
    def test_download_budget_includes_system_reserve(self):
        with patch.object(f.shutil,'disk_usage') as usage:
            usage.return_value.free=3*p.GIB
            f.require_space('/synthetic',p.GIB)
            with self.assertRaisesRegex(ValueError,'Pressure stop'):f.require_space('/synthetic',p.GIB+1)
    def test_guards_every_phase(self):
        s=(ROOT/'ansible/site.yml').read_text()
        for phase in ('packages','storage','apparmor','identity','runtime','tls','cloud','mail','office','pool'):
            self.assertIn('tasks/guard.yml\n        - ansible.builtin.import_tasks: tasks/'+phase+'.yml',s)

class ArchiveLinks(unittest.TestCase):
    def members(self, links):
        import tarfile
        file=tarfile.TarInfo('app/license');file.size=2
        members=[file]
        for name,target in links:
            m=tarfile.TarInfo(name);m.type=tarfile.SYMTYPE;m.linkname=target;members.append(m)
        return members
    def test_internal_file_and_chain(self):
        f.validate_members(self.members([('app/map','license'),('app/map2','map')]),'app')
    def test_unsafe_links(self):
        for links in ([('app/x','/etc/passwd')],[('app/x','../../etc/passwd')],[('app/x','missing')],[('app/x','y'),('app/y','x')],[('app/x','license'),('app/x/child','../license')]):
            with self.subTest(links=links),self.assertRaises(ValueError): f.validate_members(self.members(links),'app')
    def test_duplicate_members(self):
        members=self.members([])
        with self.assertRaisesRegex(ValueError,'Duplicate'):f.validate_members(members+members,'app')
    def test_internal_links_extract_without_escape(self):
        import io,tarfile,tempfile
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as work:
            work=Path(work);archive=work/'fixture.tar'
            members=self.members([('app/map','license'),('app/map2','map')])
            with tarfile.open(archive,'w') as t:
                for m in members:t.addfile(m,io.BytesIO(b'ok') if m.isfile() else None)
            f.extract(archive,work/'out','app')
            self.assertEqual((work/'out/app/map2').read_bytes(),b'ok')

class PublicDNS(unittest.TestCase):
    def test_explicit_public_query_not_local_stub(self):
        dns=load('public_dns','ansible/files/dns.py')
        with patch.object(dns.subprocess,'check_output',return_value='1.2.3.4\n') as lookup:
            self.assertEqual(dns.dig('disk.example.org','A'),['1.2.3.4'])
            self.assertIn('@1.1.1.1',lookup.call_args.args[0])
    def test_public_fallback_and_failure(self):
        dns=load('public_dns_fallback','ansible/files/dns.py')
        error=dns.subprocess.CalledProcessError(9,['dig'])
        with patch.object(dns.subprocess,'check_output',side_effect=[error,'1.2.3.4\n']) as lookup:
            self.assertEqual(dns.dig('disk.example.org','A'),['1.2.3.4'])
            self.assertIn('@8.8.8.8',lookup.call_args.args[0])
        with patch.object(dns.subprocess,'check_output',side_effect=error),self.assertRaisesRegex(SystemExit,'Public DNS'):
            dns.dig('disk.example.org','A')

if __name__=='__main__':unittest.main()
