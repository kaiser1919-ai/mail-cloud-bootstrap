#!/usr/bin/python3
"""Local synthetic probes only. No external email; never prints passwords."""
import imaplib
import json
from pathlib import Path
import smtplib
import socket
import ssl
import subprocess
import sys
import urllib.request


def run(*argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.DEVNULL).strip()


def main():
    cfg = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())
    c = cfg['parameters']
    units = ['nginx', 'mariadb', 'mail-cloud-ldap', 'mail-cloud-redis', 'mail-cloud-mail-redis', 'mail-cloud-php', 'dovecot', 'rspamd', 'postfix', 'mail-cloud-office-code', 'mail-cloud-cron.timer', 'mail-cloud-pool-usage.timer']
    for u in units:
        if run('systemctl', 'is-active', u) != 'active':
            raise RuntimeError('Service inactive: ' + u)
    if run('findmnt', '-nr', '-M', '/srv/mail-cloud/data', '-o', 'FSTYPE') != 'ext4':
        raise RuntimeError('Shared mount missing')
    run('nginx', '-t')
    run('postfix', 'check')
    run('doveconf', '-n')
    run('rspamadm', 'configtest')
    state = json.loads(run('/usr/local/lib/mail-cloud/occ', 'status', '--output=json'))
    if state.get('maintenance') or state.get('needsDbUpgrade') or not state.get('installed'):
        raise RuntimeError('Cloud is not operational')
    run('/usr/local/lib/mail-cloud/auth-check')
    # Hostname/SAN verification retained while TCP always goes to localhost.
    context = ssl.create_default_context()
    class NamedContext:
        def wrap_socket(self, sock, server_hostname=None, **kw):
            return context.wrap_socket(sock, server_hostname=c['mail_host'], **kw)
    for u in c['users']:
        email = u + '@' + c['domain']
        imap = imaplib.IMAP4_SSL('127.0.0.1', 993, ssl_context=NamedContext(), timeout=30)
        if imap.login(email, cfg['passwords'][u])[0] != 'OK':
            raise RuntimeError('LDAP IMAP login failed')
        imap.logout()
        bad = imaplib.IMAP4_SSL('127.0.0.1', 993, ssl_context=NamedContext(), timeout=30)
        try:
            bad.login(email, cfg['passwords'][u] + '-wrong')
        except imaplib.IMAP4.error:
            pass
        else:
            raise RuntimeError('Wrong IMAP password accepted')
        finally:
            try: bad.logout()
            except Exception: pass
        with smtplib.SMTP('127.0.0.1', 587, timeout=30) as smtp:
            smtp.ehlo()
            if 'auth' in smtp.esmtp_features:
                raise RuntimeError('AUTH advertised before TLS')
            smtp.starttls(context=NamedContext()); smtp.ehlo()
            smtp.login(email, cfg['passwords'][u])
            code, _ = smtp.mail('not-your-account@' + c['domain'])
            if code < 500:
                code, _ = smtp.rcpt('nobody@example.net')
            if code < 500:
                raise RuntimeError('Foreign sender accepted')
    with smtplib.SMTP('127.0.0.1', 25, timeout=30) as smtp:
        smtp.ehlo()
        if 'auth' in smtp.esmtp_features:
            raise RuntimeError('AUTH on port25')
        smtp.mail('nobody@example.net')
        code, _ = smtp.rcpt('nobody@example.org')
        if code < 500:
            raise RuntimeError('Open relay')
        smtp.rset(); smtp.mail('nobody@example.net')
        code, _ = smtp.rcpt('does-not-exist@' + c['domain'])
        if code < 500:
            raise RuntimeError('Unknown mailbox accepted')
    for host in (c['cloud_host'], c['mail_host']):
        with socket.create_connection(('127.0.0.1', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host):
                pass
    text = run('curl', '-fsS', '--max-time', '90', '--resolve', c['cloud_host'] + ':443:127.0.0.1', 'https://' + c['cloud_host'] + '/custom_apps/richdocumentscode/proxy.php?req=/hosting/discovery')
    if '<wopi-discovery' not in text:
        raise RuntimeError('Office gateway unavailable')
    listeners = run('ss', '-Hlnt').splitlines()
    private = {'1389', '6379', '6380', '9983', '11332', '11333', '11334'}
    for row in listeners:
        address = row.split()[3]
        host, _, port = address.rpartition(':')
        if port in private and host not in ('127.0.0.1', '[::1]'):
            raise RuntimeError('Private service exposed: port ' + port)
    run('/usr/local/lib/mail-cloud/dns', 'full')
    print('PASS local TLS/auth/relay/sender/unknown-recipient/mount/Office discovery/DNS checks.')
    print('NOT tested: external TCP25 delivery/reputation, browser MFA/Office save/reopen, clean reboot and load, disaster recovery.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Errors from parsers/auth can contain private config; do not print raw exceptions.
        print('FAIL health check. Inspect services locally; no secrets printed.', file=sys.stderr)
        sys.exit(1)
