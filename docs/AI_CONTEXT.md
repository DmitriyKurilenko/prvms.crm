# AI Ассистент — Контекст обсуждения (2026-05-09)

## Архитектурные решения

| Компонент | Решение |
|-----------|---------|
| AI провайдер | OpenCode.ai (облачный сервис) |
| Hermes настройка | API_TOKEN для OpenCode провайдера |
| Hermes | Docker, API server port 8642, профили per-tenant, cron, skills |
| Django ↔ Hermes | HTTP /v1/chat/completions, HERMES_API_URL + bearer token |
| Хранение диалогов | PostgreSQL, tenant-scoped AIConversation/AIMessage |
| CRM tools | Python skills в hermes profile volume, schema_context для tenant data |
| Multi-tenant изоляция | Hermes profile = tenant slug, volume для persistence |
| Проактивные уведомления | Hermes cron → skill → webhook → Django → Notification → WebSocket |

## Функционал

1. **Чат с AI** — отдельная страница `/app/assistant`
2. **AI в чате с клиентом** — команда `/ai` в ChannelsView, передаётся deal context
3. **Проактивные напоминания** — ежедневный дайджест, контроль просроченных задач (Hermes cron jobs)

## Docker

- `hermes` сервис в docker-compose
- Profile directories в named volume `hermes_profiles`
- HERMES_API_URL, HERMES_API_KEY, HERMES_WEBHOOK_SECRET в .env

## Django app: apps/ai_assistant

- Models: AIConversation, AIMessage (tenant-scoped)
- API: POST /api/ai/chat/ → Hermes → ответ → stored
- Consumer: ws/ai/ для real-time ответов
- Tasks: sync с Hermes, обработка webhook от Hermes cron
- Hermes webhook endpoint: POST /ai/hermes-webhook/

## Frontend

- Store: frontend/src/stores/ai.ts
- View: frontend/src/views/AssistantView.vue
- API: frontend/src/api/ai.ts
- Route: /app/assistant
- Menu: AI Ассистент добавлен в AppMenu
- ChannelsView: кнопка AI и команда /ai для помощи в чате

## Hermes Skills (CRM tools)

- apps/ai_assistant/hermes_skills/crm_get_deal.py
- apps/ai_assistant/hermes_skills/crm_create_task.py

## Реализовано

- [x] docker-compose.yml — hermes сервис (nousresearch/hermes-agent:latest, API server)
- [x] .env — HERMES_API_KEY, OPENCODE_API_KEY
- [x] apps/ai_assistant/ — models, api, consumers, tasks, services
- [x] config/api.py — ai_router
- [x] config/routing.py — ws/ai/ consumer
- [x] config/settings.py — HERMES_API_URL=http://prvmscrm-hermes:8642
- [x] config/urls.py — hermes webhook endpoint
- [x] frontend/src/stores/ai.ts
- [x] frontend/src/views/AssistantView.vue
- [x] frontend/src/api/ai.ts
- [x] frontend/src/router/index.ts — /app/assistant route
- [x] frontend/src/layout/AppMenu.vue — AI Ассистент menu item
- [x] frontend/src/views/ChannelsView.vue — /ai команда и кнопка
- [x] Hermes Skills — crm_get_deal, crm_create_task
- [x] Hermes webhook endpoint для cron уведомлений
- [x] Миграции для AIConversation/AIMessage (0001_initial.py)

## Конфигурация Hermes (prvmscrm-hermes)

Docker compose service с `API_SERVER_ENABLED=true`, API на порту 8642.
Конфиг: `/opt/data/config.yaml` — provider: opencode-go, base_url: https://opencode.ai/zen/go/v1, default model: qwen3.6-plus.
Креды: `OPENCODE_GO_API_KEY` в .env (скопирован из работающего внешнего контейнера).
Access: GATEWAY_ALLOW_ALL_USERS=true, API_SERVER_KEY=hermes_dev_key_12345.

## Нерешённые вопросы

- (нет)