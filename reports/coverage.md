# Coverage: specs/bootstrap.md

Ubuntu adaptation, approved scope revision 2026-10-18. Preview, not production-ready.

## Requirements
- [x] R1: Терминальный мастер: домен, публичный IPv4, email ACME, список локальных имён пользователей. Cloud/mail hostname выводятся из домена; расширенный файл параметров позволяет изменить их и размер пула. Пароли генерируются локально, сохраняются только root-private. — wizard validation, generated root-private state, no additional platform prompt; unit/plan tests.
- [x] R2: Нативный стек Nextcloud 34.0.4, Mail, Calendar, Office/Collabora, LDAP, Postfix, Dovecot 2.3 на Ubuntu / 2.4 на Debian, Rspamd, отдельные Redis для почты и облака, MariaDB, PHP-FPM, Nginx, TLS, cron. Общий LDAP-пароль облака и почты; Mail в сессии Nextcloud. — Ubuntu profile PHP8.3/Dovecot2.3/Postfix3.8-compatible native stack; Debian profile retained. Actual full Nextcloud/Mail/Office target deployment pending.
- [x] R3: Общий ограниченный ext4-пул для файлов, почты и состояния фильтра, физическое резервирование, защита от записи при потере mount; ресурсы/временные файлы ограничены. Индикатор фактической общей ёмкости без раскрытия чужих файлов. — storage.py seals/reservation tests, persistent shared pool and mount-bound units; live mount/reboot/load acceptance pending.
- [x] R4: SMTP25 без AUTH, submission587 только STARTTLS, IMAPS993, запрет relay и чужого sender; обязательный milter/DKIM, исходящий лимит 50/час; LDAP/DB/Redis/CODE не публикуются. Отдельный recovery-admin, настройка MFA до открытия портала. — separate native23/24 LDAP/TLS templates, mandatory milter/DKIM, Lua50/h, MFA gate. Full authenticated SMTP/negative filter and browser security acceptance pending.
- [x] R5: Мастер проверяет DNS A/MX/SPF/DKIM/DMARC/PTR и сертификаты, выдаёт точные требуемые записи. Не обещает доставляемость, не меняет DNS/хостинг без API-доступа. Обновление TLS с deploy hook. — DNS utility, SAN ACME and renewal hooks; no real target DNS/ACME run yet.
- [x] R6: Preflight чистой Ubuntu 24.04 / Debian 13, последовательные возобновляемые фазы, блокировка параллельного запуска, запрет перезаписи чужого конфигурационного дерева; повторный запуск не форматирует пул и не меняет пароли. Ошибки не считаются успехом. — preflight/lock/private state; exact OS/profile resume check incl. legacy Debian-only handling. Full interruption/rerun/reboot acceptance pending.
- [x] R7: README.md EN / README.ru.md RU, архитектура, ограничения, исправленные проблемы, эксплуатация/обновления/backup; GitHub CI, локальные тесты, отдельный публичный GitHub-репозиторий с проверкой секретов перед публикацией. — Public GitHub source, RU/EN READMEs, operations/lessons, CI and source safety scan. Ubuntu-native CI results tracked in ubuntu-adaptation.md.
- [x] R8: Автоматически выбирать профиль Ubuntu 24.04 LTS: PHP 8.3, нативные пакеты без PPA, конфигурации Dovecot 2.3/LDAP/TLS и совместимый Postfix. Все PHP helpers/cron/FPM используют выбранный профиль; Ubuntu universe подключается штатно при необходимости. AppArmor сохраняется: локальные разрешения для проектных LDAP-путей и адресное userns-разрешение только CODE AppImage на Ubuntu, без отключения глобальной защиты. Сохранить профиль Debian 13/PHP 8.4/Dovecot 2.4; серверная приёмка Debian отложена. Профиль сохраняется, смена ОС/профиля при resume отклоняется. CI проверяет обе ветки шаблонов и нативные парсеры/пакеты Ubuntu в изолированной среде, не production. — platforms.json + wizard + all PHP helpers/cron/FPM; native23 LDAP and Postfix compatibility profiles; both profile renders/unit tests PASS. Ubuntu24.04 native CI PASS on code 5430880d1e91427b84adba70679b6f955a2dfa95; run 39145337644. Native Ansible2.16, AppArmor/MariaDB/Postfix/Dovecot/Rspamd/PHP/Nginx parsers and real loopback integration checks passed.

## Constraints
- [x] C1: Не менять production; только новый проект. Не переносить ключи, токены, домены/IP/почту владельца, приватную историю и проприетарные шрифты. — Only isolated public project modified; no production server commands, personal data/keys/fonts excluded.
- [x] C2: Без Docker/AIO/Mailcow; чистая Ubuntu 24.04 LTS или Debian 13 amd64, systemd; root нужен только пользователю на целевой машине. Backup внешний не реализован, не обозначать его готовым. — Native stack, no runtime Docker/PPA; container is only an ephemeral CI test harness. External backup explicitly absent.
- [x] C3: Никакого автоматического удаления/форматирования существующих данных; пакетные версии из подписанных штатных security-репозиториев выбранной ОС фиксировать в install receipt, архив Nextcloud проверять pinned SHA256, apps — штатной подписью Nextcloud. — Exclusive image creation/seals; signed native apt repos + standard Ubuntu Universe, core pinned SHA, app signature gates; actual deployment pending.

## Edge Cases
- [x] E1: Невалидный/инъекционный ввод отклоняется до записи/выполнения. — Input/injection/control character/user/IP/size tests reject before changes.
- [x] E2: DNS/ACME/сеть недоступны — остановка с понятной причиной и возобновление после исправления, без генерации новых паролей. — DNS/download failures stop without rotating secrets. Real interrupted target/network acceptance pending.
- [x] E3: Занятые порты/установленный чужой стек/недостаточный диск — отказ до изменения служб. — Preflight tests reject unsupported OS/foreign config/occupied ports/low disk.
- [x] E4: Прерывание/повтор/конкурентный запуск — сохранение состояния/секретов, не повторять mkfs; несовпадение параметров/артефактов блокируется. — State and image resume tests plus cross-OS/profile rejection; actual concurrency/reboot acceptance pending.

## Definition of Done
- [x] D1: Локальные tests и syntax/render проверки проходят, нет персональных данных/секретов. — 36 unit tests PASS, actual Ansible render20templates x2profiles PASS, Python compile/shell/Ansible syntax checks PASS; Ubuntu-native CI PASS: https://github.com/kaiser1919-ai/mail-cloud-bootstrap/actions/runs/39145337644.
- [ ] D2: Реальный clean Ubuntu 24.04 install + повторный запуск + reboot + negative mail/auth/privacy + Office save/reopen проверены; проверка Debian 13 отдельно отложена по поручению владельца; если тестовая VPS недоступна, фиксировать непроверенное и НЕ объявлять готовность. — Ubuntu24.04 full target VPS install/rerun/reboot/public mail/Nextcloud/Office/private-browser acceptance still pending access. Debian13 server acceptance explicitly deferred.
- [x] D3: Публичный GitHub repo содержит проверенный исходный код, двуязычную документацию и мастер. — Published standalone source repository: https://github.com/kaiser1919-ai/mail-cloud-bootstrap. No parent/private repository push.

## Out-of-spec observations (not built)
Ubuntu adaptation source checks are separate from full VPS acceptance. No Docker runtime, external backup, PPA, cross-OS in-place migration or automatic distribution upgrade. Review is requirements-based, not an independent-agent security audit.

Verified Ubuntu adaptation code: `5430880d1e91427b84adba70679b6f955a2dfa95`, [GitHub Actions](https://github.com/kaiser1919-ai/mail-cloud-bootstrap/actions/runs/39145337644). Subsequent documentation-only commit does not alter that code. Full VPS acceptance D2 remains open; Debian real-server checks are deferred.

## R9 — explicit reduced-headroom test (2026-10-19)
- [x] Persisted opt-in test mode, 8 GiB initial headroom; normal +25 GiB unchanged; resume mode change refused — wizard.py, test_pressure.py.
- [x] Before/after phase guards, 2 GiB system reserve, 250 MiB MemAvailable/512 MiB SwapFree — pressure_guard.py, site.yml.
- [x] Download/extraction budget and bounded isolated pool write/read SHA256 runner with own-fixture cleanup — fetch.py, tests/stress_pool.py.
- [x] RU/EN warnings distinguish raw image/usable capacity and filesystem/app stress.
- [ ] Real VPS stress run, full install/rerun/reboot/application acceptance — pending; not replaced by unit tests.
- Local checks: 43 unit tests pass; Ansible syntax passes. Current native CI and VPS evidence pending for this change.

Evidence update: code `92e90028788c255783fae3eac4940e0888df7417`, GitHub Actions run `39206838664`: ubuntu-native and offline Python3.12/3.13 all SUCCESS. Local 43 unit tests, Ansible syntax and 20 templates ×2 profiles PASS. Live VPS installation in progress; no live acceptance claim.

### Real Ubuntu test progress (2026-10-19)
- Native packages installed on real systemd Ubuntu24.04; dense80GiB data and2GiB staging images created/mounted, AppArmor managed profiles loaded.
- 2GiB bounded fixture write/read SHA256 PASS, fixture cleanup confirmed; root free7751073792bytes after reservation. Actual data filesystem capacity83955703808bytes, available83079892992bytes before application data (raw image80GiB, not usable80GiB).
- First install exposed R6 bug: slaptest needs its /run directory before the LDAP service starts. Fixed in fb97c12081df6b2fc5fef8535394cef8999c60c6; native CI now removes the fixture directory and executes the actual creation task before validation. 44 local tests PASS. Resume and full stress ongoing; not full acceptance.

### Pinned archive regression (R2/C3/R6)
Official Nextcloud34.0.4 archive SHA256 matches the pinned digest. Its30144members include118relative licence symlinks, sometimes chained. Full member-table validation now permits only bounded internal chains ending at regular files; rejects duplicate paths, hardlinks, link/file ancestors, cycles/dangling/outside links and special files. 48 unit tests and syntax PASS; the actual pinned archive member table passes validation. Real target extraction/install still pending; no protection/sha/space guard disabled. Previous LDAP fix fb97c12 native CI39207315615 all3jobs SUCCESS; LDAP validation/start/populate also passed on the resumed real VPS.

### Real bounded full-pool stress — PASS (filesystem only)
Requested80GiB, actual81939922944bytes written/read SHA256 verified in1081.74s; pool available1139945472bytes at peak, root free6875688960bytes, MemAvailable1480644KiB/SwapFree4164424KiB at completion. Own fixture cleanup confirmed, pool available83079880704bytes afterward. This tests the bounded filesystem, not concurrent Nextcloud/mail/Office behavior. Config and both volume-seal hashes unchanged across interrupted resumes; real parallel invocation refused.
Archive fix7b844fa: CI39208320667 all3jobs SUCCESS and real core extraction completed. Next real-host findings: local DNS stub synthesizes /etc/hosts answers; FPM cannot reopen journald socket via/proc/self/fd/2. Build now uses explicit public DNS resolvers, native syslog FPM logging and socket readiness check. 50unitPASS; new nativeCI/live verification pending. Full D2 still incomplete.

### Root-umask core extraction follow-up (R2/R6/C3)
Real ACME SAN certificate obtained and FPM socket readiness confirmed after syslog fix. Initial Nextcloud install then exposed implicit directory700 from tarfile data_filter under rootumask077; console.php itself644 but its parents inaccessible. Fresh publisher-code extraction now normalizes755dirs/644files/755executables before rename. Interrupted preview repair changes only known public core directories, never config/custom_apps/data or existing files. 53unitPASS including config.php0600 preservation. Actual app install still to verify. Latest previouscode2a15ff9 CI39209334760all3SUCCESS; aptwait also resumed naturally after security updater released lock, without killing it.

### Real cloud/browser progress and session-store fix
Core install, LDAP mapping and actual credential check PASS; all4official apps downloaded, signatures verified before enable. Codeebd537f CI39210796553all3SUCCESS. Public TLS verification PASS for both SAN names; both portal endpoints403 before MFA. Mail native parsers PASS; activation correctly waits for testDKIM DNS. Browser session exposed read-only default PHPsessionpath under strict sandbox: bounded private0700data/php-sessions, targeted writable path and PHPGC now configured.54unitPASS; native FastCGI persistence regression added; live browser retest pending. No portal MFA bypass/public opening performed.
