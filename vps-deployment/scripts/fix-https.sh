#!/usr/bin/env bash
# Diagnose and repair Traefik routing / Let's Encrypt certificate issues.
#
# Idempotent. Run after start-all.sh / init-server.sh.
# Usage: sudo /opt/scripts/fix-https.sh
set -Eeuo pipefail

PROJECTS=(rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)
ACME_FILE="/opt/traefik/letsencrypt/acme.json"
PROXY_NET="proxy"
TRAEFIK_CID=""

ISSUES=()
FIXED=()
RECREATE=()  # projects whose env was patched and need recreate

log()   { echo "[$(date +'%H:%M:%S')] $*"; }
warn()  { echo "⚠️  $*"; }
issue() { ISSUES+=("$1"); echo "❌ $1"; }
fix()   { FIXED+=("$1"); echo "🔧 $1"; }

require_root() {
  [ "$EUID" -eq 0 ] || { echo "Run as root: sudo $0"; exit 1; }
}

run_compose() {
  local project="$1"; shift
  local dir="/opt/${project}"
  if [ "$project" = "crm_prvms" ] && [ -f "${dir}/.env.prod" ]; then
    (cd "$dir" && docker compose --env-file "${dir}/.env.prod" "$@")
  else
    (cd "$dir" && docker compose "$@")
  fi
}

container_for() {
  # Find the web/app container of a project (the one carrying traefik labels).
  local project="$1"
  case "$project" in
    bookstack) docker ps -aqf "name=^bookstack-bookstack" | head -1 ;;
    druzhina)  docker ps -aqf "name=^druzhina-app"        | head -1 ;;
    *)         docker ps -aqf "name=^${project}-web"      | head -1 ;;
  esac
}

extract_router_host() {
  # Read Host(`...`) from the container labels (already interpolated by compose).
  local cid="$1"
  docker inspect "$cid" --format '{{range $k, $v := .Config.Labels}}{{if eq $k "traefik.http.routers.'"$2"'.rule"}}{{$v}}{{end}}{{end}}' 2>/dev/null \
    | grep -oE 'Host\(`[^`]+`\)' 2>/dev/null \
    | sed -E 's/Host\(`([^`]+)`\)/\1/' \
    | head -n 1 || true
}

env_get() {
  # Read a single var from a key=value file, last occurrence wins.
  # Always returns 0 (under set -e a missing key would otherwise kill the script).
  local file="$1" key="$2"
  [ -f "$file" ] || return 0
  grep -E "^[[:space:]]*${key}=" "$file" 2>/dev/null | tail -n 1 | sed -E "s/^[[:space:]]*${key}=//" || true
  return 0
}

env_has_value() {
  # True if key exists AND value is non-empty.
  local file="$1" key="$2" v
  v="$(env_get "$file" "$key")"
  [ -n "${v}" ]
}

env_append() {
  local file="$1" line="$2"
  if [ ! -s "$file" ] || [ "$(tail -c1 "$file" 2>/dev/null)" != "" ]; then
    echo "" >> "$file"
  fi
  echo "$line" >> "$file"
}

repair_crm_prvms_env() {
  local f="/opt/crm_prvms/.env.prod"
  [ -f "$f" ] || return 0
  if env_has_value "$f" "DATABASE_URL"; then
    return 0
  fi

  local user pass name host port
  user="$(env_get "$f" "DB_USER")"
  pass="$(env_get "$f" "DB_PASSWORD")"
  name="$(env_get "$f" "DB_NAME")"
  host="$(env_get "$f" "DB_HOST")"; host="${host:-db}"
  port="$(env_get "$f" "DB_PORT")"; port="${port:-5432}"
  user="${user:-platform}"
  name="${name:-platform_db}"

  if [ -z "$pass" ]; then
    issue "crm_prvms: DB_PASSWORD missing in .env.prod (cannot build DATABASE_URL)"
    return 0
  fi

  env_append "$f" "DATABASE_URL=postgresql://${user}:${pass}@${host}:${port}/${name}"
  fix "crm_prvms: appended DATABASE_URL to .env.prod"
  RECREATE+=("crm_prvms")
}

repair_vybra_env() {
  local f="/opt/vybra/.env"
  [ -f "$f" ] || return 0

  local changed=0
  if ! env_has_value "$f" "DB_HOST"; then
    env_append "$f" "DB_HOST=db"
    changed=1
    fix "vybra: appended DB_HOST=db to .env"
  fi
  if ! env_has_value "$f" "DB_PORT"; then
    env_append "$f" "DB_PORT=5432"
    changed=1
    fix "vybra: appended DB_PORT=5432 to .env"
  fi
  if ! env_has_value "$f" "REDIS_URL"; then
    env_append "$f" "REDIS_URL=redis://redis:6379/0"
    changed=1
    fix "vybra: appended REDIS_URL=redis://redis:6379/0 to .env"
  fi
  [ "$changed" -eq 1 ] && RECREATE+=("vybra")
}

repair_bookstack_env() {
  local f="/opt/bookstack/.env"
  [ -f "$f" ] || return 0

  if env_has_value "$f" "BOOKSTACK_APP_KEY"; then
    return 0
  fi

  log "Generating BOOKSTACK_APP_KEY..."
  local key
  key="$(docker run --rm --entrypoint /bin/bash lscr.io/linuxserver/bookstack:latest appkey 2>/dev/null \
    | grep -Eo 'base64:[A-Za-z0-9+/=]+' | head -n 1 || true)"

  if [ -z "$key" ]; then
    issue "bookstack: failed to generate APP_KEY (image pull/run problem)"
    return 0
  fi

  env_append "$f" "BOOKSTACK_APP_KEY=${key}"
  fix "bookstack: appended BOOKSTACK_APP_KEY to .env"
  RECREATE+=("bookstack")
}

repair_envs() {
  log "Patching env files for projects with known requirements..."
  repair_crm_prvms_env
  repair_vybra_env
  repair_bookstack_env
}

recreate_patched_projects() {
  [ "${#RECREATE[@]}" -eq 0 ] && return 0
  # de-duplicate
  local uniq=()
  local p seen
  for p in "${RECREATE[@]}"; do
    seen=0
    for u in "${uniq[@]:-}"; do [ "$u" = "$p" ] && seen=1 && break; done
    [ "$seen" -eq 0 ] && uniq+=("$p")
  done

  for p in "${uniq[@]}"; do
    log "Recreating ${p} with patched env..."
    run_compose "$p" up -d --force-recreate >/dev/null 2>&1 || warn "${p}: recreate returned non-zero"
  done
}

router_name_for() {
  local project="$1"
  case "$project" in
    crm_prvms)  echo "crm_prvms" ;;
    rent_django) echo "rent_django" ;;
    kapitan_api) echo "kapitan_api" ;;
    kupi_slona) echo "kupi_slona" ;;
    bookstack)  echo "bookstack" ;;
    druzhina)   echo "druzhina" ;;
    vybra)      echo "vybra" ;;
  esac
}

ensure_traefik() {
  TRAEFIK_CID="$(docker ps -qf 'name=^traefik-traefik' | head -1)"
  if [ -z "$TRAEFIK_CID" ]; then
    issue "Traefik container is not running"
    log "Bringing Traefik up..."
    (cd /opt/traefik && docker compose up -d) || true
    sleep 5
    TRAEFIK_CID="$(docker ps -qf 'name=^traefik-traefik' | head -1)"
    [ -n "$TRAEFIK_CID" ] && fix "Traefik started"
  fi
}

ensure_proxy_network_health() {
  if ! docker network inspect "$PROXY_NET" >/dev/null 2>&1; then
    issue "Network '${PROXY_NET}' does not exist"
    log "Creating overlay '${PROXY_NET}'..."
    docker network create -d overlay --attachable "$PROXY_NET" >/dev/null
    fix "Created network ${PROXY_NET}"
  fi

  if [ -n "$TRAEFIK_CID" ]; then
    local nets
    nets="$(docker inspect "$TRAEFIK_CID" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}')"
    if ! grep -qw "$PROXY_NET" <<<"$nets"; then
      issue "Traefik is not connected to ${PROXY_NET} (in: ${nets})"
      docker network connect "$PROXY_NET" "$TRAEFIK_CID" 2>/dev/null && \
        fix "Connected Traefik to ${PROXY_NET}" || \
        warn "Could not auto-connect Traefik. Recreating..."
      (cd /opt/traefik && docker compose up -d --force-recreate) >/dev/null 2>&1 || true
    fi
  fi
}

scan_project() {
  local project="$1"
  echo
  echo "── ${project} ──────────────────────────────"

  local dir="/opt/${project}"
  if [ ! -d "$dir" ] || [ ! -f "${dir}/docker-compose.yml" ]; then
    issue "${project}: missing /opt/${project}/docker-compose.yml"
    return
  fi

  local cid
  cid="$(container_for "$project")"
  if [ -z "$cid" ]; then
    issue "${project}: web container not found"
    log "Running: docker compose up -d for ${project}..."
    run_compose "$project" up -d 2>&1 | tail -5 || true
    cid="$(container_for "$project")"
    [ -n "$cid" ] && fix "${project}: started"
    [ -z "$cid" ] && return
  fi

  # State / health
  local state health restarts
  state="$(docker inspect "$cid" --format '{{.State.Status}}' 2>/dev/null)"
  health="$(docker inspect "$cid" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' 2>/dev/null)"
  restarts="$(docker inspect "$cid" --format '{{.RestartCount}}' 2>/dev/null)"
  echo "  state=${state}, health=${health}, restarts=${restarts}"

  if [ "$state" != "running" ]; then
    issue "${project}: container is '${state}'. Last logs:"
    docker logs --tail=20 "$cid" 2>&1 | sed 's/^/    /'
    return
  fi

  if [ "$health" = "unhealthy" ]; then
    issue "${project}: container is 'unhealthy'. Last logs:"
    docker logs --tail=15 "$cid" 2>&1 | sed 's/^/    /'
  fi

  # Labels — domain interpolated?
  local rname host
  rname="$(router_name_for "$project")"
  host="$(extract_router_host "$cid" "$rname")"
  if [ -z "$host" ]; then
    issue "${project}: traefik router label missing or unparseable"
  elif [[ "$host" == *'${'* ]]; then
    issue "${project}: label has uninterpolated variable: ${host}. Fill .env and recreate."
  else
    echo "  domain=${host}"
  fi

  # In proxy network?
  local nets
  nets="$(docker inspect "$cid" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}')"
  if ! grep -qw "$PROXY_NET" <<<"$nets"; then
    issue "${project}: not in '${PROXY_NET}' network (in: ${nets})"
    docker network connect "$PROXY_NET" "$cid" 2>/dev/null && \
      fix "${project}: connected to ${PROXY_NET}" || \
      warn "${project}: connect failed, will recreate compose"
    run_compose "$project" up -d --force-recreate >/dev/null 2>&1 || true
  fi

  # Skip if no host — cert never possible
  [ -z "$host" ] || [[ "$host" == *'${'* ]] && return 0

  # Already in acme storage?
  if grep -q "\"main\": \"${host}\"" "$ACME_FILE" 2>/dev/null; then
    echo "  cert: ✅ present in acme.json"
  else
    echo "  cert: ⏳ not yet issued"
  fi
}

print_acme_state() {
  echo
  echo "── Certificates in acme.json ───────────────"
  if [ ! -s "$ACME_FILE" ]; then
    warn "acme.json is empty or missing"
    return
  fi
  python3 - "$ACME_FILE" <<'PY' || true
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    certs = data.get('le', {}).get('Certificates') or []
    print(f"  count: {len(certs)}")
    for c in certs:
        print(f"   - {c['domain'].get('main', '?')}")
except Exception as e:
    print(f"  could not parse: {e}")
PY
}

print_acme_errors() {
  echo
  echo "── Recent ACME errors (excluding rate-limit) ──"
  docker logs "$TRAEFIK_CID" 2>&1 \
    | grep -iE "unable to obtain|acme.*error" \
    | grep -vi "rateLimited\|too many" \
    | tail -10 \
    | sed 's/^/  /' || true

  echo
  echo "── Rate-limit hits ─────────────────────────"
  docker logs "$TRAEFIK_CID" 2>&1 \
    | grep -i "rateLimited\|too many" \
    | tail -5 \
    | sed 's/^/  /' || true
}

reload_traefik_routes() {
  # Touching compose triggers Traefik provider re-scan; safer than full restart.
  log "Asking Traefik to re-scan routers..."
  (cd /opt/traefik && docker compose up -d) >/dev/null 2>&1 || true
}

main() {
  require_root
  echo "🩺 HTTPS / Traefik diagnostic + repair (v2 — env-repair)"
  echo "========================================================"

  ensure_traefik
  ensure_proxy_network_health
  repair_envs
  recreate_patched_projects

  if [ "${#RECREATE[@]}" -gt 0 ]; then
    log "Waiting 15s for recreated containers to settle..."
    sleep 15
  fi

  for p in "${PROJECTS[@]}"; do
    scan_project "$p"
  done

  reload_traefik_routes

  print_acme_state
  print_acme_errors

  echo
  echo "════════════════ SUMMARY ════════════════"
  echo "Auto-fixed: ${#FIXED[@]}"
  for f in "${FIXED[@]:-}"; do [ -n "$f" ] && echo "  🔧 $f"; done
  echo
  echo "Manual issues: ${#ISSUES[@]}"
  for i in "${ISSUES[@]:-}"; do [ -n "$i" ] && echo "  ❌ $i"; done
  echo "═════════════════════════════════════════"

  if [ ${#ISSUES[@]} -eq 0 ] && [ ${#FIXED[@]} -gt 0 ]; then
    echo
    echo "Wait ~60 seconds for Let's Encrypt to issue new certs, then re-run:"
    echo "  sudo $0"
  fi
}

main "$@"
