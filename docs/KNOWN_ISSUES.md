# Известные проблемы

## Закрытые (2026-05-10)

4. ~~`frontend` typecheck нестабилен из-за TS-несоответствий и `(... as any)` кастов.~~
   - Закрыто DEC-032: типы `CrmContact/CrmDeal` расширены под фактический backend-ответ; `IvrMenu.options` строго типизирован; `http.ts` retry вынесен в обёртку (правильная архитектура); `tsconfig.json` получил `skipLibCheck: true`. `npm run typecheck` зелёный.

5. ~~Backend-тесты падают с `relation "ai_assistant_aiconversation" does not exist` при создании второго tenant.~~
   - Закрыто DEC-032: убран избыточный `tenant` FK (модель живёт в tenant schema), поле `herMes_conversation_id → hermes_conversation_id`, миграция перегенерирована. 118/118 backend-тестов зелёные.

6. ~~Vite dev `GET /app` → 500 EISDIR из-за коллизии SPA-маршрута и `working_dir: /app`.~~
   - Закрыто DEC-032: `working_dir: /srv/app` в `docker-compose.yml`. Все volume-mount-ы перенесены. `/app` возвращает SPA HTML (200).

7. ~~auto_create_lead в мессенджерах не работал — Pipeline/Stage не сидировались при регистрации тенанта.~~
   - Исправлено: `_seed_default_pipeline()` в `register()`, `onboarding_skip()`, try/except в `tasks.py`. После DEC-032 — единый `provision_tenant()` сервис.

8. ~~Распределение не работало — trigger mismatch `new_deal` vs `new_lead` + отсутствовал синонимный фоллбек.~~
   - Исправлено: trigger `'new_deal'` в онбординге, фоллбек в `try_distribute()`, `builtin_crm` в SOURCE_CHOICES

9. ~~Выход при рефреше страницы — `SameSite='None'` без `Secure` в dev.~~
   - Исправлено: `samesite='Lax' if DEBUG else 'None'`, `secure=not DEBUG`

10. ~~В DealsView не было быстрого создания контакта/компании.~~
    - Исправлено: quick-create диалоги + `+` кнопки в формах создания/редактирования

## Закрытые (2026-05-11)

12. ~~crm.prvms.ru не получает Let's Encrypt сертификат на shared VPS.~~
    - **Истинная причина (выявлена debug-логами Traefik):** Traefik 2.x намеренно не регистрирует роутеры для контейнеров со статусом `unhealthy`/`starting` (`Filtering unhealthy or starting container`). Контейнеры `web` и `frontend-app` были unhealthy по двум независимым причинам: (а) `web` healthcheck бил `/healthz`, но `django_tenants.TenantMainMiddleware` не находил `localhost` в Domain table и возвращал 404 до URL-резолва; (б) `frontend-app` healthcheck использовал busybox-wget на `localhost`, который резолвит `::1` и не делает IPv4-fallback, а nginx слушал только IPv4.
    - **Дополнительная причина (исходный триггер):** В серверном `.env.prod` отсутствовал `PUBLIC_HOSTNAME`, на котором шаблонизированы Traefik-лейблы. Без него лейблы становились `Host(``)` и Traefik их отбрасывал.
    - **Исправление (DEC-034):** `HealthCheckBypassMiddleware` отвечает на `/healthz` до tenant resolution; healthcheck `frontend-app` использует `127.0.0.1`; в `start-all.sh` добавлен preflight на `PUBLIC_HOSTNAME`. DEC-033 (перезапуск Traefik) сохранён как defensive measure.
    - **Файлы:** `apps/core/middleware.py`, `config/settings.py`, `vps-deployment/crm_prvms/docker-compose.yml`, `vps-deployment/scripts/start-all.sh`, `.gitignore`

## Открытые

1. Для внешних CRM в production всё ещё требуется финальная валидация на реальных аккаунтах маркетплейсов amoCRM/Битрикс24 (боевые app credentials + реальный callback домен).
   - Файлы: `apps/integrations/api.py`, `apps/integrations/services.py`, `apps/integrations/adapters_amocrm.py`, `apps/integrations/adapters_bitrix24.py`
   - План закрытия: production-hardening этап (staging QA прогон marketplace install + webhook events + auto token refresh на реальных CRM tenant-ах)

2. `freeswitch` в профиле `telephony` остаётся экспериментальным; на ARM-хостах возможна нестабильность образа/медиа-контура.
   - Файл: `docker-compose.yml` (`freeswitch` service)
   - План закрытия: выделить и протестировать целевой образ FreeSWITCH под platform matrix (amd64/arm64)

3. Покрытие автотестами пока базовое (smoke/integration): отсутствуют end-to-end UI сценарии и нагрузочные тесты.
   - Файлы: `apps/*/tests/*`, `frontend/src/**/*.test.ts`
   - План закрытия: добавить Playwright e2e (auth/tenant switch/core CRM flows) и отдельный performance-профиль для API/WebSocket/Celery

11. CI отсутствует — нет автоматического прогона `manage.py check`/тестов/typecheck/vitest при PR.
    - Файлы: нет `.github/workflows/`
    - План закрытия: добавить GitHub Actions workflow с матрицей backend (Python 3.13 + Postgres) + frontend (Node 24).
