# Эксплуатация / Operations

## RU: безопасный первый вход

Все примеры используют фиктивные имена; замени их своими. На ноутбуке добавь временную hosts-запись `127.0.0.1 disk.example.org`. Открой SSH-туннель, сохранив проверку SSH host key:

```bash
ssh -N -L 127.0.0.1:8443:127.0.0.1:443 operator@YOUR_VPS_IP
```

Открой **https://disk.example.org:8443**. Не используй адрес `https://localhost`: проверка сертификата должна видеть настоящее имя. Не отключай certificate verification. Если Nextcloud отвергает hostname с портом, добавь ровно `disk.example.org:8443` в `trusted_domains` временно через `occ config:system:set trusted_domains 1 --value=disk.example.org:8443` и удали после настройки. Не добавляй `*`.

В root-shell на VPS открой `/etc/mail-cloud-installer/config.json` локальным редактором, возьми сгенерированный пароль `secrets.recovery`. Не копируй весь файл в чат/тикеты/репозиторий. Войди как `recovery_admin`, включи TOTP в Personal → Security и сгенерируй резервные коды. Храни коды отдельно, проверь повторный вход и один резервный код. Только затем выполни `bash install.sh --open-portal`. Удали временную hosts-запись ноутбука и туннель, зайди снаружи и проверь сертификат.

Пароли обычных пользователей — в `passwords`. Вход в облако и клиенты IMAP/SMTP — **полный email**. После первого входа Mail должен получить пароль текущего пользователя штатно. Это подлежит браузерной приёмке, не обещание cross-domain SSO.

## EN: first login

Temporarily map `disk.example.org` to `127.0.0.1` on your laptop and establish the SSH tunnel shown above. Open **https://disk.example.org:8443** with hostname verification, never an insecure localhost certificate exception. If required, add exactly `disk.example.org:8443` as a temporary trusted domain via the `occ` command above; remove it afterwards, never use a wildcard.

Read the root-only credential file locally on the VPS; use `secrets.recovery` to sign in as `recovery_admin`. Enrol TOTP, generate backup codes, store them independently, and test a fresh login and a recovery-code login. Then run `bash install.sh --open-portal`. Remove the laptop hosts override and tunnel, and test public HTTPS. Mailbox users authenticate with full email addresses; generated initial passwords are in `passwords`.

## Диагностика / Diagnostics

```bash
bash install.sh --check
systemctl --failed
systemctl status mail-cloud-php mail-cloud-ldap mail-cloud-office-code
systemctl status mail-cloud-redis mail-cloud-mail-redis
systemctl status postfix@- dovecot rspamd mariadb nginx
findmnt -M /srv/mail-cloud/data
findmnt -M /srv/mail-cloud/staging
df -h / /srv/mail-cloud/data /srv/mail-cloud/staging
free -h
journalctl -u mail-cloud-office-code --since '-10min'
postqueue -p
certbot renew --dry-run
```

`--check` performs **bootstrap credential acceptance**, including wrong-password checks; after user password rotation, initial stored passwords are no longer valid. Do not reset user passwords just to make this probe green. Adapt protected acceptance credentials or perform a current-user login manually. Do not publish the secrets file, `doveconf -n` output, full `postconf` map content, journals, request URLs or email contents: diagnostics can contain private information. The health helper suppresses raw authentication/config exceptions.

Ключевые пути / Key paths:

| Path | Purpose |
|---|---|
| `/etc/mail-cloud-installer` | Root-only parameters, credentials, installer lock/temp |
| `/srv/mail-cloud/images` | Dense data and staging ext4 images; **never delete/reformat** |
| `/srv/mail-cloud/data/nextcloud` | Cloud files and bounded log |
| `/srv/mail-cloud/data/mail` | User Maildirs |
| `/srv/mail-cloud/data/postfix` | Native Postfix queue layout |
| `/srv/mail-cloud/data/mail-redis` | Persistent mail policy Redis |
| `/srv/mail-cloud/staging` | Bounded on-disk PHP/Office/Nginx temp; not shared `/tmp` |
| `/srv/mail-cloud/identity` | LDAP config and MDB database |
| `/var/lib/mysql` | MariaDB, outside user pool |
| `/etc/rspamd/dkim` | Private DKIM key |
| `/srv/mail-cloud/state/packages.tsv` | Actual OS package version receipt |

Cloud code is outside the user data filesystem. Mail/cloud/Office units depend on mounts and bind to them; loss of a mount stops dependent units. Do not casually unmount a live filesystem for a test; perform mount-loss failure injection only on a disposable test VPS. Do not add `discard` or `fstrim` for image mounts: hole-punching can invalidate physical reservation. The installer deliberately does not put these image mounts in fstab (the stock Ubuntu/Debian fstrim timer enumerates fstab first). Audit local fstrim overrides before production.

## Обновления / Updates

No unattended Nextcloud/app upgrades are installed. Ubuntu/Debian security updates should be maintained by the operator. Record the current receipt, read release notes/advisories and compatibility constraints, take a consistent independent backup, test in staging and use the supported Nextcloud upgrade path. Do not edit only the version string or disable signature verification.

The core archive SHA256 is pinned in `ansible/site.yml`. App release URLs/versions are pinned there, signed file manifests are checked by `occ integrity:check-app` before enabling. The repository does not currently implement upgrading an existing installation: downloads refuse replacement, and the wizard refuses changed installation parameters. **Do not use a changed version of this installer as an upgrade command.**

Certbot's timer renews certificates; its deploy hook validates/reloads Nginx, Dovecot and Postfix. Test renewal with the command above and monitor expiry from outside. Never replace TLS with `-k` to make a failure disappear.

## Backup / restore: НЕ реализован / NOT implemented

An external encrypted backup and recovery scheduler are **not included**. A same-host file copy is not a backup and is lost with that host. Before real data, design a consistent backup of:

- Nextcloud database + file data + config and custom app source, coordinated for consistency;
- Maildirs and Postfix queue without competing writers;
- LDAP MDB through supported consistent export/snapshot;
- `/etc/mail-cloud-installer`, TLS/DKIM keys and all service configurations;
- actual package/app versions and supported restore sequence.

Protect the backup passphrase/key separately from the source VPS. Retention requires space for real user data plus change history, not merely today's small dataset. Restore onto a second clean isolated host; verify user logins, files/hashes, mail and Office saves. Never restore a running second MTA onto the same public domain/IP without an explicit migration plan.

## Приёмка / Acceptance checklist

This is the **broader operator production-qualification checklist**, not a claim that every item below passed. The actual Ubuntu test subset and remaining limitations are recorded in [the current review](../reports/spec-review.md); external-provider delivery, owner MFA login, every Office format/co-edit case and independent restore still need operator qualification:

1. Clean Ubuntu24.04 installation (Debian13 native acceptance deferred), interrupted DNS/download recovery, rerun without new passwords/formatting, reboot with all dependencies active and both mounts intact.
2. Real external HTTPS and TLS renewal; TOTP and backup-code login; fresh LDAP cloud/Mail/IMAP/submission logins, wrong and cross-account password rejection.
3. Two isolated browser users: no access to the other's private files/Maildirs, explicit shares work, revocation blocks later access. Mail can receive and send with an external provider; inspect SPF/DKIM/DMARC authentication results. Never send test email to arbitrary third parties.
4. SMTP25 never advertises AUTH; no external relay, unknown recipients or foreign authenticated sender; stopped Rspamd/mail Redis/missing DKIM key result in temporary rejection, not unsigned mail. Sliding hourly limit and retry queue-id deduplication survive Redis/service restarts.
5. Office: create ODT/ODS/ODP, open DOCX/XLSX/PPTX, edit/save/close/reopen/download/export PDF; two-user shared edit and read-only/revoked permissions; test interruption and restart only after save.
6. Load/resource/disk-full behavior, mount-loss refusal on **test** host, no hidden writes into underlying root filesystem; independent backup restoration.

Passing a subset cannot be reported as a full acceptance PASS.

## Interrupted bootstrap safety stops

A `.tmp` state file or an image without a UUID seal indicates interruption during a safety-critical write. The master intentionally stops rather than deleting/reformatting it. Inspect it locally as root, verify the corresponding operation completed, and recover state explicitly; never use a blind cleanup command. A normal DNS/download failure does not require resetting state. Rerunning the installation can stop/restart its own services; use it for bootstrap recovery, not as a zero-downtime production update mechanism.

## Ubuntu 24.04 profile

Ubuntu is the first native acceptance target. The master enables the standard Universe component, uses PHP8.3/FPM8.3, Dovecot2.3 with `/etc/dovecot/mail-cloud-ldap.conf`, and a Postfix3.8-compatible configuration. `/usr/local/lib/mail-cloud/platform.json` is root-owned non-secret runtime metadata, shared by every PHP helper. Original secret state records the OS/profile to prevent cross-distribution resume. Legacy state without a profile is accepted only on Debian13, its sole original target.

Native Ubuntu CI installs actual packages and tests parsers, LDAP-bind IMAPS authentication including wrong/cross passwords, LMTP mailbox isolation and Redis rolling limits/dedup/restart. It does not prove systemd dependencies, real mounts/cgroups, reboot, ACME, internet mail or Nextcloud/Office browser behavior. Debian's real-server checks remain explicitly deferred.

## SWAP assistance / Помощь с подкачкой

Current main wizard explains swap and offers additional missing space only when active swap is below4GiB. It asks for `CREATE SWAP` after clean-host/RAM/port/disk checks, keeps existing swap, and never weakens the pool reserve. Default managed file: `/var/lib/mail-cloud-installer/swapfile`0600 inside0700, identity seal `swap.json`, original fstab backup `fstab.before-swap`. Only ext4/XFS are automatically supported; other filesystems need operator-specific preparation. No automatic CoW changes, sparse files, swapoff or removal. The unchanged Ubuntu v1.0.0 snapshot predates this assistance.

A partially written/unsealed file or stale fstab temporary file stops safely; inspect locally rather than deleting or running mkswap blindly. A sealed inactive file may be reactivated on resume; its inode/size/density/type/UUID are verified first. fstab retains old entries, adds only the managed file and refuses conflicts. If a provider/container forbids swapon, arrange host-level swap or use a full VPS; do not bypass the guard. Swap is slower disk-backed memory, not a substitute for RAM. See [swapon(8)](https://manpages.debian.org/trixie/mount/swapon.8.en.html).

Mailbox secrets stay in `/etc/mail-cloud-installer/config.json`: each local login is a key in `passwords`, e.g. `passwords["alice"]`. The wizard prints an address/path/key mapping before service installation, never secret values. Existing accounts/passwords are not recreated on resume; `--config` still accepts the public `users` JSON list without interactive mailbox questions.
