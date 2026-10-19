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

## Restrictive root clone permission regression, 2026-10-19
A read-only check of a fresh root clone under umask077 showed app source directories700/files600. Copying those modes unchanged would make the local pool app unreadable to its PHP service account. The installer now assigns root ownership and normalizes public app files/directories to644/755; a native CI regression exercises the actual Ansible task against a700/600 fixture and verifies unprivileged read/no-write. Previous native evidence above predates this patch; its CI result is tracked separately before claiming the new source passed. Full VPS disk/mount/browser acceptance remains open.

2026-10-19: root-umask copy regression + explicit low-headroom test mode covered by all three successful jobs of CI39206838664, code92e90028788c255783fae3eac4940e0888df7417. Clean real Ubuntu VPS installation has started; full acceptance still pending.

## Real VPS progress and latest regression evidence, 2026-10-19
- Code2a15ff9895c5e9a237624a815d62768094f4bbf0:51unitPASS; GitHubCI39209334760 all3jobsSUCCESS. Earlier DNS/FPM patch4d55735 CI39209208878SUCCESS, including real FPM startup with socket-backed stderr.
- Real bounded filesystem stress completed:81939922944bytes write/read SHA256 in1081.74s, own fixture cleaned, system reserve preserved. Not an application stress/reboot/Office acceptance result.
- Clean-host discoveries fixed in source/tests: LDAP runtime-before-slaptest;118safe upstream licence symlinks; explicit public DNS rather than systemd-resolved hosts synthesis; native FPMsyslog/socket-readiness; bounded waiting for unattended-upgrades lock without killing security updates. Actual public DNS initial check nowPASS.
- Full master/service/browser/reboot acceptance remains in progress; do not treat native container CI or filesystem stress as full D2 completion.
