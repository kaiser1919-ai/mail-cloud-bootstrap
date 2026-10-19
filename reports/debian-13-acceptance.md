# Debian 13 — real isolated VPS acceptance

Date: 2026-10-19. Tested implementation: `a50802c64430abaea1c9689fcb3ac95e7fde1ac2` (final release documentation does not change runtime code).

## Environment and scope
- New Debian 13.3 amd64/systemd VPS; 2 vCPU, about 2 GiB RAM, initially no swap; ext4 system disk nominally 100 GiB.
- Interactive master with two synthetic accounts, 80 GiB **raw** shared image, separate 2 GiB staging and explicit owner-authorised `--test-low-headroom`. Ordinary production pool+25 GiB reserve remains unchanged. This tight test disk is not a production recommendation.
- Native PHP8.4/Dovecot2.4/MariaDB/Postfix/Nginx/Rspamd, pinned Nextcloud and four signed apps. No production system or parent-domain mail was changed; no private keys or accounts were copied from another server.

## Observed results
- Wizard created new dense root-private 4 GiB swap from zero, saved identity seal and exact additive fstab entry with backup. Resume verifies existing swap rather than reformatting it.
- Full installation/resume and completed full master repeat: 129 successful tasks, zero failures (Debian skips Ubuntu-only tasks). Per-mailbox password file/key locations displayed without password values.
- Real SAN TLS and A/MX/SPF/DKIM/DMARC/PTR checks passed. New test-only DKIM TXT matched both authoritative nameservers and public resolvers. ACME staging renewal and deploy hooks passed.
- WebDAV write/read/SHA checks, cross-account denial and wrong/cross-password rejection passed. Local SMTP STARTTLS→IMAPS delivery passed both directions with cryptographic DKIM validation, including 512 KiB attachments. Own UID-only cleanup passed.
- Browser Mail automatically connected the correct account without a second password prompt; all folders opened, zero page errors. Eight simultaneous authenticated TLS IMAP connections (four per account) passed.
- Native Office ODT edit/save/download-content/reopen passed, including a bounded concurrent load: 256 MiB random WebDAV writes/readbacks in31.86s plus two mail attachments. Saved text after load was visually verified; Office fixture deletion returned204. Sampled minima: root free5490405376bytes, MemAvailable604200KiB, SwapFree4051172KiB.
- Controlled data-mount loss stopped all six pool-bound services; the underlying root mountpoint stayed empty and not writable by the cloud account.
- Actual reboot changed boot ID. All four credential/storage/swap state hashes stayed identical; both sealed ext4 mounts, 4 GiB managed swap, exact single fstab entry, internal hostname routing, native WOPI URLs and13 services/timers persisted. Pre-boot1MiB DAV fixture matched SHA256 after reboot and was removed204. Postboot master `--check` exited0; mail/DKIM delivery and milter failure454/refusal/restoration passed again.
- 82 unit tests, both OS template renders, syntax checks and real Ansible TLS readiness/negative-CA fixture passed. [CI for the tested code](https://github.com/kaiser1919-ai/mail-cloud-office/actions/runs/39292141981) completed SUCCESS.

## Fixed actual failures
1. CODE listening on TCP did not imply `/hosting/discovery` was ready. Added bounded verified HTTPS200+XML readiness before the existing CLI activation, with real503/non-XML/retry and untrusted-CA regression tests. No TLS ignore, arbitrary sleep or memory-limit increase.
2. Dovecot login process limit2 dropped simultaneous Mail folder connections despite sequential health passing. Both native profiles now use bounded8 login/16 IMAP processes; per-user/IP4 and systemd384MiB/64tasks remain. Native parser, eight-connection and fresh browser retests passed.

## Limits
This certifies the stated functional test, not general production security or many-user throughput. The full80GiB filesystem sweep was performed in the earlier **Ubuntu** acceptance, not repeated on Debian; Debian used bounded application load on its new80GiB raw pool. Raw size is not usable ext4 capacity. No arbitrary external recipient mail was sent; Internet delivery/reputation, every Office format/export/co-edit scenario, long-duration load, owner MFA enrolment and disaster recovery are not certified. The portal remains externally403 until the owner enrols recovery-admin TOTP/backup codes. Independent encrypted backup/restore is **not implemented**.

## Final postboot confirmation — PASS
Cold native Office ODT edit/save/download/reopen passed after reboot; saved text was visually verified and own cleanup returned204. Known own fixture prefixes are absent. All observed private TCP listeners (including MariaDB) are loopback-only. CODE/FPM NRestarts=0; CODE processes stayed within their bounded unit. Final root free5481947136bytes, MemAvailable870432KiB, SwapFree4120652KiB. External cloud/mail HTTPS both returned403 with certificate verification0, as intended before owner MFA enrolment. All four state hashes were checked unchanged again.
