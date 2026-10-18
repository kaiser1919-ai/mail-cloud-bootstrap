#!/usr/bin/python3
"""Ephemeral Ubuntu CI ONLY: native package parsers + loopback LDAP/IMAP/LMTP/Redis.
NOT the full installer, not a systemd/reboot/public DNS/Office acceptance test.
"""
import imaplib
import json
import os
from pathlib import Path
import pwd
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from email.utils import formatdate

ROOT=Path(__file__).resolve().parents[1]

def run(*argv, **kw):
    print('+',argv[0],flush=True)
    return subprocess.run(argv,check=True,**kw)

def capture(*argv):
    return subprocess.check_output(argv,text=True).strip()

def wait(port):
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=1): return
        except OSError: time.sleep(.1)
    raise RuntimeError('Loopback service did not start: '+str(port))

def write(path,text,mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);path.chmod(mode)

def main():
    release=Path('/etc/os-release').read_text()
    if os.geteuid()!=0 or os.environ.get('MAIL_CLOUD_EPHEMERAL_CI')!='1' or 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        raise SystemExit('Refusing: this script is only for the disposable Ubuntu24.04 CI container')
    import jinja2,yaml
    p=json.loads((ROOT/'platforms.json').read_text())['os_profiles']['ubuntu-24.04']
    env=jinja2.Environment(undefined=jinja2.StrictUndefined)
    tasks=yaml.safe_load((ROOT/'ansible/tasks/packages.yml').read_text())
    apt=next(t['ansible.builtin.apt'] for t in tasks if 'ansible.builtin.apt' in t)
    packages=[env.from_string(x).render(php_version=p['php_version']) for x in apt['name']]
    write('/usr/sbin/policy-rc.d','#!/bin/sh\nexit 101\n',0o755)
    run('apt-get','update')
    run('apt-get','install','-y','--no-install-recommends',*packages,'ansible-core')
    # Exercise target distro Ansible2.16, not only the development version.
    run('ansible-playbook','-i','localhost,','-c','local','ansible/site.yml','--syntax-check',cwd=ROOT)
    run('bash','tests/render.sh',cwd=ROOT)
    rendered=ROOT/'.runtime/render/ubuntu-24.04'
    for name in ('mailcloud-nextcloud','mailcloud-vmail'):
        run('useradd','--system','--no-create-home','--shell','/usr/sbin/nologin',name)
    for path in ('/srv/mail-cloud/data/mail','/srv/mail-cloud/data/mail-redis','/srv/mail-cloud/identity/config','/srv/mail-cloud/identity/data','/run/mail-cloud-ldap','/run/mail-cloud-php','/srv/mail-cloud/staging/nextcloud','/srv/mail-cloud/staging/nginx','/srv/mail-cloud/state','/srv/mail-cloud/nextcloud/config'):
        Path(path).mkdir(parents=True,exist_ok=True)
    for path,user in [('/srv/mail-cloud/data/mail','mailcloud-vmail'),('/srv/mail-cloud/data/mail-redis','redis'),('/srv/mail-cloud/identity/config','openldap'),('/srv/mail-cloud/identity/data','openldap'),('/run/mail-cloud-ldap','openldap'),('/srv/mail-cloud/staging/nextcloud','mailcloud-nextcloud'),('/srv/mail-cloud/staging/nginx','www-data')]:
        shutil.chown(path,user,user)
    run('cp','-a','/var/spool/postfix','/srv/mail-cloud/data/postfix')
    c=json.loads((ROOT/'example.json').read_text());c.update(cloud_host='disk.example.org',mail_host='mail.example.org')
    cfg={'parameters':c,'platform':{'key':'ubuntu-24.04',**p},'secrets':{'db':'fixturedb','ldap_admin':'fixtureadmin','ldap_cloud':'fixturecloud','ldap_mail':'synthetic-only','recovery':'fixturerecovery'},'passwords':{'alice':'fixture-alice-only','bob':'fixture-bob-only'}}
    write('/etc/mail-cloud-installer/config.json',json.dumps(cfg))
    context={'c':c,'secrets':cfg['secrets'],'base':'/srv/mail-cloud','nc':'/srv/mail-cloud/nextcloud','suffix':'dc=example,dc=org','php_version':'8.3','runtime_profile':p}
    def render(name): return env.from_string((ROOT/'ansible/templates'/name).read_text()).render(**context)
    write('/usr/local/lib/mail-cloud/platform.json',json.dumps(p),0o644)
    for file in ('mc_runtime.py','occ.py'):
        dest='/usr/local/lib/mail-cloud/'+('occ' if file=='occ.py' else file)
        write(dest,(ROOT/'ansible/files'/file).read_text(),0o755)
    cert=Path('/etc/letsencrypt/live/disk.example.org');cert.mkdir(parents=True,exist_ok=True)
    run('openssl','req','-x509','-nodes','-newkey','rsa:2048','-days','1','-subj','/CN=disk.example.org','-addext','subjectAltName=DNS:disk.example.org,DNS:mail.example.org','-keyout',str(cert/'privkey.pem'),'-out',str(cert/'fullchain.pem'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for name,dest in [('dovecot-2.3.conf.j2','/etc/dovecot/dovecot.conf'),('dovecot-ldap-2.3.conf.j2','/etc/dovecot/mail-cloud-ldap.conf'),('main.cf.j2','/etc/postfix/main.cf'),('ldap-mailboxes.cf.j2','/etc/postfix/ldap-mailboxes.cf'),('virtual-aliases.j2','/etc/postfix/virtual-aliases'),('php-fpm.conf.j2','/srv/mail-cloud/php-fpm.conf'),('nginx.conf.j2','/etc/nginx/sites-enabled/mail-cloud-native.conf')]:
        write(dest,render(name))
        if dest.startswith('/etc/postfix/'):
            shutil.chown(dest,'root','postfix');Path(dest).chmod(0o640)
    write('/etc/nginx/mail-cloud-access.conf','allow 127.0.0.1;\ndeny all;\n',0o644)
    # Compile Ubuntu's AppArmor policy without attempting to load host-kernel profiles
    # from a container. Actual enforcement remains a real-VPS test.
    write('/etc/apparmor.d/mail-cloud-code',render('apparmor-code.j2'),0o644)
    run('apparmor_parser','-Q','-T','/etc/apparmor.d/mail-cloud-code')
    aa_tasks=yaml.safe_load((ROOT/'ansible/tasks/apparmor.yml').read_text())
    rules=next(t for t in aa_tasks if t.get('name','').startswith('Preserve native LDAP'))['block'][1]['ansible.builtin.blockinfile']['block']
    if Path('/etc/apparmor.d/usr.sbin.slapd').exists():
        write('/etc/apparmor.d/local/usr.sbin.slapd',rules,0o644)
        run('apparmor_parser','-Q','-T','/etc/apparmor.d/usr.sbin.slapd')
    print('AppArmor parser checked; kernel enforcement NOT tested in a container.',flush=True)
    run('doveconf','-n',stdout=subprocess.DEVNULL)
    run('postfix','check')
    result=subprocess.run(['postconf','-n'],capture_output=True,text=True,check=True)
    if 'unused parameter' in result.stderr: raise RuntimeError('Postfix unsupported parameter: '+result.stderr)
    runtime_tasks=yaml.safe_load((ROOT/'ansible/tasks/runtime.yml').read_text())
    dbconf=next(t['ansible.builtin.copy']['content'] for t in runtime_tasks if t.get('ansible.builtin.copy',{}).get('dest')=='/etc/mysql/mariadb.conf.d/70-mail-cloud.cnf')
    write('/etc/mysql/mariadb.conf.d/70-mail-cloud.cnf',dbconf,0o644)
    run('mariadbd','--user=mysql','--verbose','--help',stdout=subprocess.DEVNULL)
    run('php-fpm8.3','--test','--fpm-config','/srv/mail-cloud/php-fpm.conf')
    write('/srv/mail-cloud/nextcloud/config/check.config.php',render('cloud.config.php.j2'))
    for path in list((ROOT/'ansible/files/sentinel_pool').rglob('*.php'))+[Path('/srv/mail-cloud/nextcloud/config/check.config.php')]:
        run('php8.3','-l',str(path))
    run('nginx','-t')
    # Real installed Rspamd3.8 parser loads the custom Lua guard and signing config.
    Path('/etc/rspamd/dkim').mkdir(exist_ok=True)
    run('openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out','/etc/rspamd/dkim/mc.key',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    shutil.chown('/etc/rspamd/dkim/mc.key','_rspamd','_rspamd')
    for path in (ROOT/'ansible/templates').glob('rspamd-*.j2'):
        write('/etc/rspamd/local.d/'+path.name.removeprefix('rspamd-').removesuffix('.j2'),render(path.name),0o644)
    write('/etc/rspamd/mc_outbound.lua',render('mc_outbound.lua.j2'),0o644)
    write('/etc/rspamd/outbound-window.lua',(ROOT/'ansible/files/window.lua').read_text(),0o644)
    mail_tasks=yaml.safe_load((ROOT/'ansible/tasks/mail.yml').read_text())
    local=next(t['ansible.builtin.copy']['content'] for t in mail_tasks if t.get('ansible.builtin.copy',{}).get('dest')=='/etc/rspamd/rspamd.conf.local')
    write('/etc/rspamd/rspamd.conf.local',local,0o644)
    run('rspamadm','configtest')
    # Target runtime profile used by every PHP helper, not system alternatives.
    run('python3','-c','from mc_runtime import php_binary; assert php_binary()=="/usr/bin/php8.3"',cwd='/usr/local/lib/mail-cloud')
    run('python3',str(ROOT/'ansible/files/identity.py'),'configure')
    children=[]
    try:
        ldap=subprocess.Popen(['slapd','-f','/srv/mail-cloud/identity/config/slapd.conf','-h','ldap://127.0.0.1:1389/','-d','0','-u','openldap','-g','openldap']);children.append(ldap);wait(1389)
        run('python3',str(ROOT/'ansible/files/identity.py'),'populate')
        for alias in ('postmaster','abuse','dmarc'):
            assert capture('postmap','-q',alias+'@example.org','regexp:/etc/postfix/virtual-aliases')=='alice@example.org'
        assert capture('postmap','-q','alice@example.org','ldap:/etc/postfix/ldap-mailboxes.cf')=='alice@example.org'
        dovecot=subprocess.Popen(['dovecot','-F']);children.append(dovecot);wait(993)
        ctx=ssl.create_default_context(cafile=str(cert/'fullchain.pem'))
        class NamedContext:
            def wrap_socket(self,sock,server_hostname=None,**kw): return ctx.wrap_socket(sock,server_hostname='mail.example.org',**kw)
        for user in c['users']:
            email=user+'@example.org'
            for password,allowed in [(cfg['passwords'][user],True),('wrong-password',False),(cfg['passwords']['bob' if user=='alice' else 'alice'],False)]:
                client=imaplib.IMAP4_SSL('127.0.0.1',993,ssl_context=NamedContext(),timeout=20)
                try:
                    client.login(email,password)
                    if not allowed: raise AssertionError('Wrong/cross password accepted')
                except imaplib.IMAP4.error:
                    if allowed: raise
                finally:
                    try:client.logout()
                    except Exception:pass
        with smtplib.LMTP('/srv/mail-cloud/data/postfix/private/dovecot-lmtp',timeout=20) as lmtp:
            lmtp.sendmail('fixture@example.net',['alice@example.org'],'From: fixture@example.net\r\nTo: alice@example.org\r\nSubject: native-ci-only\r\n\r\nSynthetic fixture.\r\n')
        for user,expected in [('alice',1),('bob',0)]:
            client=imaplib.IMAP4_SSL('127.0.0.1',993,ssl_context=NamedContext(),timeout=20)
            client.login(user+'@example.org',cfg['passwords'][user])
            _,count=client.select('INBOX',readonly=True);assert int(count[0])==expected
            client.logout()
        # Native Redis7 executes the actual rolling-window script and persists it.
        runtime=yaml.safe_load((ROOT/'ansible/tasks/runtime.yml').read_text())
        redisconf=next(t['ansible.builtin.copy']['content'] for t in runtime if t.get('ansible.builtin.copy',{}).get('dest')=='/etc/redis/mail-cloud-mail.conf')
        write('/etc/redis/mail-cloud-mail.conf',redisconf)
        redis=subprocess.Popen(['redis-server','/etc/redis/mail-cloud-mail.conf'],stdout=subprocess.DEVNULL);children.append(redis);wait(6380)
        script=(ROOT/'ansible/files/window.lua').read_text()
        def admit(token):return capture('redis-cli','-p','6380','--raw','EVAL',script,'1','ci:window','3600000','50',token).splitlines()
        for i in range(50):assert admit('fixture-'+str(i))[0]=='1'
        assert admit('over-limit')[0]=='0';assert admit('fixture-0')==['1','50','1']
        redis.terminate();redis.wait(timeout=15)
        redis=subprocess.Popen(['redis-server','/etc/redis/mail-cloud-mail.conf'],stdout=subprocess.DEVNULL);children.append(redis);wait(6380)
        assert admit('after-restart')[0]=='0'
        # Actual Rspamd3.8 task API and DKIM signing: no remote SMTP delivery.
        # Only loopback HTTP/Rspamd requests with synthetic message bytes.
        rspamd=subprocess.Popen(['rspamd','-f','-u','_rspamd','-g','_rspamd'],stdout=subprocess.DEVNULL);children.append(rspamd);wait(11333)
        def scan(label,user='alice@example.org',mime='alice@example.org'):
            body=('From: '+mime+'\r\nTo: bob@example.net\r\nDate: '+formatdate(localtime=False)+'\r\nMessage-ID: <'+label+'@example.org>\r\nSubject: Synthetic native CI fixture\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nOnly a local synthetic test.\r\n').encode()
            request=urllib.request.Request('http://127.0.0.1:11333/checkv2',data=body,headers={'User':user,'From':'alice@example.org','Rcpt':'bob@example.net','IP':'127.0.0.1','Queue-Id':label})
            with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
        good=scan('ci-valid-sender')
        assert 'DKIM_SIGNED' in good['symbols'],good
        assert 'MC_OUTBOUND_ALLOWED' in good['symbols'],good
        for label,kwargs in [('ci-foreign-mime',{'mime':'bob@example.org'}),('ci-unknown-user',{'user':'unknown@example.org'})]:
            result=scan(label,**kwargs)
            assert result['action']=='soft reject' and 'MC_OUTBOUND_BLOCKED' in result['symbols'],result
        key=Path('/etc/rspamd/dkim/mc.key'); saved=key.with_suffix('.saved')
        key.rename(saved)
        try:
            result=scan('ci-missing-key')
            assert result['action']=='soft reject' and 'MC_OUTBOUND_BLOCKED' in result['symbols'],result
        finally:saved.rename(key)
        redis.terminate();redis.wait(timeout=15)
        result=scan('ci-redis-unavailable')
        assert result['action']=='soft reject' and 'MC_OUTBOUND_BLOCKED' in result['symbols'],result
        print('PASS native Rspamd3.8 task API/DKIM/guard: allowed, foreign MIME, unknown user, missing key, Redis outage.',flush=True)
        print('PASS Ubuntu24.04 native parsers, installed packages, PHP8.3, Dovecot2.3 LDAP/TLS/negative auth, LMTP mailbox isolation, Redis rolling50/dedup/restart.',flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=15)
                except subprocess.TimeoutExpired: child.kill();child.wait()
    versions=capture('dpkg-query','-W','php8.3-fpm','dovecot-core','postfix','rspamd','mariadb-server','redis-server','slapd','nginx','ansible-core')
    print('Package receipt:\n'+versions)
    print('NOT VERIFIED: full installer, mounts/cgroups/systemd boot, ACME/public DNS, external SMTP, Nextcloud/Mail/Office browser acceptance.')

if __name__=='__main__': main()
