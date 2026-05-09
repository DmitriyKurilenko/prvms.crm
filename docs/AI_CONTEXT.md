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
- HERMES_API_URL, HERMES_API_KEY в .env

## Django app: apps/ai_assistant

- Models: AIConversation, AIMessage (tenant-scoped)
- API: POST /api/ai/chat/ → Hermes → ответ → stored
- Consumer: ws/ai/ для real-time ответов
- Tasks: sync с Hermes, обработка webhook от Hermes cron

## Frontend

- Store: frontend/src/stores/ai.ts
- View: frontend/src/views/AssistantView.vue
- API: frontend/src/api/ai.ts
- Route: /app/assistant

## Нерешённые вопросы

(пусто)