#!/usr/bin/python3
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

cfg = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())
c, s = cfg['parameters'], cfg['secrets']
suffix = ','.join('dc=' + p for p in c['domain'].split('.'))
base = Path('/srv/mail-cloud/identity')

def hashed(password):
    salt = os.urandom(8)
    return '{SSHA}' + base64.b64encode(hashlib.sha1(password.encode() + salt).digest() + salt).decode()

if sys.argv[1] == 'configure':
    text = f'''include /etc/ldap/schema/core.schema
include /etc/ldap/schema/cosine.schema
include /etc/ldap/schema/inetorgperson.schema
pidfile /run/mail-cloud-ldap/slapd.pid
argsfile /run/mail-cloud-ldap/slapd.args
modulepath /usr/lib/ldap
moduleload back_mdb
threads 2
database mdb
maxsize 67108864
suffix "{suffix}"
rootdn "cn=admin,{suffix}"
rootpw {hashed(s['ldap_admin'])}
directory /srv/mail-cloud/identity/data
index objectClass eq
index uid,mail eq
access to attrs=userPassword by self write by anonymous auth by * none
access to attrs=entry,children,objectClass,uid,mail,cn,sn,entryUUID,modifyTimestamp,createTimestamp by dn.exact="cn=nextcloud,ou=services,{suffix}" read by dn.exact="cn=dovecot,ou=services,{suffix}" read by self read by * none
access to * by * none
'''
    f = base / 'config/slapd.conf'
    if not f.exists():
        f.write_text(text)
        u = pwd.getpwnam('openldap')
        os.chown(f, u.pw_uid, u.pw_gid)
        f.chmod(0o600)
    subprocess.run(['slaptest', '-f', str(f), '-u'], check=True, capture_output=True)
else:
    def ldif(dn, attrs):
        return 'dn: ' + dn + '\n' + '\n'.join(k + ':: ' + base64.b64encode(v.encode()).decode() for k, v in attrs) + '\n\n'
    entries = [(suffix, [('objectClass', 'dcObject'), ('objectClass', 'organization'), ('dc', c['domain'].split('.')[0]), ('o', c['domain'])])]
    for ou in ('people', 'services'):
        entries.append((f'ou={ou},{suffix}', [('objectClass', 'organizationalUnit'), ('ou', ou)]))
    for name, key in [('nextcloud', 'ldap_cloud'), ('dovecot', 'ldap_mail')]:
        entries.append((f'cn={name},ou=services,{suffix}', [('objectClass', 'organizationalRole'), ('objectClass', 'simpleSecurityObject'), ('cn', name), ('userPassword', hashed(s[key]))]))
    for user in c['users']:
        entries.append((f'uid={user},ou=people,{suffix}', [('objectClass', 'inetOrgPerson'), ('uid', user), ('cn', user), ('sn', user), ('mail', user + '@' + c['domain']), ('userPassword', hashed(cfg['passwords'][user]))]))
    with tempfile.NamedTemporaryFile(mode='w', dir='/etc/mail-cloud-installer') as pw:
        pw.write(s['ldap_admin']); pw.flush()
        auth = ['-x', '-H', 'ldap://127.0.0.1:1389', '-D', 'cn=admin,' + suffix, '-y', pw.name]
        for dn, attrs in entries:
            r = subprocess.run(['ldapsearch', *auth, '-b', dn, '-s', 'base', '(objectClass=*)', 'dn'], capture_output=True)
            if r.returncode == 0:
                continue
            if r.returncode != 32:
                raise SystemExit('LDAP lookup failed; nothing reset')
            subprocess.run(['ldapadd', *auth], input=ldif(dn, attrs).encode(), check=True, capture_output=True)
