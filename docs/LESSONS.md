# Опыт внедрения / Deployment lessons

Перенесены архитектурные решения и причины реальных сбоев, а не персональные логи, одноразовые разрешения или слепая цепочка старых скриптов. / This captures architectural fixes, not private logs, one-off production grants or an unsafe replay of historical migration commands.

| Проблема / Failure | Решение / Resolution |
|---|---|
| Dovecot 2.3 examples fail on 2.4 | Select native 2.3 on Ubuntu (`passdb { driver=ldap }`, separate LDAP file, `%u`, ssl_cert/ssl_key) versus 2.4 on Debian (versioned config, `passdb ldap`, `fields`, `%{user}`). Validate both separately; removing only an OS guard is unsafe. |
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

- [Collabora built-in CODE upstream](https://github.com/CollaboraOnline/richdocumentscode): AppImage extraction fallback, fontconfig and resource requirements; not proof of the service unit on a new host.

The installer is a new portability implementation of the original native architecture, not a byte-for-byte copy of a person's production machine. Independent clean-host acceptance remains open.

## Ubuntu adaptation sources (2026-10-18)

- [Ubuntu PHP](https://packages.ubuntu.com/noble/php-fpm), [Dovecot](https://packages.ubuntu.com/noble/dovecot-core), [Postfix](https://packages.ubuntu.com/noble/postfix), [Rspamd](https://packages.ubuntu.com/rspamd): native Noble package branches, not guesses based on apt similarity.
- [Pinned Nextcloud PHP requirements](https://raw.githubusercontent.com/nextcloud/server/v34.0.4/composer.json), [version gate](https://raw.githubusercontent.com/nextcloud/server/v34.0.4/lib/versioncheck.php): PHP8.3 falls within this pinned source's declared range; no third-party PHP PPA needed.
- [Dovecot2.3 LDAP](https://doc.dovecot.org/2.3/configuration_manual/authentication/ldap/): distinct bind/database syntax.

The earlier Debian-only profile is retained; actual Debian acceptance follows Ubuntu, not vice versa. Ubuntu-native CI is partial integration evidence, never a replacement for a full target VPS run.

Ubuntu24.04 also restricts unprivileged user namespaces: a targeted AppImage policy and packaged LDAP profile local include are provided; AppArmor is never globally disabled. [Ubuntu24.04 release notes](https://documentation.ubuntu.com/release-notes/24.04/). Policy parsing in CI does not prove kernel enforcement or real Office behavior.

Additional native-CI findings: preserve Postfix queue ownership with `cp -a` (a generic Python copytree fixture changed ownership and correctly failed postsuper); test service-alias regexes with real postmap and both positive/negative domains, not a substring assertion; test the target Ubuntu Ansible2.16 as well as development2.19. Actual Rspamd3.8 task requests also verify guard behavior rather than relying on a parser-only green result.

## Реальная Ubuntu проверка: порядок LDAP и ссылки в upstream архиве
- CI fixture заранее создавал /run/mail-cloud-ldap и скрывал ошибку первого запуска: slaptest нуждается в PID-каталоге ещё до старта systemd-службы. Установщик создаёт каталог до валидации; native regression начинает с отсутствующего каталога и выполняет реальный Ansible task.
- Pinned Nextcloud34.0.4 содержит относительные symlink на licence-файлы, в том числе цепочки. Запрет любых ссылок блокировал штатный архив. Распаковщик валидирует полную таблицу: запрещены дубликаты, абсолютные/внешние/висячие/циклические ссылки, link/file ancestors, hardlink/devices/FIFO; допускаются только относительные внутренние цепочки до обычного файла (максимум32 звена), затем применяется tarfile data filter. SHA256/границы размера/системный резерв не отключаются.
- Источник для поведения extraction filter: https://docs.python.org/3/library/tarfile.html#tarfile.data_filter (проверено19.10.2026). Такие ошибки нельзя считать проверенными только по syntax/unit CI без реального clean-host install.
- Ubuntu systemd-resolved может синтезировать ответ из /etc/hosts и для dig через127.0.0.53. После локального hostname routing публичную DNS-проверку выполнять явно через внешний resolver (1.1.1.1, fallback8.8.8.8), не через локальный stub. Реальная проверка показала localhost/127.0.0.1 черезstub и правильный IPv4 через оба внешнихresolver.
- PHP-FPM `error_log=/proc/self/fd/2` работает с обычным pipe в CI, но не с journald stream socket (ENXIO). Используется штатный `error_log=syslog`/идентификатор mail-cloud-php; после systemd start ждать реальный Unix socket. NativeCI воспроизводит socket-backed stderr. Официальная конфигурация: https://www.php.net/manual/en/install.fpm.configuration.php (проверено19.10.2026).
- На чистой Ubuntu фоновое unattended-upgrades может держать dpkg frontend lock. Мастер и apt-фаза ждут штатную блокировку до600секунд; не убивают обновление безопасности и не удаляют lock-файлы.
- Ещё один rootumask077 эффект: tarfile data_filter игнорирует mode директорий архива, поэтому implicitmkdir создавал700 и PHP не мог читать console.php. Свежий распакованный publisher-code нормализуется755/644 (исполняемые файлы755) до atomicrename. Resume-совместимость исправляет только директории известного публичного core-code; config/custom_apps/data и существующие файлы не chmodятся. Отдельные тесты подтверждают сохранениеconfig.php0600.
- Настоящий browserlogin выявил ещё не покрытую CLIauthcheck ошибку: ProtectSystem=strict оставлял стандартный /var/lib/php/sessions read-only. FPM использует отдельный php-sessions0700 внутри boundeddata-пула с точечным ReadWritePaths; PHPGC включён для нестандартного каталога. NativeCI проверяет два настоящих FastCGI-запроса с одним cookie, сохранение счётчика/UID/0600 и удаление только своей тестовой сессии. Защита файловой системы глобально не ослабляется.
- Ansible `script` переносит только один файл во временный каталог: helper с sibling-import `mc_runtime` там не запускается, хотя прямой запуск из исходников успешен. Mail provisioner устанавливается рядом с runtime-модулем и вызывается через `command`; unit проверяет wiring всех зависимых script, nativeCI выполняет реальную copy-задачу, проверяет module resolution вне исходного каталога и PHP syntax встроенных программ. Нельзя маскировать это добавлением случайного рабочего каталога в PYTHONPATH.
- Реальное SMTP→IMAP письмо для поддомена выявило `DKIM_SIGNED`, но с `d=` родительского домена: Rspamd по умолчанию `use_esld=true`. Задано `use_esld=false`, чтобы домен подписи совпадал с выбранным доменом и опубликованным DNS-ключом, без изменения рабочей зоны родителя. Native regression проверяет фактический signing-symbol domain для apex и subdomain, а не только наличие символа. [Официальная конфигурация DKIM](https://docs.rspamd.com/modules/dkim_signing/) (проверено19.10.2026).
- Установка Office не должна переписывать root-owned core через `maintenance:mimetype:update-js`: это генерация core/js/mimetypelist.js, а не регистрация Office. Штатные `app:enable` и `richdocuments:activate-config` сохраняются; лишняя core-write задача удалена, invariant проверяется unit. В узкий repair старой preview-extraction включён публичный themes-каталог, приватные config/data по-прежнему не меняются.
