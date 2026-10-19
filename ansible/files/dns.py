#!/usr/bin/python3
"""No DNS API credentials; show exact public records, then verify, never claim delivery."""
import json
from pathlib import Path
import subprocess
import sys

def dig(name, typ):
    # systemd-resolved may synthesize answers from /etc/hosts even for dig.
    # Query public DNS explicitly, never the local stub used for app routing.
    for resolver in ('1.1.1.1', '8.8.8.8'):
        try:
            return subprocess.check_output(['dig', '+time=5', '+tries=1', '+short', '@' + resolver, name, typ], text=True, stderr=subprocess.DEVNULL).strip().splitlines()
        except subprocess.CalledProcessError:
            continue
    raise SystemExit('WAIT: Public DNS resolvers unavailable; check outbound DNS connectivity')


def main():
    c = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())['parameters']
    mode = sys.argv[1] if len(sys.argv) > 1 else 'full'
    print(f"DNS required:\n{c['cloud_host']} A {c['ipv4']}\n{c['mail_host']} A {c['ipv4']}\n{c['domain']} MX 10 {c['mail_host']}.\n{c['domain']} TXT v=spf1 ip4:{c['ipv4']} -all\n_dmarc.{c['domain']} TXT v=DMARC1; p=none; rua=mailto:dmarc@{c['domain']}")
    print(f"Provider control panel: PTR {c['ipv4']} -> {c['mail_host']}")
    key = Path('/srv/mail-cloud/state/dkim-dns.txt')
    if key.exists():
        print(key.read_text())
    failed = []
    for host in (c['cloud_host'], c['mail_host']):
        if dig(host, 'A') != [c['ipv4']]:
            failed.append(f'A record {host} must resolve only to the target IPv4')
        if dig(host, 'AAAA'):
            failed.append(f'Remove AAAA for {host}: this installer configures IPv4 mail only')
    if mode == 'full':
        if f"10 {c['mail_host']}." not in dig(c['domain'], 'MX'):
            failed.append('MX mismatch')
        spf = ''.join(dig(c['domain'], 'TXT')).replace('"', '')
        if f"v=spf1 ip4:{c['ipv4']} -all" not in spf:
            failed.append('SPF mismatch; do not replace existing senders without reviewing them')
        dmarc = ''.join(dig('_dmarc.' + c['domain'], 'TXT')).replace('"', '')
        if 'v=DMARC1;' not in dmarc or 'p=' not in dmarc:
            failed.append('Missing DMARC')
        reverse = '.'.join(reversed(c['ipv4'].split('.'))) + '.in-addr.arpa'
        if dig(reverse, 'PTR') != [c['mail_host'] + '.']:
            failed.append('PTR mismatch; set it at the VPS provider')
        dkim = ''.join(dig('mc._domainkey.' + c['domain'], 'TXT')).replace('"', '').replace(' ', '')
        expected = Path('/srv/mail-cloud/state/dkim-public.txt')
        if not expected.exists() or ('p=' + expected.read_text().strip()) not in dkim:
            failed.append('DKIM public key mismatch')
    if failed:
        print('\n'.join('WAIT: ' + s for s in failed), file=sys.stderr)
        raise SystemExit(1)
    print('DNS checks passed. This does not prove outbound TCP25 or reputation/deliverability.')


if __name__ == "__main__":
    main()
