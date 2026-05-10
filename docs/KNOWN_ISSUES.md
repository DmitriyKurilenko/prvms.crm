# Известные проблемы

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

4. `frontend` typecheck (`npm run typecheck`) остаётся нестабильным из-за накопленных TS-несоответствий (часть в сторонних типах, часть в локальных типах API/views).
   - Файлы: `frontend/src/api/http.ts`, `frontend/src/views/CRMView.vue`, `frontend/src/views/SubscriptionView.vue`, `frontend/src/composables/useSIPPhone.ts` и др.
   - План закрытия: выделить отдельный hardening-этап для чистки TS-типов и выравнивания зависимостей `vite/vitest` + `undici` типов

5. Backend-тесты (5 шт.): `test_auth_api`, `test_invites_api`, `test_tenant_resolver` падают с `relation "ai_assistant_aiconversation" does not exist` при создании второго tenant-а в тестовой БД.
   - Файлы: `config/settings.py` (`apps.ai_assistant` в `TENANT_APPS`), `apps/ai_assistant/models.py` (FK к неправильному app_label), `apps/users/tests/test_auth_api.py`, `apps/users/tests/test_invites_api.py`, `apps/tenants/tests/test_tenant_resolver.py`
   - Корневая причина: `apps.ai_assistant` добавлен в `TENANT_APPS`, но миграция не закоммичена (untracked). Модель `AIConversation` ссылается на `messenger_channels.ChatSession` и `crm.Deal` — смесь public/tenant FK.
   - План закрытия: закоммитить миграцию `ai_assistant/0001_initial.py`, либо перенести `apps.ai_assistant` в `SHARED_APPS` если модели public-schema.

6. Vite dev-сервер: `GET /app` → `500 EISDIR` из-за совпадения SPA-маршрута `/app` с рабочей директорией контейнера `/app`.
   - Файлы: `frontend/vite.config.ts`, `docker-compose.yml` (working_dir, volume mount)
   - Влияние: только dev-режим; `/app/dashboard`, `/app/onboarding` и остальные дочерние маршруты работают. Production nginx не затронут.
   - План закрытия: изменить рабочую директорию с `/app` на `/srv/app` в docker-compose, либо добавить middleware-перезапись в Vite config.
