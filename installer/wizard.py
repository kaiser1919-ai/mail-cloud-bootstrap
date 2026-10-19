#!/usr/bin/env python3
"""Local-only bootstrap. No passwords in argv, shell expansion, or stdout."""
import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = Path('/etc/mail-cloud-installer')
GIB = 1024**3


def validate(raw):
    allowed = {'domain', 'ipv4', 'acme_email', 'users', 'cloud_host', 'mail_host', 'pool_gib'}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError('Unknown configuration keys')
    c = dict(raw)
    domain_re = r'(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if isinstance(c.get('domain'), str):
        c.setdefault('cloud_host', 'disk.' + c['domain'])
        c.setdefault('mail_host', 'mail.' + c['domain'])
    for key in ('domain', 'cloud_host', 'mail_host'):
        if key == 'domain' or key in c:
            if not isinstance(c.get(key), str) or not re.fullmatch(domain_re, c[key]):
                raise ValueError(f'Invalid {key}: use a lowercase ASCII/punycode FQDN')
    c.setdefault('cloud_host', 'disk.' + c['domain'])
    c.setdefault('mail_host', 'mail.' + c['domain'])
    if len({c['domain'], c['cloud_host'], c['mail_host']}) != 3:
        raise ValueError('Domain, cloud and mail hostnames must be distinct')
    ip = ipaddress.IPv4Address(c['ipv4'])
    if not ip.is_global:
        raise ValueError('A public IPv4 is required')
    if not isinstance(c.get('acme_email'), str) or not re.fullmatch(r'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', c['acme_email']):
        raise ValueError('Invalid ACME email')
    users = c.get('users')
    if not isinstance(users, list) or not 1 <= len(users) <= 20 or any(not isinstance(u, str) for u in users) or len(users) != len(set(users)):
        raise ValueError('Provide 1–20 distinct users')
    if any(not isinstance(u, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,30}', u) or u in ('root', 'admin', 'recovery_admin', 'postmaster', 'abuse', 'dmarc') for u in users):
        raise ValueError('Invalid/reserved local user name')
    c.setdefault('pool_gib', 80)
    if type(c['pool_gib']) is not int or not 5 <= c['pool_gib'] <= 100000:
        raise ValueError('pool_gib must be an integer >=5')
    return c


def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def private_load(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077:
        raise ValueError(f'Unsafe config file permissions: {path}')
    return json.loads(path.read_text())


def detect_platform(os_release=None):
    if os_release is None:
        os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    key = os_release.get('ID', '').strip('"') + '-' + os_release.get('VERSION_ID', '').strip('"')
    profiles = json.loads((ROOT / 'platforms.json').read_text())['os_profiles']
    if key not in profiles:
        raise ValueError('Only Ubuntu 24.04 LTS and Debian 13 are supported')
    return {'key': key, **profiles[key]}


def validate_resume_platform(values, current):
    previous = values.get('platform')
    # Pre-profile releases were Debian13-only: adopt only that exact platform.
    if previous is None:
        if current['key'] != 'debian-13':
            raise ValueError('Legacy Debian state cannot be resumed on another OS')
    elif previous != current:
        raise ValueError('OS/runtime profile changed; refusing cross-OS migration')


def validate_test_mode(values, requested):
    previous = values.get('test_low_headroom', False)
    if type(previous) is not bool or previous != requested:
        raise ValueError('Test mode changed; resume with the original --test-low-headroom setting')


def disk_requirement(pool_gib, resume, test_mode=False):
    return ((2 if test_mode else 5) if resume else pool_gib + (8 if test_mode else 25)) * GIB


def preflight(c, resume, test_mode=False):
    profile = detect_platform()
    if os.uname().machine != 'x86_64' or not Path('/run/systemd/system').is_dir():
        raise ValueError('Requires amd64 and a running systemd, not a container')
    if not resume:
        # Never adopt an existing stack, including inactive services/config directories.
        for p in ('/srv/mail-cloud', '/etc/nginx', '/etc/postfix', '/etc/dovecot', '/etc/ldap/slapd.d', '/var/lib/mysql', '/usr/sbin/policy-rc.d'):
            if Path(p).exists() or Path(p).is_symlink():
                raise ValueError(f'Not a clean host: {p} exists. Use a NEW VPS.')
        for port in (25, 80, 443, 587, 993, 1389, 3306, 6379, 6380, 9983):
            with socket.socket() as s:
                try:
                    s.bind(('0.0.0.0', port))
                except OSError as e:
                    raise ValueError(f'Port {port} is occupied') from e
        if shutil.disk_usage('/srv').free < disk_requirement(c['pool_gib'], False, test_mode):
            raise ValueError('Need pool size +' + ('8' if test_mode else '25') + ' GiB free on /srv')
    if resume and shutil.disk_usage('/srv').free < disk_requirement(c['pool_gib'], True, test_mode):
        raise ValueError('Need >=' + ('2' if test_mode else '5') + ' GiB free outside the reserved images before resuming')
    mem = dict((r.split(':', 1)[0], int(r.split()[1])) for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith(('MemTotal:', 'SwapTotal:')))
    if mem['MemTotal'] < 1800 * 1024 or mem['SwapTotal'] < 4095 * 1024:
        raise ValueError('Need at least ~2 GiB RAM and 4 GiB swap (4+ GiB RAM recommended for Office)')


def run(argv):
    subprocess.run(argv, check=True, cwd=ROOT, env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'ANSIBLE_NOCOLOR': '1', 'ANSIBLE_DISPLAY_ARGS_TO_STDOUT': 'false', 'ANSIBLE_LOG_PATH': '/dev/null', 'ANSIBLE_LOCAL_TEMP': str(STATE / 'ansible-local'), 'ANSIBLE_HOME': str(STATE / 'ansible'), 'ANSIBLE_CONFIG': str(ROOT / 'ansible.cfg')})


def main():
    ap = argparse.ArgumentParser(description='Mail/cloud bootstrap. See README.ru.md / README.md')
    ap.add_argument('--test-low-headroom', action='store_true', help='TEST VPS ONLY: reserve pool+8 GiB instead of +25; retains pressure guards')
    ap.add_argument('--config', type=Path, help='Public parameters JSON, never shell sourced')
    ap.add_argument('--plan', action='store_true', help='Validate/print public configuration, no root/network/writes')
    ap.add_argument('--check', action='store_true', help='Run installed health checks, no reinstall')
    ap.add_argument('--open-portal', action='store_true', help='Verify recovery TOTP then allow public HTTPS')
    args = ap.parse_args()
    if args.plan:
        if not args.config:
            ap.error('--plan requires --config')
        print(json.dumps(validate(json.loads(args.config.read_text())), indent=2))
        return
    if os.geteuid() != 0:
        raise ValueError('Run as root on a NEW Ubuntu 24.04 or Debian 13 VPS. Read/review the code first.')
    os.umask(0o077)
    if STATE.is_symlink():
        raise ValueError('State directory must not be a symlink')
    STATE.mkdir(mode=0o700, exist_ok=True)
    if STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
        raise ValueError('State directory must be root:root 0700')
    lockfd = os.open(STATE / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('Another installer is running') from None
    stored = STATE / 'config.json'
    resume = stored.exists()
    if resume:
        values = private_load(stored)
        c = validate(values['parameters'])
        validate_test_mode(values, args.test_low_headroom)
        if args.config and validate(json.loads(args.config.read_text())) != c:
            raise ValueError('Parameters changed; refusing to rewrite an existing installation')
    else:
        if args.check or args.open_portal:
            raise ValueError('No installation state')
        if args.config:
            c = validate(json.loads(args.config.read_text()))
        else:
            print('NEW Ubuntu 24.04 LTS / Debian 13. Domains default to disk.DOMAIN and mail.DOMAIN.')
            c = validate({'domain': input('Domain: ').strip(), 'ipv4': input('Public IPv4: ').strip(),
                          'acme_email': input('Email for certificate notices: ').strip(),
                          'users': input('Mailbox local names, comma separated (e.g. alice,bob): ').strip().split(',')})
        print(json.dumps(c, indent=2))
        print('This installs services on this host; does NOT change DNS. Needs 4GiB swap.')
        print('TEST VPS: reduced disk headroom, pressure stops enabled.' if args.test_low_headroom else 'Need pool+25GiB free.')
        if input('Type INSTALL to proceed: ') != 'INSTALL':
            return
    preflight(c, resume, args.test_low_headroom)
    profile = detect_platform()
    if resume:
        validate_resume_platform(values, profile)
        if 'platform' not in values:
            values['platform'] = profile
            atomic_json(stored, values)
    if not resume:
        values = {'parameters': c, 'platform': profile, 'test_low_headroom': args.test_low_headroom, 'secrets': {k: secrets.token_hex(32) for k in ('db', 'ldap_cloud', 'ldap_mail', 'ldap_admin', 'recovery')},
                  'passwords': {u: secrets.token_urlsafe(24) for u in c['users']}}
        atomic_json(stored, values)
    if profile['os_id'] == 'ubuntu' and not (args.check or args.open_portal):
        # Standard Ubuntu component, never a third-party PPA. Also needed when
        # ansible already exists but Universe dependencies were disabled.
        run(['apt-get', 'update'])
        run(['apt-get', '-y', '--no-install-recommends', 'install', 'software-properties-common'])
        run(['add-apt-repository', '--yes', '--no-update', 'universe'])
        run(['apt-get', 'update'])
    if not shutil.which('ansible-playbook'):
        run(['apt-get', 'update'])
        run(['apt-get', '-y', '--no-install-recommends', 'install', 'ansible-core'])
    phase = 'open' if args.open_portal else 'check' if args.check else 'install'
    run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', 'ansible/site.yml', '-e', '@' + str(stored), '-e', 'bootstrap_action=' + phase])
    print('Checks passed for this invocation. Credentials: /etc/mail-cloud-installer/config.json (root only).')
    if phase == 'install':
        print('Portal remains localhost-only. Set recovery-admin TOTP via SSH tunnel (docs/OPERATIONS.md), then --open-portal.')
        print('No external backup configured; remote deliverability and browser Office acceptance still need testing.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, EOFError, subprocess.CalledProcessError) as e:
        # Do not echo subprocess output or credential-bearing values.
        print('STOP: ' + (str(e) if not isinstance(e, subprocess.CalledProcessError) else 'Step failed; fix the reported phase and rerun. No data was reset.'), file=sys.stderr)
        sys.exit(1)
