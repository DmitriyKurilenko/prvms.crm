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
4. Targeted tests for changed modules
5. Manual HTTP check for affected pages

If any step fails — fix and rerun. Partial validation ≠ done.
