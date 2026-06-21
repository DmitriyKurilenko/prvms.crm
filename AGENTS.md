# AGENTS: Protocol for This Repository

## Mandatory Read Order Before Any Code Change
1. docs/TASK_STATE.md
2. docs/DECISIONS.md
3. docs/KNOWN_ISSUES.md
4. docs/DEV_LOG.md (latest entries first)
5. Current task file (task.md when present)

If instructions conflict — STOP and ask user.

## Non-Negotiable Guardrails
- Stack: Django 5.2 LTS, Python 3.13, PostgreSQL, Redis, Celery,
  django-tenants, django-ninja, Django Channels, uvicorn, WeasyPrint, FreeSWITCH,
  Vue 3, Vite, PrimeVue, Tailwind CSS, Pinia, SIP.js, Docker
- Frontend: Vue 3 SPA в `frontend/`. Django НЕ рендерит HTML для ЛК.
- Docker-only development. No host installs.
- Do not remove production data without explicit approval.
- Никаких временных заплаток и «быстрых фиксов»: только устранение первопричины, с валидацией тестами и обновлением документации.

## Update Ritual (After Non-Trivial Changes)
1. docs/DECISIONS.md — если изменилось поведение/инвариант
2. docs/TASK_STATE.md — обновить статус (done/in-progress/blocked)
3. docs/DEV_LOG.md — дата, файлы, валидация, риски
4. docs/KNOWN_ISSUES.md — если найден или закрыт баг
5. docs/RELEASE_NOTES.md — если изменение видно пользователю:
   - Язык: русский
   - Без технических деталей 
   - Группировка по дате → «Новое», «Улучшения», «Исправления»

## Validation Baseline (Docker)
1. docker compose down
2. docker compose up -d --build
3. docker compose run --rm web python manage.py check
4. docker compose run --rm lint  — ruff (статанализ, профиль `tools`). Обязателен при любых изменениях `.py`.
5. Targeted tests for changed modules (backend; для фронта — `docker compose exec frontend npm run typecheck && npm run build && npm run test`)
6. docker compose run --rm e2e  — Playwright e2e (профиль `tools`, сам поднимает `web`+`seed`). Обязателен при изменениях UI/SPA.
7. Manual HTTP check for affected pages

If any step fails — fix and rerun. Partial validation ≠ done.
Шаги 4 и 6 — не опциональны: ruff и e2e заменяют «зелёные тесты» как критерий «работает».

## Decision Rules (Self-Limitation)
1. Если выполнение одной задачи занимает больше 2 итераций — остановись и спроси.
2. Если что-то непонятно из известных знаний — спроси.
3. Если не уверен на 100% что делать — спроси.
4. Если есть разные варианты решения — спроси.
5. Никогда не зацикливайся на одной проблеме. Если не нашлось решения за 2 итерации — спроси.
