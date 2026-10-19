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

if __name__=='__main__':unittest.main()
