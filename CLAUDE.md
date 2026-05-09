# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Before Any Code Change

Read in this order:
1. `docs/TASK_STATE.md`
2. `docs/DECISIONS.md`
3. `docs/KNOWN_ISSUES.md`
4. `docs/DEV_LOG.md` (latest entries first)

If instructions conflict — stop and ask.

## Stack

- **Backend**: Django 5.2 LTS, Python 3.13, PostgreSQL, Redis, Celery, django-tenants, django-ninja, Django Channels, uvicorn, WeasyPrint, FreeSWITCH
- **Frontend**: Vue 3 SPA (`frontend/`), Vite, PrimeVue (Aura theme), Tailwind CSS, Pinia, SIP.js
- **Infra**: Docker-only. No host installs.

## Common Commands (Docker-only)

```bash
# Start full dev stack
docker compose up -d --build

# Backend shell / management
docker compose run --rm web python manage.py <command>

# Migrations (always use migrate_schemas, not migrate)
docker compose run --rm web python manage.py migrate_schemas --shared --noinput
docker compose run --rm web python manage.py migrate_schemas --tenant --noinput

# Django system check
docker compose run --rm web python manage.py check

# Run backend tests (targeted)
docker compose run --rm web python manage.py test apps.<module>

# Seed test data (3 tenants + 6 users + platform_admin)
docker compose run --rm web python manage.py create_test_users

# Frontend typecheck (inside running container)
docker compose exec frontend npm run typecheck

# Frontend tests
docker compose exec frontend npm run test
```

## Docker Profiles

- Default: `web`, `celery`, `celery-beat`, `db`, `redis`, `migrate`, `frontend` (Vite dev server on port `$FRONTEND_DEV_HOST_PORT`, default 15173)
- `--profile frontend-prod`: nginx-served production build (`$FRONTEND_PROD_HOST_PORT`, default 14173)
- `--profile telephony`: FreeSWITCH SIP/WebRTC server

Ports are all parameterised via env vars (`WEB_HOST_PORT` default 18100, `DB_HOST_PORT` default 15432, etc.) to allow parallel project instances.

## Multi-Tenant Architecture

- **django-tenants** with one PostgreSQL schema per tenant.
- **Shared apps** (public schema): `apps.tenants`, `apps.billing`, `apps.users` — hold `Tenant`, `Domain`, `User`, `Membership`, `Plan`, `Feature`, `RolePermission`, `Payment`.
- **Tenant apps** (per-tenant schema): `apps.crm`, `apps.contracts`, `apps.channels`, `apps.integrations`, `apps.telephony`, `apps.audit`, `apps.notifications`, `apps.distribution`.
- Tenant is resolved from the request domain, `X-Tenant-Slug` header, `*.localhost` subdomain, or fallback to public schema in dev. See `apps/core/tenant.py` + `EnsureTenantContextMiddleware`.

## API Layer (django-ninja)

All authenticated API routes are under `/api/` via `config/api.py`. Key routers:
- `/api/auth/` — JWT login/logout/refresh/me/organizations/switch-tenant
- `/api/crm/` — deals, contacts, companies, pipelines, activities, tasks
- `/api/tenant/`, `/api/users/`, `/api/billing/`, `/api/distribution/`, `/api/contracts/`, `/api/channels/`, `/api/telephony/`, `/api/integrations/`, `/api/audit/`, `/api/notifications/`, `/api/dashboard/`, `/api/onboarding/`

**Public (no auth) Django views** — registered directly in `config/urls.py` (not ninja routers):
- `/sign/<token>/` — contract signing flow (Django template, not SPA)
- `/channels/webhook/...`, `/wh/.../...` — incoming webhooks
- `/telephony/...` — FreeSWITCH XML/ESL endpoints
- `/billing/yookassa/webhook/` — payment webhook
- `/notifications/telegram/bot-webhook/` — Telegram bot webhook

**JWT auth**: access token stored in JS memory, refresh token in httpOnly cookie.

## Access Control

All backend guards are in `apps/core/access.py`:
- `require_membership(request)` — active joined membership required, raises 402 if trial expired
- `require_roles(request, roles)` — role subset check
- `require_feature_access(request, feature_code)` — plan feature gate
- `require_crm_permission(request, entity, action)` — granular RBAC (entity × can_view/create/update/delete + scope all/team/own)
- `filter_crm_queryset_by_scope(request, qs, entity)` — scope-aware queryset filter

**Trial**: `require_membership`/`require_roles` raise 402 when trial expired. Billing/subscription endpoints pass `allow_trial_expired=True`.

**Feature gating**: `Plan` ↔ `Feature` M2M. Frontend composable: `useFeatureGate`. Backend decorator: `require_feature_access`. New features added via Django Admin without deploy.

## CRM Mode

`Tenant.crm_mode` selects the adapter (`builtin` / `amocrm` / `bitrix24`). All subsystems (distribution, contracts, channels, telephony) interact with CRM through the `CRMAdapter` protocol in `apps/crm/adapter.py`. `BuiltinCRMAdapter` uses ORM; external adapters use HTTP.

## Frontend Architecture

- Entry: `frontend/src/main.ts` → `App.vue` (single `<RouterView>`)
- Public routes: `/`, `/login`, `/register`, `/invite/accept`
- Protected app shell: `/app/**` via `AppLayout.vue` (Sakai fixed topbar + sidebar, `useLayout` composable in `frontend/src/layout/composables/layout.ts`)
- PrimeVue components globally registered with `P` prefix (`PButton`, `PDataTable`, etc.)
- Stores: `stores/auth.ts`, `stores/tenant.ts`, `stores/notifications.ts`, `stores/ui.ts`
- API layer: `frontend/src/api/` (http.ts base client + per-domain files)
- Route guards in `frontend/src/router/guards.ts` — enforces auth + role + feature checks

**Tenant context in requests**: frontend sends `X-Tenant-Slug` header (from auth store) on every API call.

**User-guide docs**: `docs/user-guide/*.md` are bundled into the SPA at build-time via `import.meta.glob`. The `frontend` container mounts them as a read-only volume at `frontend/src/docs/user-guide/`. Do not use symlinks — they break across Docker volume boundaries.

## WebSockets

- `ws/notifications/?token=...` — per-user notification stream + presence heartbeat (45s)
- `ws/chat/?token=...&slug=...` — per-channel messenger (tenant-isolated groups `chat.{slug}.channel.{id}`)
- Auth: JWT via query param, handled by `JWTQueryAuthMiddleware` in `config/routing.py`
- Redis channel layer used for group_send from Celery tasks

## Validation Checklist (after non-trivial changes)

1. `docker compose down && docker compose up -d --build`
2. `docker compose run --rm web python manage.py check`
3. Run targeted tests for changed modules
4. Manual HTTP check for affected pages (green tests ≠ working feature)

After non-trivial changes, update:
- `docs/DECISIONS.md` — if behaviour or invariant changed
- `docs/TASK_STATE.md` — status
- `docs/DEV_LOG.md` — date, files, validation, risks
- `docs/KNOWN_ISSUES.md` — if a bug was found or closed
- `docs/RELEASE_NOTES.md` — if user-visible (Russian, no technical details)
