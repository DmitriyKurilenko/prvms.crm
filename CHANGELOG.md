# Changelog

## [0.2.6] — 2026-05-16

### Mobile UI adaptation (DEC-037) — user-visible

Root cause of "mobile sidebar won't hide" was a **CSS-specificity bug**, not JS: the desktop rule `.layout-static .layout-sidebar` (specificity 0,2,0) always beat the mobile media-query rule `.layout-sidebar` (0,1,0) — media queries add no specificity and the container always carries `.layout-static`. The sidebar stayed permanently visible on phones.

- **Structural layout fix:** desktop static/overlay modes moved under `@media (min-width: 992px)`, mobile off-canvas drawer + mask under `@media (max-width: 991px)` — mutually-exclusive ranges remove the specificity collision structurally (no `!important` patch). JS (`useLayout`, `AppSidebar` route watcher) unchanged — it was already correct.
- **Single-source responsive layer in `styles/main.css`:** `.form-grid/.form-row-2/.form-row-3` are now global primitives that collapse to one column ≤640px (scoped duplicates removed from 6 files so the global rule is not shadowed by `[data-v-*]` specificity); `.section-header` wraps ≤640px; `.p-dialog`/`.p-drawer` capped at `max-width: 95vw` globally (one place vs 12 per-dialog widths); topbar shrinks on ≤991px, wordmark hidden ≤480px.
- **Card-mode tables:** new `v-responsive-table` directive tags the table root `.rt-cards` and copies each column header into `td[data-label]`; ≤767px every row becomes a labelled card, the empty/`colspan` row stays a single block. Selectors are PrimeVue-class-agnostic (semantic `thead/tbody/tr/td`) and verified against PrimeVue 4.4 source. Applied to all 24 `PDataTable`.
- **Per-view:** `tasks-layout`/`assistant-layout` collapse to one column ≤768px; `.tabs-bar`/`.tab-bar` (Contracts/Team/Pipelines) wrap.

Validation: `manage.py check` 0 issues; `npm run typecheck` EXIT=0; `npm run build` EXIT=0; **5/5** vitest; bundle contains `rt-cards`/`min-width:992px`/`max-width:991px`/`data-label`; dev SPA `/app` → 200. Browser QA on a real device not run in this environment (no browser) — KNOWN_ISSUES #17.

### Refactor (P0–P2, DEC-036) — behaviour-preserving, no user-visible change

Decomposition of monolithic modules following the DEC-032 pattern (sibling modules + thin back-compat shim). All public imports keep working unchanged.

**Backend.**
- `apps/crm/api.py` 864 LOC → 23-line shim + `_api_common` + `schemas` + domain modules `contacts_api`/`companies_api`/`pipelines_api`/`deals_api`/`activities_api`/`stats_api`.
- `apps/integrations/api.py` 705 LOC → shim + `connections_api`/`webhooks_api`/`oauth_api` (`_api_common` for router/schemas/request-coupled helpers; `services.py` stays request-agnostic).
- `apps/contracts/services.py` 558 LOC → shim + `mapping`/`pdf`/`otp`/`esign_agreement`/`signing` (acyclic import graph). `test_signing_flow` OTP patch targets repointed to `apps.contracts.signing.*` (behavioural assertions unchanged).
- All CRM `XIn`/`XPatchIn` schemas centralised in `apps/crm/schemas.py`.

**Frontend.**
- Restored the DEC-032 “0 `as any`” invariant: `CrmDeal` completed (`created_at`/`expected_close_date`/`loss_reason`); SIP.js boundary typed via `Web.SessionDescriptionHandler`.
- `useApiCall` composable — single enforcement point for the DEC-031 error-toast invariant; `DealsView` fully migrated.
- View decomposition (pattern: parent owns state/WS/loading, child is presentational, reactive form objects passed by reference, actions via emits):
  - `DealsView` 760→623 — `QuickContactDialog`, `QuickCompanyDialog`, `DealFormDialog`, `DealDetailDialog`.
  - `IntegrationsView` 645→415 — `IntegrationSetupCard`, `ConnectionsTable`, `IntegrationErrorsDialog`.
  - `ChannelsView` 605→452 — `ChannelsTab` and `ChatsTab` (WS lifecycle stays in the parent; `ChatsTab` owns only the scroll DOM node and exposes `scrollToBottom()` so the parent's WS/send/load handlers keep deciding *when* to scroll — a 1:1 control-flow-preserving relocation).

**Validation gate** strengthened with a real `vite build` (full `.vue` compilation + component prop/import resolution) in addition to `vue-tsc --noEmit`.

Validation: `manage.py check` clean; **128/128** backend tests; targeted crm/integrations/contracts 24/24; `npm run typecheck` EXIT=0; `npm run build` EXIT=0 (706 modules); **5/5** vitest.

## [0.2.5] — 2026-05-13

### Fixed (Messenger channels)

Messenger pipeline rewrite — four independent bugs fixed in a single pass:

**`normalize_incoming_payload` returns `None` for unsupported update types.**
Previously, a Telegram `edited_message` update would fall through to `payload.get('message') or payload`, returning the whole Update object and producing `chat_id='unknown'`. Incoming messages from the same user would either be lost or merged into a single session. MAX `bot_started` events created ghost sessions with `chat_id='unknown'`. Now: Telegram `edited_message` is correctly routed to the session; `callback_query`, `inline_query` and other unsupported types return `None` and are ignored. MAX `bot_started` returns `None` and is ignored.

**`register_telegram_webhook` now requests `edited_message` updates.**
`allowed_updates` expanded from `['message']` to `['message', 'edited_message']`.

**Explicit pipeline/stage lookup with user-visible failure.**
`_find_pipeline_and_stage()` logs a warning when no pipeline or no stage is found. `_auto_create_lead()` writes `message.error = 'Воронка или этап не настроены — сделка не создана'` and sets `delivered=False` so ops can see the exact cause in the UI instead of a silent missing deal.

**Bare `except Exception` replaced with typed handlers.**
All `providers.py` functions (and outbound path in `tasks.py`) now use `requests.RequestException` instead of a bare `except`, so network failures, HTTP errors and timeouts are properly distinguished from programming errors.

### Refactored

- `apps/channels/tasks.py`: three helper functions extracted — `_find_pipeline_and_stage()`, `_build_contact()`, `_auto_create_lead()`, `_sync_to_external_crm()`. Source length unchanged but logical units are now independently testable.
- `apps/channels/tests/test_bridge.py`: coverage expanded from 3 to 13 tests covering normal message, edited message, unsupported updates (Telegram and MAX), missing pipeline, missing stage, `auto_create_lead=False`, and external CRM sync.
- `apps/channels/public_views.py`: structured `logger.info`/`logger.warning` added at every webhook entry/exit point.

### Infrastructure

- `vps-deployment/crm_prvms/docker-compose.yml`: Redis `command` rewritten from YAML block scalar (`>`) to JSON array to fix argument parsing bug that produced `requirepass "--maxmemory" "256mb"`.

## [0.2.4] — 2026-05-11

### Added (CI/CD via GitHub Actions)

End-to-end pipeline in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Single file, three jobs:

- **backend** — runs on every PR and push. Spins up Postgres 17 + Redis 7.4 as service containers, installs system deps for WeasyPrint/psycopg, then: `manage.py check`, `makemigrations --check --dry-run` (catches the latent-debt class of bug that 0.2.3 cleaned up — any future model drift fails CI), `manage.py test apps`. Python pinned to 3.13 to match the production Dockerfile.
- **frontend** — Node 24, `npm ci`, `npm run typecheck`, `npm run test` (vitest), `npm run build` with `VITE_API_URL=https://crm.prvms.ru/api` to verify the prod bundle compiles.
- **deploy** — runs only on push to `main` after both CI jobs pass. SSH-deploys to the VPS using the existing `vps-deployment/crm_prvms/deploy.sh`. Singleton concurrency group `production-deploy` so two deploys can never overlap; `cancel-in-progress: false` so a newer commit never aborts an in-flight deploy. Smoke tests `/healthz` (12 attempts × 10s = 2 min) and `/` (homepage) after deploy. GitHub environment `production` declared so an approval gate can be enabled later without code changes.

[`.github/SECRETS.md`](.github/SECRETS.md) documents the three secrets needed (`SSH_HOST`, `SSH_PRIVATE_KEY`, `SSH_PORT`), one-time server-side SSH-key setup, branch-protection rules to prevent direct push to `main`, and the optional approval gate.

### Notes
- CI uses dummy values for `SECRET_KEY` / `FIELD_ENCRYPTION_KEY` / `SALT_KEY` baked into the workflow — there are no real secrets in CI runs. Production secrets stay on the VPS in `/opt/crm_prvms/.env.prod`.
- Deploy step uses `git reset --hard ${DEPLOY_SHA}` so CI is the single source of truth for what `main` looks like on the server. Untracked `.env.prod` is preserved by `reset --hard` (it does not touch untracked files).

## [0.2.3] — 2026-05-11

### Migrations

`deploy.sh` log on production surfaced silent latent debt — two apps had model code that diverged from the last migration. Existing migrations applied fine, but `makemigrations --check` would have failed and any future `makemigrations` run would have created these implicitly. Generated, applied to local DB (`migrate_schemas --shared` and `--tenant`), verified `--check` is clean:

- `apps/distribution/migrations/0003_distribution_choices_sync.py` — sync `DistributionLog.source` choices (adds `builtin_crm`) and `DistributionRule.trigger` choices (`new_deal` canonical) with what's been in the model code since DEC-030. Choices-only, no schema change beyond the CHECK constraint refresh.
- `apps/users/migrations/0003_rolepermission_index_names.py` — rename two indexes on `RolePermission` whose autogenerated hash suffix drifted after a field-options change. Pure metadata, `ALTER INDEX RENAME`.

## [0.2.2] — 2026-05-11

### Fixed (DEC-034 addendum: production HTTPS — three remaining failure modes)

After `0.2.1` was deployed the homepage on `crm.prvms.ru` still returned 404. Debug-level Traefik logs revealed three structural issues that survived `0.2.1`:

**`/opt/crm_prvms/docker-compose.yml` was a stale copy, not a symlink.** At initial server setup the file got copied instead of `ln -sf`'d to `vps-deployment/crm_prvms/docker-compose.yml`. Every subsequent `git pull` updated the source file but `docker compose up` kept consuming the frozen copy — so the `0.2.1` healthcheck fix never reached the running container.

**`frontend-app` healthcheck removed entirely.** Fighting busybox-`wget` over `localhost` / `::1` / `127.0.0.1` / PATH inside `nginx:alpine` is a losing battle for a static-file container. Any resolution or wget-variant quirk makes the container `unhealthy` and Traefik filters its routers. nginx serving an SPA is reliable; if it dies, Docker's restart policy handles it. Traefik v2 treats containers without a healthcheck as healthy and registers their routers immediately.

**`bring_up()` now uses `--force-recreate`.** Without it, `docker compose up -d` may decide the image hash is unchanged and skip container recreation, leaving the previous compose-level config (healthcheck command, labels) in place. Force-recreate guarantees compose-level changes actually propagate.

### Added

- **`/VERSION`** — single source of truth for the project version (was implicit in `docs/VERSIONING.md` text). [`docs/VERSIONING.md`](docs/VERSIONING.md) now describes the bump-checklist and points to `/VERSION`.
- **`vps-deployment/crm_prvms/deploy.sh`**: `ensure_root_layout()` idempotently rewrites `/opt/crm_prvms/{docker-compose.yml,deploy.sh,.env.prod.example}` as symlinks to `vps-deployment/crm_prvms/*` on every run. Any pre-existing regular file is backed up to `<file>.copy_replaced_<unix-ts>.bak`. Makes the copy-vs-symlink class of bug structurally impossible.
- **`vps-deployment/scripts/start-all.sh`**: mirror `ensure_crm_root_symlinks()` in `prepare_project_env`, so first-time setup or drift gets repaired on the next `start-all.sh` run too.

### Changed

- `web` healthcheck rewritten to use `127.0.0.1` literal instead of `localhost`. Marginal — `curl` does IPv4 fallback — but removes the extra RTT and makes behavior deterministic.

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
