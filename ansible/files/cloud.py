#!/usr/bin/python3
import json
import os
from pathlib import Path
import subprocess
import sys

cfg = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())
c, s = cfg['parameters'], cfg['secrets']
base = Path('/srv/mail-cloud')

def occ(args):
    return subprocess.check_output(['/usr/local/lib/mail-cloud/occ', '--json-stdin'], input=json.dumps(args).encode()).decode().strip()

if sys.argv[1] == 'install':
    p = base / 'nextcloud/config/config.php'
    if not p.exists():
        occ(['maintenance:install', '--database=mysql', '--database-host=localhost', '--database-name=nextcloud', '--database-user=nextcloud', '--database-pass=' + s['db'], '--admin-user=recovery_admin', '--admin-pass=' + s['recovery'], '--data-dir=/srv/mail-cloud/data/nextcloud'])
    state = json.loads(occ(['status', '--output=json']))
    if not state.get('installed') or state.get('needsDbUpgrade') or state.get('maintenance'):
        raise SystemExit('Interrupted cloud install; inspect before retry')
    (base / 'state/cloud-installed').touch(mode=0o600)
else:
    marker = base / 'state/ldap-prefix'
    if not marker.exists():
        # Command creates exactly one empty config. Save immediately before any settings.
        prefix = occ(['ldap:create-empty-config', '--only-print-prefix'])
        if not __import__('re').fullmatch(r's[0-9]+', prefix):
            raise SystemExit('Unexpected LDAP configuration prefix')
        marker.write_text(prefix)
    prefix = marker.read_text().strip()
    suffix = ','.join('dc=' + x for x in c['domain'].split('.'))
    settings = {
        'ldapHost': '127.0.0.1', 'ldapPort': '1389', 'ldapBase': suffix,
        'ldapBaseUsers': 'ou=people,' + suffix, 'ldapBaseGroups': 'ou=people,' + suffix,
        'ldapAgentName': 'cn=nextcloud,ou=services,' + suffix, 'ldapAgentPassword': s['ldap_cloud'],
        'ldapTLS': '0', 'ldapUserFilterMode': '1',
        'ldapUserFilter': '(&(objectClass=inetOrgPerson)(mail=*@' + c['domain'] + '))',
        'ldapUserDisplayName': 'cn', 'ldapEmailAttribute': 'mail', 'ldapLoginFilterMode': '1',
        'ldapLoginFilter': '(&(objectClass=inetOrgPerson)(mail=%uid))',
        'ldapGroupFilterMode': '1', 'ldapGroupFilter': '(objectClass=groupOfNames)',
        'ldapExpertUsernameAttr': 'uid', 'ldapExpertUUIDUserAttr': 'entryUUID',
        'ldapCacheTTL': '60', 'ldapQuotaDefault': 'none', 'ldapConfigurationActive': '1',
    }
    for k, v in settings.items():
        occ(['ldap:set-config', prefix, k, v])
    occ(['ldap:test-config', prefix])
