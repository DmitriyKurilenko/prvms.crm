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
