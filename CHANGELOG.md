# Changelog

## [0.2.1] — 2026-05-11

### Fixed (DEC-034: HTTPS root cause)
- **`/healthz` returns 200 regardless of Host header.** New `HealthCheckBypassMiddleware` placed first in `MIDDLEWARE`, before `django_tenants.TenantMainMiddleware`. Liveness probes from container orchestrators (Docker healthcheck, k8s, Traefik) no longer depend on `Domain`/`Tenant` state.
  - Root cause: `TenantMainMiddleware` ran before URL resolution and returned 404 for `Host: localhost`/`127.0.0.1` since no matching `Domain` row exists in shared schema. Docker healthcheck hit `curl http://localhost:8000/healthz` → 404 → container marked unhealthy → Traefik 2.x silently filtered out the routers → Let's Encrypt never issued a certificate.
- **`frontend-app` healthcheck uses IPv4 literal `127.0.0.1`.** Busybox-`wget` in `nginx:alpine` resolves `localhost` to `::1` first and does not fall back to IPv4; nginx listens IPv4-only here.

### Added
- `vps-deployment/scripts/start-all.sh`: preflight in `check_build_prereqs` — `crm_prvms` refuses to start without `PUBLIC_HOSTNAME` in `.env.prod`. Prevents the silent `Host(``)` Traefik-label scenario.

### Security
- `.gitignore`: removed the blanket `/vps-deployment` rule (was hiding new tracked files); added narrow patterns for secrets only (`vps-deployment/**/.env*`, `acme.json`, `logs/`, `media/`); generalized `.venv/` → `.venv*`.
- Removed `vps-deployment/crm_prvms/.venv.current_on_server` — a snapshot of production `.env.prod` containing real `SECRET_KEY`, `DB_PASSWORD`, `FIELD_ENCRYPTION_KEY`, `REDIS_PASSWORD`, `HERMES_API_KEY`, `OPENCODE_API_TOKEN`. File was untracked locally but lived in the working tree. **Rotate exposed keys.**

### Closed Issues
- KNOWN_ISSUES #12: `crm.prvms.ru` Let's Encrypt certificate finally issuable; previously masked by two independent unhealthy-container conditions and a missing `PUBLIC_HOSTNAME` in server env. DEC-033 (Traefik restart on deploy) retained as defensive measure.

## [0.2.0] — 2026-05-10

### Refactoring (DEC-032: Full A-E)
- **AI Assistant**: removed redundant `tenant` FK from `AIConversation` (lives in tenant schema); renamed `herMes_conversation_id` → `hermes_conversation_id`; regenerated migration; removed duplicate test suite.
- **Vite dev**: `working_dir` changed from `/app` to `/srv/app` — fixes 500 EISDIR on SPA route `/app`.
- **Frontend types**: `CrmContact` expanded with `position/messenger_id/source/esign_agreement_*`; `CrmDeal` got `contracts/chat_sessions/source` refs; `IvrMenu.options` strictly typed; all 12 `(x as any)` casts eliminated; `tsconfig.json` added `skipLibCheck: true`.
- **Backend API split**: `apps/users/api.py` (769 LOC) → shim (18 LOC) + `auth_api.py` (login/register/refresh/logout/me/orgs/switch/invite) + `team_api.py` (members/invite/role/permissions) + `managers_api.py` (manager-profiles/days-off).
- **Tenant provisioning**: new `apps/tenants/services.py` with `provision_tenant()` and `ensure_default_pipeline()` — single public entry point replacing private cross-app imports.
- **Frontend decomposition**: `CRMView.vue` (2023 LOC) removed; new `CompaniesView` (167 LOC), `PipelinesView` (480 LOC), `StatsView` (135 LOC); `/app/crm` redirects to `/app/deals`; sidebar updated with new items.
- **Frontend logger**: `utils/logger.ts` with scoped `debug/info/warn/error` — `debug`/`info` silent in production; replaced `console.log` in stores and views.
- **Bare except**: 23 broad `except Exception:` narrowed to `TokenError`, `DoesNotExist`, `RequestException`, `OSError`, `JSONDecodeError`; remaining broad excepts in `telephony/tasks.py` justified with explicit comment (greenswitch library).

### Fixed (DEC-030: Functional Hardening)
- Pipeline/Stage seeding now runs at tenant registration and onboarding skip — `auto_create_lead` in messengers no longer fails for new tenants.
- Distribution: added synonym fallback (`new_deal` ↔ `new_lead`) in `try_distribute()`; default rule trigger changed to `new_deal`.
- Session: refresh cookie `SameSite` set to `Lax` in dev, `None` in production; `secure=not DEBUG`.
- `auto_create_lead` wrapped in try/except with error logging to `message.error`.
- Quick-create contact/company buttons added to DealsView create/edit forms.
- Added `builtin_crm` to `DistributionLog.SOURCE_CHOICES`.

### Fixed (DEC-031: UI Error Handling)
- 11 views/components: added `catch` blocks with PrimeVue Toast notifications for all API calls.
- `<PToast />` placed in `App.vue`.
- `stores/tenant.ts`: added `planLoaded` getter; `hasFeature` checks `plan !== null` before feature lookup.
- `DashboardView`, `AppMenu`: feature-dependent blocks defer locking until plan data is loaded.
- `SameSite=None` always for refresh cookie (cross-origin `fetch()` requirement).
- `auth.ts`: `isAuthenticated` uses token presence, not user object; catch in `initialize()` no longer clears `tenant_slug`.
- `http.ts`: `refreshAccessToken()` catch no longer calls `setAccessToken(null)` on error.

### Added
- `frontend/nginx.conf`: `/static/` location for Django collected-static from shared volume; `/assets/` with immutable long-term cache.
- `frontend/src/router/guards.ts`: token-presence guard — if token exists but user data missing (page refresh race), fetches `me()` before redirecting to login.
- `vps-deployment/`: production deployment configuration (Docker Compose, deploy script, env template).
- CHANGELOG.md

### Closed Issues
- KNOWN_ISSUES #4: frontend typecheck → green (`npm run typecheck`)
- KNOWN_ISSUES #5: ai_assistant migration tenant FK → 118/118 tests
- KNOWN_ISSUES #6: Vite `/app` 500 EISDIR → `/srv/app` working_dir
- KNOWN_ISSUES #7: auto_create_lead → pipeline seeded at registration
- KNOWN_ISSUES #8: distribution trigger mismatch → synonym fallback
- KNOWN_ISSUES #9: page refresh logout → SameSite + token guard
- KNOWN_ISSUES #10: missing quick-create in DealsView → + buttons
