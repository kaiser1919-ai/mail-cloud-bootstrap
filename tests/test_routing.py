import socket
import unittest
from unittest.mock import patch
import yaml
from test_bootstrap import ROOT,module

health=module('health_routing',ROOT/'ansible/files/health.py')

class LocalRouting(unittest.TestCase):
    def rows(self,*addresses):
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(a,443)) for a in addresses]
    def test_loopback_hostname_routing_passes(self):
        with patch.object(health.socket,'getaddrinfo',return_value=self.rows('127.0.0.1')) as resolver:
            health.check_local_routing(['disk.example.org','mail.example.org'])
            self.assertEqual(resolver.call_count,2)
            resolver.assert_called_with('mail.example.org',443,socket.AF_INET,socket.SOCK_STREAM)
    def test_public_mixed_or_missing_local_routing_fails(self):
        for addresses in [('192.0.2.1',),('127.0.0.1','192.0.2.1'),()]:
            with self.subTest(addresses=addresses),patch.object(health.socket,'getaddrinfo',return_value=self.rows(*addresses)):
                with self.assertRaisesRegex(RuntimeError,'routing missing'):health.check_local_routing(['disk.example.org'])
    def test_cloud_init_only_updates_existing_packaged_template(self):
        tasks=yaml.safe_load((ROOT/'ansible/tasks/tls.yml').read_text())
        self.assertEqual(tasks[0]['ansible.builtin.stat']['path'],'/etc/cloud/templates/hosts.debian.tmpl')
        self.assertFalse(tasks[0]['ansible.builtin.stat']['follow'])
        self.assertIn('ansible.builtin.assert',tasks[1])
        block=tasks[2]['ansible.builtin.blockinfile']
        self.assertEqual(block['block'],'127.0.0.1 {{ c.cloud_host }} {{ c.mail_host }}')
        self.assertEqual(tasks[2]['when'],'cloud_hosts_template.stat.exists')
        self.assertFalse(block.get('create',False))
        self.assertNotIn('manage_etc_hosts:',(ROOT/'ansible/tasks/tls.yml').read_text())
        self.assertIn('check_local_routing((c[',(ROOT/'ansible/files/health.py').read_text())
