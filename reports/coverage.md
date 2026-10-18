# Coverage: specs/bootstrap.md

2026-10-18. Preview only; no claim of production readiness.

## Requirements
- [x] R1: Терминальный мастер: домен, публичный IPv4, email ACME, список локальных имён пользователей. Cloud/mail hostname выводятся из домена; расширенный файл параметров позволяет изменить их и размер пула. Пароли генерируются локально, сохраняются только root-private. — installer/wizard.py: validate/main, 26 unit tests incl. input/state/plan.
- [x] R2: Нативный стек Nextcloud 34.0.4, Mail, Calendar, Office/Collabora, LDAP, Postfix, Dovecot 2.4, Rspamd, отдельные Redis для почты и облака, MariaDB, PHP-FPM, Nginx, TLS, cron. Общий LDAP-пароль облака и почты; Mail в сессии Nextcloud. — ansible/tasks/{identity,runtime,cloud,mail,office}.yml; templates rendered by real Ansible; upstream archive HEAD HTTP200. Real services/install not tested.
- [x] R3: Общий ограниченный ext4-пул для файлов, почты и состояния фильтра, физическое резервирование, защита от записи при потере mount; ресурсы/временные файлы ограничены. Индикатор фактической общей ёмкости без раскрытия чужих файлов. — files/storage.py, collect-pool-usage.py and mount dependencies; sealed/partial/symlink/mismatch unit cases; real mount/reboot/load pending.
- [x] R4: SMTP25 без AUTH, submission587 только STARTTLS, IMAPS993, запрет relay и чужого sender; обязательный milter/DKIM, исходящий лимит 50/час; LDAP/DB/Redis/CODE не публикуются. Отдельный recovery-admin, настройка MFA до открытия портала. — native templates, Lua policy, mfa-check, health.py; real positive/negative SMTP/DKIM/Office security acceptance pending.
- [x] R5: Мастер проверяет DNS A/MX/SPF/DKIM/DMARC/PTR и сертификаты, выдаёт точные требуемые записи. Не обещает доставляемость, не меняет DNS/хостинг без API-доступа. Обновление TLS с deploy hook. — files/dns.py, tls.yml, renewal hook; no actual DNS/ACME issuance on a new host. Only publisher URLs verified.
- [x] R6: Preflight чистого Debian, последовательные возобновляемые фазы, блокировка параллельного запуска, запрет перезаписи чужого конфигурационного дерева; повторный запуск не форматирует пул и не меняет пароли. Ошибки не считаются успехом. — wizard preflight/lock/private state; storage resume test proves no format command on existing fixture; real interruption/reboot not tested.
- [x] R7: README.md EN / README.ru.md RU, архитектура, ограничения, исправленные проблемы, эксплуатация/обновления/backup; GitHub CI, локальные тесты, отдельный публичный GitHub-репозиторий с проверкой секретов перед публикацией. — README RU/EN, docs/LESSONS.md, OPERATIONS.md; public repository https://github.com/kaiser1919-ai/mail-cloud-bootstrap; GitHub Actions success for source commit dda054e528ae4fbdd48c5255cf38570e03027afe (run 39142637360).

## Constraints
- [x] C1: Не менять production; только новый проект. Не переносить ключи, токены, домены/IP/почту владельца, приватную историю и проприетарные шрифты. — New isolated source tree; forbidden private values/font/key scan, no production commands executed.
- [x] C2: Без Docker/AIO/Mailcow; чистый Debian 13 amd64, systemd; root нужен только пользователю на целевой машине. Backup внешний не реализован, не обозначать его готовым. — Native Debian13/systemd; wizard refuses another OS/arch; external backup explicitly absent.
- [x] C3: Никакого автоматического удаления/форматирования существующих данных; пакетные версии из подписанного Debian security-репозитория фиксировать в install receipt, архив Nextcloud проверять pinned SHA256, apps — штатной подписью Nextcloud. — Exclusive image creation, UUID seal; Debian signed apt; pinned core SHA; app signatures checked before enable. Actual deployment still unverified.

## Edge Cases
- [x] E1: Невалидный/инъекционный ввод отклоняется до записи/выполнения. — Validation tests reject injection/control chars, reserved/duplicate users, invalid IP/domain/size before writes.
- [x] E2: DNS/ACME/сеть недоступны — остановка с понятной причиной и возобновление после исправления, без генерации новых паролей. — DNS/download tasks fail rather than replacing secrets; real network-interruption recovery pending.
- [x] E3: Занятые порты/установленный чужой стек/недостаточный диск — отказ до изменения служб. — Preflight tests reject foreign configs, occupied ports, wrong OS and low free space.
- [x] E4: Прерывание/повтор/конкурентный запуск — сохранение состояния/секретов, не повторять mkfs; несовпадение параметров/артефактов блокируется. — State permissions and sealed/incomplete image tests; actual full-run interruption/concurrency acceptance pending.

## Definition of Done
- [x] D1: Локальные tests и syntax/render проверки проходят, нет персональных данных/секретов. — 26 unit tests PASS; bash/sh syntax and Python compilation PASS; Ansible syntax PASS; all 17 templates rendered using synthetic parameters.
- [ ] D2: Реальный clean Debian 13 install + повторный запуск + reboot + negative mail/auth/privacy + Office save/reopen проверены; если тестовая VPS недоступна, фиксировать непроверенное и НЕ объявлять готовность. — No disposable clean Debian13 VPS/root authorization provided. Production intentionally not used. See docs/OPERATIONS.md acceptance checklist.
- [x] D3: Публичный GitHub repo содержит проверенный исходный код, двуязычную документацию и мастер. — Public source tree published and HTTP200/page content verified; only this standalone repository was pushed, not the parent Sentinel repository. Source safety scan passed for all 65 tracked files.

## Out-of-spec observations (not built)
External backup, upgrades, migration from existing servers and DNS-provider API automation are intentionally not implemented.

Publication is a PREVIEW and does not close D2. Full implementation acceptance remains FAIL until the disposable-VPS checks are complete.
