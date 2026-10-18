# Ubuntu24.04 adaptation — preview

Owner-approved change, 2026-10-18: Ubuntu24.04 first; retain Debian13 profile but defer its native-server acceptance.

## Implemented
- Shared automatic platform profile and root-owned runtime metadata, exact resume guards; legacy profile-free state is Debian13-only.
- Ubuntu native PHP8.3 everywhere: package names, FPM, cron, occ and PHP bootstrap/provision/auth helpers. Standard Universe, no third-party PPA or distribution upgrade.
- Separate Dovecot2.3 main/LDAP templates using native bind/TLS/username/home syntax; Debian2.4 template retained.
- Postfix3.8-compatible compatibility level, existing mandatory TLS/auth/sender/milter/DKIM policy retained.
- CI: Python3.12/3.13, renders of both profiles, and a disposable Ubuntu24.04 native-package/parser/loopback integration suite.

- AppArmor: project LDAP local paths and targeted CODE AppImage userns policy, no global disable.

## Evidence so far
- Local 36 unit tests PASS; both profiles render 20 templates each using real Ansible; syntax/compile checks PASS.
- Ubuntu-native CI: pending execution for this revision. Do not report native checks passed before reading actual CI results.
- Complete target install/rerun/reboot/systemd/cgroup/mount/ACME/public SMTP/Nextcloud/Office browser checks: pending actual Ubuntu test VPS access. No production host was changed.
- Overall spec-review remains FAIL until the full accepted VPS checks are complete; Debian real-server testing is deliberately deferred.
