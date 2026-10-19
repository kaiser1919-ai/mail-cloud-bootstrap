# Self-hosted cloud, mail, calendar and Office

[Русский](README.ru.md) · [Architecture](docs/ARCHITECTURE.md) · [Operations](docs/OPERATIONS.md) · [Deployment lessons](docs/LESSONS.md)

## Quick start: [installation wizard `install.sh`](install.sh)

On a **new clean VPS**, from a root shell (Git and Python3 must be installed):

```bash
git clone https://github.com/kaiser1919-ai/mail-cloud-office.git
cd mail-cloud-office
bash install.sh
```

## Minimum server requirements

- Ubuntu24.04 LTS **or Debian13**, amd64, systemd and root. Both profiles passed separate clean test-VPS installations.
- Approximately **2GiB RAM + 4GiB SWAP**;4+GiB RAM preferable for Office. If swap is insufficient, the wizard explains it and offers to create the missing amount with separate consent. Existing swap is never disabled.
- Free space on `/srv`: **pool size +25GiB after swap preparation**, default105GiB for an80GiB raw pool; up to4GiB additional disk space if swap must be created. Raw image capacity is not usable ext4 capacity.
- A domain, static public IPv4, DNS and provider PTR control.
- Inbound TCP80/443/25/587/993, outbound TCP25/HTTPS; native package repositories, GitHub, Nextcloud and ACME reachable. Firewall and SSH are not disabled.
- **Not an existing mail/database/web server.** Foreign stacks, occupied ports or insufficient reserves cause refusal.

> **Ubuntu24.04 and Debian13 test-VPS acceptance passed.** Clean install, full rerun, reboot, mail/privacy checks and native Office save/reopen passed, including bounded concurrent cloud/mail load. This is not a general production-security or deliverability certification. Use only a new clean VPS; prepare independent backup and owner MFA before real data. [Debian13 evidence](reports/debian-13-acceptance.md). [Evidence and limits](reports/spec-review.md).

One terminal wizard asks for a domain, public IPv4, ACME contact email, mailbox count and each login. It generates secrets and installs a native stack using Ansible on localhost. You do not need to write an inventory or install Ansible yourself: the wizard obtains `ansible-core` from the native OS repository.

## Stack

- Nextcloud **34.0.4**, Mail **5.12.4**, Calendar **6.6.2**; one browser portal.
- Nextcloud Office **richdocuments 11.1.2** and built-in Collabora CODE **26.4.402**, supervised separately by systemd.
- Private OpenLDAP: shared cloud/mail identities and passwords. Mail captures the current user's credential through its native login middleware; no shared master password. This is not cross-domain OIDC/SSO.
- Postfix, Dovecot **2.3 on Ubuntu / 2.4 on Debian**, Rspamd, mandatory DKIM/milter and **50 outgoing attempts/hour/account**.
- PHP **8.3 on Ubuntu / 8.4 on Debian** FPM, MariaDB, APCu, separate cloud/mail Redis instances, Nginx and Certbot.
- A physically reserved shared ext4 image for files/mail/queue/mail-Redis, separate 2 GiB disk staging, a read-only real-capacity indicator.

No Docker, AIO or Mailcow. The separate local `recovery_admin` is not a mailbox. Application versions intentionally reproduce the original setup, **not a claim that these are the latest or indefinitely supported**. Review upstream security advisories/support and test upgrades before production. OS packages come from signed native Ubuntu/Debian repositories including security updates; actual versions are recorded in `/srv/mail-cloud/state/packages.tsv`.

## Automatic OS profiles

| OS | PHP/FPM | Dovecot | Actual verification |
|---|---|---|---|
| **Ubuntu 24.04 LTS** | **8.3** | **2.3**, native separate LDAP/TLS config | Install / rerun / reboot / Mail / Office — PASS |
| Debian 13 | 8.4 | 2.4, separate new-syntax template | Install / rerun / reboot / Mail / Office — PASS |

No additional OS-selection prompt: detection is automatic. Ubuntu **Universe** is enabled through the standard repository tool when necessary; no third-party PPA or distribution upgrade is added. The pinned Nextcloud34.0.4 metadata permits PHP8.3. All PHP helpers, FPM and cron use the chosen runtime rather than the system alternative. AppArmor is preserved: local LDAP path rules and a CODE-AppImage-only user namespace allowance, never a global sysctl disable. The targeted policies were loaded on the real test kernel and Office executed successfully; no global AppArmor disable. Resume refuses OS/profile changes; this is not an in-place Debian-to-Ubuntu migration tool.

## Wizard parameters

The wizard asks for domain, IPv4, ACME email, **mailbox count (1–20)** and **each local login**; then `INSTALL` confirmation. If new swap is needed it separately asks for `CREATE SWAP`. For `example.org`, defaults are `disk.example.org` and `mail.example.org`. Enter each local mailbox name separately, e.g. `alice`, then `bob`; login names become full email addresses. Credentials are generated once and kept in `/etc/mail-cloud-installer/config.json` (root-only directory 0700/file 0600). For every mailbox the wizard prints the exact path and JSON key, e.g. `alice@example.org -> /etc/mail-cloud-installer/config.json : passwords["alice"]`, never the password itself. **Never commit, send or publish this file.**

Advanced public parameters:

```bash
cp example.json my-parameters.json
# Replace domain, IPv4, ACME email and mailbox names.
# Optional overrides: cloud_host, mail_host, pool_gib.
bash install.sh --plan --config my-parameters.json
bash install.sh --config my-parameters.json
```

`--plan` validates input without root/network/writes; it does not inspect target readiness. The JSON file is never shell-sourced and accepts only documented public fields. Rerun the same command to resume; changed parameters are refused, existing passwords and filesystems are not reset.

## DNS and certificates

The installer prints exact A/MX/SPF/DKIM/DMARC/PTR requirements. It generates a new DKIM key and shows the actual public TXT record for `mc._domainkey`. Default SPF authorizes only the supplied IPv4; do not apply it blindly to a domain with other senders. This installer is not a migration tool for existing complex mail infrastructure.

Set A records for both hosts, MX to `mail.DOMAIN`, SPF, DKIM, DMARC `p=none`, and ask the VPS provider to set PTR to `mail.DOMAIN`. Do not use a web CDN proxy for mail. Remove AAAA records: public mail is configured for IPv4 here.

For an installation on `test.example.org` inside the `example.org` DNS zone, use record name `mc._domainkey.test` (full name `mc._domainkey.test.example.org`). This belongs to the **test subdomain**, not the parent mail service. After reinstalling the server, replace the old value with the new installer-generated key; do not create a second TXT record at that name or change the parent domain’s MX/SPF/DKIM.

Without registrar/provider API credentials, DNS/PTR changes cannot be automated. The script stops on mismatches, preserving state; fix DNS, wait for propagation, then rerun. Mail services remain masked until configuration and full DNS acceptance, including across reboot. Passing DNS does **not** prove external TCP25 or delivery.

Let's Encrypt HTTP-01 issuance is automated through port80, with real hostname validation and a renewal deploy hook. There is no silent self-signed fallback.

## First login

The portal remains localhost-only. Establish an SSH tunnel, configure **recovery_admin TOTP and backup codes**, then run:

```bash
bash install.sh --open-portal
bash install.sh --check
```

Opening verifies enabled MFA providers before removing the localhost gate. Enrolling a person's authenticator requires that person's interaction and is intentionally not faked by the script. See [Operations](docs/OPERATIONS.md) for the hostname-preserving tunnel and manual acceptance checklist.

## Scope and limitations

No personal files/messages/keys, website, VPN, bots, paid service, external backup, unattended Nextcloud/app upgrades, DNS API integration or deliverability guarantee. Local state and configurations are **not backups**. Back up consistent DB/LDAP/files/mail/config/keys/secrets to an independent encrypted destination and test restoration separately.

Before production: clean install → rerun → reboot; two real isolated browser users, external bidirectional email, file/mail privacy and negative relay/sender/auth probes, Office create/edit/save/reopen/export, mount-loss refusal and restore onto another machine. Unit tests are not substitutes.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install 'ansible-core>=2.19,<2.20' jinja2 pyyaml
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ansible-playbook -i localhost, -c local ansible/site.yml --syntax-check
```

CI covers both profile/template branches and Python 3.12/3.13; an isolated Ubuntu24.04 container installs native packages and exercises parsers and synthetic loopback LDAP/IMAPS/LMTP/Redis checks. This is **not a complete VPS/systemd/reboot/public SMTP/Office acceptance test**. Docker is only a CI isolation tool, not the installation architecture. Source license: AGPL-3.0-only. Upstream apps/packages retain their respective licenses; proprietary fonts and private deployment artifacts are excluded.

### Explicit low-headroom TEST VPS mode
Only on an isolated authorised test VPS:
`sudo ./install.sh --test-low-headroom --config /root/test-parameters.json`.
Requires image size +8 GiB free instead of the unchanged production +25 GiB.
Repeat the flag on every resume; an existing deployment cannot change modes.
Before/after phases the installer requires 2 GiB outside images, 250 MiB
MemAvailable and 512 MiB SwapFree. Downloads/extraction retain a 2 GiB system
reserve. A pressure stop never deletes user data.
After installation run `sudo python3 tests/stress_pool.py --confirm-test-vps --gib 2`,
optionally increasing to `--gib 80`. The runner writes only its private temporary
folder inside the mounted pool, retains 1 GiB pool space, verifies SHA256 on
readback, and removes its own fixture. SIGKILL may leave a fixture for manual
inspection. This is a filesystem stress test, not simultaneous Nextcloud/mail/
Office acceptance. 80 GiB is the physical ext4 image size, not usable filesystem
capacity; the UI reports actual capacity. This is not a production recommendation
or a promise that every 100 GB disk can host the whole stack.

On an isolated TEST VPS with at least two test users run
`sudo python3 tests/cloud_acceptance.py --confirm-test-vps` for WebDAV write/read,
cross-account isolation and wrong/cross-user password rejection. Only its own
UUID fixtures are deleted with a per-request skip-trash header; user trash is
never emptied. Credentials stay in memory from root-private state, TLS remains
verified. Local testing does not require publishing the portal or bypassing MFA.
This does not replace actual browser login, Mail/Office and reboot acceptance.
