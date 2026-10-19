# Architecture / Архитектура

This describes the portable source configuration, not a claim that every production scenario has been tested. See [the acceptance report](../reports/spec-review.md) for actual evidence and limits.

## Request and identity paths

```text
Browser -- HTTPS443 --> Nginx -- private FPM socket --> Nextcloud
                           |                             |-- LDAP127.0.0.1:1389
                           |                             |-- MariaDB localhost
                           |                             `-- cloud Redis127.0.0.1:6379
                           |
                           `-- /hosting,/browser,/cool --> CODE127.0.0.1:9983
                                                          (own bounded systemd unit)
CODE -- TLS + WOPI token --> cloud hostname --> Nginx --> Nextcloud file API

Internet SMTP25(no AUTH) --> Postfix --> mandatory Rspamd milter127.0.0.1:11332
User submission587(STARTTLS + AUTH) --> Postfix             |-- DKIM
                                    |                    `-- mail Redis127.0.0.1:6380
                                    `-- LMTP socket --> Dovecot --> Maildir
User IMAPS993(TLS) -------------------------------------> Dovecot --> LDAP bind
```

- Nextcloud and mail users share LDAP credentials. Nextcloud Mail provisions only the logged-in user's mailbox and receives that user's password through its normal session middleware; no master mailbox password or cross-user credential sharing.
- `recovery_admin` is a separate local emergency administrator, not a mailbox. Nginx keeps the portal localhost-only until the operator enrols TOTP and backup codes. MFA enrolment is deliberately not simulated by the installer.
- Office frontend transport uses native Nginx HTTP/WebSocket proxying to the already supervised CODE service. WOPI callbacks still enter Nextcloud's normal token-checked PHP API. The legacy PHP CODE auto-start proxy and admin WebSocket are blocked; Office long polls do not occupy FPM workers.
- Internal cloud/mail hostname resolution uses project loopback entries, retaining real hostnames/SAN validation. When a packaged cloud-init Debian-family hosts template exists, the same narrow marked block is preserved there. Public DNS is checked separately against external resolvers, not the local hosts-aware stub.

## Storage and resource boundaries

| Boundary | Contents / policy |
|---|---|
| `/srv/mail-cloud/data` | Dense, UUID-sealed ext4 image: Nextcloud user files, PHP sessions, Maildirs, Postfix queue, Rspamd state and persistent mail Redis |
| `/srv/mail-cloud/staging` | Separate bounded2GiB ext4 image for CODE extraction/runtime and Nginx/PHP temporary files; not memory-backed `/tmp` |
| Outside user pool | Nextcloud application code, MariaDB, LDAP database, OS packages, TLS/DKIM and root-private installer state |
| Cloud Redis | Separate non-persistent64MiB cache/locking budget; not the persistent mail-policy Redis |
| Pool indicator | Read-only filesystem aggregate, no users' filenames/messages; only authenticated users can read counts |

Image size is raw capacity, not usable ext4 capacity. The default80GiB image yields less than80GiB usable; the UI reports measured filesystem bytes. Normal preflight reserves pool+25GiB outside allocation planning; an explicitly persisted TEST-only low-headroom mode does not change production defaults.

Pool-bound PHP/CODE/Dovecot/Rspamd/Postfix/persistent-mail-Redis units stop on data-mount loss. The underlying root mountpoint is not application-writable. Memory-only cloud Redis can remain independent. CODE/FPM/mail resource limits and separate staging bound temporary growth; they are not a promise of unlimited concurrent users. Do not TRIM or hole-punch image-backed mounts: that would invalidate physical reservation.

## Mail and deployment controls

- SMTP25 never advertises AUTH. Submission587 requires STARTTLS; IMAPS993 requires TLS. LDAP, DB, Redis, CODE and filter ports stay private.
- Postfix rejects relaying, unknown local recipients and an authenticated user's foreign envelope sender. Rspamd additionally enforces MIME-From ownership, a readable signing key and a successful signing result; unavailable policy/signing or Redis causes temporary refusal.
- DKIM signs the exact selected domain (`use_esld=false`), including a subdomain. A Redis-time rolling window limits authenticated outgoing messages to50/hour/account with queue-ID retry deduplication and persistent state.
- Ubuntu24.04 selects PHP8.3/Dovecot2.3; retained Debian13 selects PHP8.4/Dovecot2.4. Packages come from signed native repositories; no PPA or runtime Docker. AppArmor remains enabled, with narrow project-specific rules.
- Root-only parameters/secrets, a lock, immutable deployment/profile parameters and volume seals support interrupted bootstrap recovery without formatting or rotating passwords. They do not implement an in-place OS/app upgrade.
- Core SHA256 and app signatures are checked before execution. Actual OS package versions are receipted. Certbot renewal uses a validation/reload hook. External encrypted backup/restore, provider DNS APIs and external deliverability qualification are **not included**.
