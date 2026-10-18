# Опыт внедрения / Deployment lessons

Перенесены архитектурные решения и причины реальных сбоев, а не персональные логи, одноразовые разрешения или слепая цепочка старых скриптов. / This captures architectural fixes, not private logs, one-off production grants or an unsafe replay of historical migration commands.

| Проблема / Failure | Решение / Resolution |
|---|---|
| Dovecot 2.3 examples fail on 2.4 | Use 2.4 configuration/storage versions, native `passdb ldap`, `fields`, `%{user}` syntax and validate with `doveconf` before start. |
| One browser portal was confused with merely matching emails | Shared local LDAP identities, native Nextcloud Mail provisioning and credential middleware. Separate recovery admin; no invented OIDC service or cross-domain SSO claim. |
| Base64-shaped LDAP passwords were accidentally treated as encoded content | Generate hex service passwords, hash the actual literal string with salted SSHA, and use explicit LDIF base64 encoding for attributes. |
| Public cloud exposure before recovery MFA | Default localhost-only HTTPS; owner enrols TOTP and backup codes; opening parses only **enabled** providers, not the disabled-provider list. |
| Missing Postfix `tlsmgr` broke STARTTLS even with valid certificates | Preserve native Debian master services; explicitly ensure tlsmgr exists. Do not replace master.cf with a tiny incomplete list. |
| Global service instances competed with isolated runtimes | Mask stock LDAP/PHP/Redis; start explicit project units. Mail instances are masked until parser/DNS acceptance, including across reboot. |
| Cloud locking and outgoing mail policy shared volatile Redis | Separate Redis instances/ports and limits; mail Redis persists rolling rate history. Rspamd and milter failures must tempfail. |
| Sender login could send as a different user | SMTP sender ownership through LDAP map, submission-only AUTH after TLS; Lua verifies both envelope and MIME sender, DKIM presence and known account. |
| Dense images lost reservation through lazy inode initialization / TRIM | Disable lazy inode/journal init, disallow discard and verify allocated blocks. Never format an existing/unsealed image on resume. Keep automatic TRIM off image mounts. |
| Missing mount silently redirected writes to root | Require mount units and BindsTo dependencies; capacity collector refuses a missing/wrong filesystem instead of publishing root-disk numbers. |
| Tiny `/tmp` filled during Office downloads/extraction | Downloads stay in the project tree; PHP/Nginx/Office temp is on a separate bounded disk filesystem, not RAM tmpfs. |
| CODE spawned inside PHP inherited an incompatible sandbox/lifetime | Own supervised CODE service and bounded resource budget. Loopback listener only; never expose 9983 publicly. |
| Broad `custom_apps/*.php` permission fixed one problem but opened others | Exact CODE proxy.php FastCGI exception only, plus explicit Office routes and websocket support. |
| Mail/Calendar JS became 403 or the wrong MIME | Permit real signed static assets including `.mjs`; keep data/config/hidden files forbidden. |
| GitHub CDN HTTP/2 transfers stalled on the RU host | HTTP/1.1, bounded connect/total/no-progress timeouts and retries; pinned publisher release, no arbitrary mirrors. |
| Application availability was checked in one cached PHP process | Separate occ executions per operation/user; real browser acceptance remains mandatory. |
| A green service status was mistaken for saved Office documents | Discovery is only a health check. Save/close/reopen, permissions, collaboration, restart-after-save and download integrity need actual browsers. |
| A small local snapshot was mistaken for backup | Explicitly leave external backup incomplete until retention capacity, scheduling and independent restoration are proven. |

## Sources checked / Проверенные первичные источники

Consulted 2026-10-18; the `latest` manuals may describe newer versions than this pinned reproduction. They are not version compatibility evidence by themselves.

- [Nextcloud source installation](https://docs.nextcloud.com/server/latest/admin_manual/installation/source_installation.html): native stack, permissions, background jobs and FPM operational considerations.
- [Dovecot native LDAP](https://doc.dovecot.org/main/core/config/auth/databases/ldap.html): LDAP authentication configuration.
- [Rspamd ratelimit](https://docs.rspamd.com/modules/ratelimit/): Redis-backed rate limiting concepts. This project ports the original custom sliding-window policy, **not** a claim to use that module unchanged.

The installer is a new portability implementation of the original native architecture, not a byte-for-byte copy of a person's production machine. Independent clean-host acceptance remains open.
