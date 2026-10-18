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
- Ubuntu-native CI **PASS**: [39145337644](https://github.com/kaiser1919-ai/mail-cloud-bootstrap/actions/runs/39145337644), source `5430880d1e91427b84adba70679b6f955a2dfa95`. Both Python3.12/3.13 offline jobs and the native Ubuntu job succeeded.
- Complete target install/rerun/reboot/systemd/cgroup/mount/ACME/public SMTP/Nextcloud/Office browser checks: pending actual Ubuntu test VPS access. No production host was changed.
- Overall spec-review remains FAIL until the full accepted VPS checks are complete; Debian real-server testing is deliberately deferred.

## Native checks actually exercised
- All installer package names resolve/install from Ubuntu24.04 main/universe. No PHP PPA.
- Target's native Ansible2.16 syntax plus both platform renders, alongside development Ansible2.19 tests.
- AppArmor policy compilation (not kernel enforcement), MariaDB configuration parsing, Nginx/Postfix/Dovecot/Rspamd/FPM parsers and local PHP8.3 source lint.
- Real loopback LDAP + Dovecot IMAPS with hostname-verified test TLS, correct/wrong/cross passwords; LMTP sends only synthetic local mail and the other mailbox remains empty.
- Real Redis rolling50 limit, duplicate queue token and restart persistence.
- Actual Rspamd3.8 HTTP task API: DKIM_SIGNED + MC_OUTBOUND_ALLOWED; foreign MIME sender, unknown authenticated user, missing key and stopped Redis yield soft reject + MC_OUTBOUND_BLOCKED. No external SMTP delivery was performed.
- Service aliases tested with native postmap and LDAP map lookup. Fixed overescaped domain regex using a literal [.] class.

These tests do NOT execute the complete installer on a systemd host or validate filesystem mounts/cgroups/reboot, public ACME/DNS/SMTP, Nextcloud/Mail/Office browser behavior or real AppArmor enforcement. Those remain target VPS checks, not silently marked PASS.
