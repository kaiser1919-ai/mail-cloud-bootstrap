# Ubuntu24.04 adaptation — native CI and real VPS evidence

Owner-approved change, 2026-10-18: Ubuntu24.04 first; retain Debian13 profile but defer its native-server acceptance.

## Implemented
- Shared automatic platform profile and root-owned runtime metadata, exact resume guards; legacy profile-free state is Debian13-only.
- Ubuntu native PHP8.3 everywhere: package names, FPM, cron, occ and PHP bootstrap/provision/auth helpers. Standard Universe, no third-party PPA or distribution upgrade.
- Separate Dovecot2.3 main/LDAP templates using native bind/TLS/username/home syntax; Debian2.4 template retained.
- Postfix3.8-compatible compatibility level, existing mandatory TLS/auth/sender/milter/DKIM policy retained.
- CI: Python3.12/3.13, renders of both profiles, and a disposable Ubuntu24.04 native-package/parser/loopback integration suite.

- AppArmor: project LDAP local paths and targeted CODE AppImage userns policy, no global disable.

## Historical initial-preview evidence (2026-10-18)
- Local 36 unit tests PASS; both profiles render 20 templates each using real Ansible; syntax/compile checks PASS.
- Ubuntu-native CI **PASS**: [39145337644](https://github.com/kaiser1919-ai/mail-cloud-office/actions/runs/39145337644), source `5430880d1e91427b84adba70679b6f955a2dfa95`. Both Python3.12/3.13 offline jobs and the native Ubuntu job succeeded.
- At that initial checkpoint the real target was not yet available; the current real-VPS checkpoint below supersedes that historical limitation. No production host was changed.
- That initial review was FAIL pending the real tests. Consult the current review, not this historical checkpoint; Debian real-server testing remains deliberately deferred.

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

## Current verified Ubuntu checkpoint — 2026-10-19
This supersedes the historical in-progress checkpoints above. See the complete [spec review](spec-review.md) and [coverage](coverage.md).

- Verified code `2c25cd1ef3f152d14f9a7602cae20ac74a84496d`:64 local unit tests, syntax and20templates×2profiles PASS; [CI39220165998](https://github.com/kaiser1919-ai/mail-cloud-office/actions/runs/39220165998), all3jobsSUCCESS. Documentation-only publication does not alter that implementation.
- Real clean Ubuntu24.04 systemd installation, interrupted resumes and complete full reruns PASS; final rerun ok136/failed0. Root credential and both volume-seal hashes remained unchanged; package receipt written. Concurrent master invocation refused.
- Actual final reboot changed boot ID and preserved13 active services/timers, both sealed ext4 mounts,4GiB swap, native WOPI URLs and internal hostname resolution; post-boot master --check PASS. A pre-boot1MiB file matched SHA256 and was deleted204.
- Controlled pool loss stopped all six pool-bound PHP/CODE/mail/persistent-Redis services. Underlying mountpoint remained empty and application-unwritable; memory-only cloud Redis correctly remains independent.
- Real SAN ACME/verified HTTPS, A/MX/SPF/DKIM/DMARC/PTR and renewal staging dry-run/deploy hook PASS. External MX TCP25 EHLO works; no external message sent, reputation/deliverability not certified.
- Fresh browser cloud/Mail login without a second password,0pageerrors, WebDAV write/read/wrong/cross-password/privacy and own cleanup PASS. Real local two-way SMTP→IMAPS, exact-domain DKIM cryptographic verification and own UID-only cleanup PASS. Actual stopped-milter refusal/restore PASS; remaining rate/policy failures separately exercised by native CI.
- Real native Office ODT edit/save/download-content/close/reopen PASS, saved text visually inspected. The final post-reboot cold test also passed with own cleanup204. Nginx HTTP/WebSocket transport avoids PHP proxy starvation; legacy PHP auto-start/admin endpoints blocked. CODE remains in its bounded systemd unit; AppArmor remains enabled.
- Concurrent Office editing plus256MiB random WebDAV write/read/isolation and two local512KiB mail attachments PASS. DAV run34.87s; sampled minima root6162337792bytes,MemAvailable781832KiB,SwapFree4142800KiB. Post-load Office save/reopen and own fixture cleanup PASS. This does not certify many-user or long-duration capacity.
- Earlier full bounded filesystem stress:81939922944bytes SHA256 write/read in1081.74s, pool reserve1139945472bytes/root free6875688960bytes; own fixture removed. Not application throughput.80GiB raw image yielded83955703808bytes filesystem total, not80GiB usable. Ordinary production pool+25GiB reserve unchanged; reduced headroom was explicitly TEST-only.
- Recovery MFA enrolment/public opening remain with the owner; portal stays localhost-only. External encrypted backup/restore is NOT implemented. Debian13 actual server acceptance, external-provider mail delivery, all Office formats/co-editing and broader production qualification remain separate, not silently marked PASS.

## Wizard/SWAP UX follow-up — 2026-10-19
- Main now asks mailbox count and each login, maps every address to its root-private password key, and offers opt-in additive swap preparation; both README files start with the wizard and minimum requirements.
- Verified installer codeccc5a72; ed1c5c5 changes only the CI-only swap fixture and README spacing.80 unit tests pass locally on Python3.13 and on real Ubuntu Python3.12; syntax/render40 pass. Real complete master rerun ok136/failed0, unchanged config/seal hashes and pre-existing4GiB swap.
- Actual own16MiB mkswap/swapon/swapoff plus private fstab fixture/backup, UUID/inode/density/modes and repeat checks passed. Own fixture removed, existing swap untouched; real system fstab was not modified by the fixture. The default new4GiB file plus reboot was NOT retested here. In the CI container only the filesystem/kernel-activation boundary is simulated; real mkswap/file/fstab logic still runs.
- [New CI39281808820](https://github.com/kaiser1919-ai/mail-cloud-office/actions/runs/39281808820) is queued at publication, not certified green. Earlier Ubuntu release/CI remain immutable successful baseline evidence. No Debian-server acceptance claimed.
