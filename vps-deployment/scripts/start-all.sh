#!/usr/bin/env bash
set -Eeuo pipefail

PROJECTS=(traefik portainer rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)
BUILD_PROJECTS=(rent_django crm_prvms druzhina kapitan_api kupi_slona vybra)
STARTED=()
SKIPPED=()
FAILED=()
SERVER_IP=""

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

warn() {
  echo "⚠️  $*"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker is not installed. Run /opt/scripts/init-server.sh first."
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "❌ docker compose plugin is not available. Run /opt/scripts/init-server.sh first."
    exit 1
  fi
}

ensure_swarm() {
  local state
  state="$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo "unknown")"
  case "$state" in
    active)
      log "Docker Swarm: active"
      ;;
    inactive)
      log "Docker Swarm is inactive. Initializing single-node swarm..."
      docker swarm init >/dev/null
      ;;
    *)
      echo "❌ Unexpected Docker Swarm state: $state"
      echo "Run /opt/scripts/init-server.sh to repair the server setup."
      exit 1
      ;;
  esac
}

cleanup_stale_proxy_networks() {
  # Drop "<project>_proxy" networks compose may have created when the external
  # "proxy" was missing at first up. Otherwise Traefik and services land in
  # separate networks and HTTPS routing silently breaks.
  local stale
  stale="$(docker network ls --format '{{.Name}}' | grep -E '_proxy$' || true)"
  if [ -z "$stale" ]; then
    return
  fi

  log "Stale compose-created *_proxy networks detected. Stopping projects to clean up..."
  # Bring all projects down so compose recreates containers cleanly on next up.
  local proj
  for proj in "${PROJECTS[@]}"; do
    if [ -f "/opt/${proj}/docker-compose.yml" ]; then
      run_compose "$proj" down --remove-orphans >/dev/null 2>&1 || true
    fi
  done

  log "Removing stale *_proxy networks..."
  local net cid
  while IFS= read -r net; do
    [ -n "$net" ] || continue
    [ "$net" = "proxy" ] && continue
    log "  Removing network: ${net}"
    while IFS= read -r cid; do
      [ -n "$cid" ] || continue
      docker network disconnect -f "$net" "$cid" >/dev/null 2>&1 || true
    done < <(docker network inspect -f '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' "$net" 2>/dev/null)
    docker network rm "$net" >/dev/null 2>&1 || warn "Could not remove network ${net}"
  done <<<"$stale"
}

ensure_proxy_network() {
  cleanup_stale_proxy_networks

  if docker network inspect proxy >/dev/null 2>&1; then
    local driver attachable
    driver="$(docker network inspect -f '{{.Driver}}' proxy)"
    attachable="$(docker network inspect -f '{{.Attachable}}' proxy)"
    if [ "$driver" = "overlay" ] && [ "$attachable" = "true" ]; then
      log "Network proxy already exists (overlay, attachable)"
      return
    fi
    warn "Network 'proxy' has wrong driver/attachable (driver=${driver}, attachable=${attachable}). Recreating."
    local cid
    while IFS= read -r cid; do
      [ -n "$cid" ] || continue
      docker network disconnect -f proxy "$cid" >/dev/null 2>&1 || true
    done < <(docker network inspect -f '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' proxy 2>/dev/null)
    docker network rm proxy >/dev/null 2>&1 || {
      echo "❌ Cannot remove existing 'proxy' network. Stop all services and retry."
      exit 1
    }
  fi

  log "Creating overlay network proxy..."
  docker network create -d overlay --attachable proxy >/dev/null
}

ensure_traefik_dirs() {
  mkdir -p /opt/traefik/letsencrypt /opt/traefik/logs
  touch /opt/traefik/letsencrypt/acme.json
  chmod 600 /opt/traefik/letsencrypt/acme.json
}

get_server_ip() {
  if [ -n "$SERVER_IP" ]; then
    echo "$SERVER_IP"
    return
  fi

  SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [ -z "$SERVER_IP" ] && command -v ip >/dev/null 2>&1; then
    SERVER_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '/src/ {for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
  fi
  echo "$SERVER_IP"
}

extract_domains_from_compose() {
  local compose_file="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -o 'Host\(`[^`]+`\)' "$compose_file" 2>/dev/null \
      | sed -E 's/Host\(`([^`]+)`\)/\1/' \
      | sort -u
  else
    grep -oE 'Host\(`[^`]+`\)' "$compose_file" 2>/dev/null \
      | sed -E 's/Host\(`([^`]+)`\)/\1/' \
      | sort -u
  fi
}

resolve_domain_ip() {
  local domain="$1"
  local resolved_ip=""

  if command -v getent >/dev/null 2>&1; then
    resolved_ip="$(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1; exit}')"
  fi
  if [ -z "$resolved_ip" ] && command -v dig >/dev/null 2>&1; then
    resolved_ip="$(dig +short A "$domain" 2>/dev/null | awk 'NF {print; exit}')"
  fi
  echo "$resolved_ip"
}

check_dns_preflight() {
  local host_ip
  host_ip="$(get_server_ip)"
  if [ -z "$host_ip" ]; then
    warn "Cannot detect server IP, skipping DNS preflight."
    return
  fi

  log "DNS preflight (expected VPS IPv4: ${host_ip})..."
  local checked=0 unresolved=0 mismatched=0
  local compose_file domain resolved

  for project in "${PROJECTS[@]}"; do
    compose_file="/opt/${project}/docker-compose.yml"
    [ -f "$compose_file" ] || continue

    while IFS= read -r domain; do
      [ -n "$domain" ] || continue
      # Skip unresolved template expressions like ${BOOKSTACK_DOMAIN:-...}
      if [[ "$domain" == *'${'* ]]; then
        continue
      fi
      checked=$((checked + 1))
      resolved="$(resolve_domain_ip "$domain")"
      if [ -z "$resolved" ]; then
        warn "DNS unresolved: ${domain}"
        unresolved=$((unresolved + 1))
      elif [ "$resolved" != "$host_ip" ]; then
        warn "DNS mismatch: ${domain} -> ${resolved} (expected ${host_ip})"
        mismatched=$((mismatched + 1))
      fi
    done < <(extract_domains_from_compose "$compose_file")
  done

  if [ "$checked" -eq 0 ]; then
    warn "No concrete domains found in compose labels for DNS preflight."
    return
  fi

  if [ "$unresolved" -eq 0 ] && [ "$mismatched" -eq 0 ]; then
    log "DNS preflight passed for ${checked} domain(s)."
  else
    warn "DNS preflight warnings: unresolved=${unresolved}, mismatched=${mismatched}."
    warn "HTTPS certificates will not issue until DNS A records point to ${host_ip}."
  fi
}

sanitize_compose_file() {
  local compose_file="$1"
  local first_non_empty
  first_non_empty="$(awk 'NF{print; exit}' "$compose_file" 2>/dev/null || true)"
  if [[ "$first_non_empty" =~ ^[[:space:]]*version:[[:space:]]* ]]; then
    local tmp_file
    tmp_file="${compose_file}.tmp.$$"
    awk 'BEGIN{removed=0} { if (!removed && $0 ~ /^[[:space:]]*version:[[:space:]]*/) {removed=1; next} print }' "$compose_file" >"$tmp_file"
    mv "$tmp_file" "$compose_file"
    log "Removed deprecated 'version' from ${compose_file}"
  fi
}

run_compose() {
  local project="$1"
  shift
  local project_dir="/opt/${project}"

  # crm_prvms keeps main runtime vars in .env.prod
  if [ "$project" = "crm_prvms" ] && [ -f "${project_dir}/.env.prod" ]; then
    (cd "$project_dir" && docker compose --env-file "${project_dir}/.env.prod" "$@")
  else
    (cd "$project_dir" && docker compose "$@")
  fi
}

check_build_prereqs() {
  local project="$1"
  local project_dir="/opt/${project}"

  case "$project" in
    rent_django|crm_prvms|kapitan_api|kupi_slona|vybra)
      if [ ! -f "${project_dir}/Dockerfile" ]; then
        echo "❌ ${project}: missing ${project_dir}/Dockerfile"
        echo "   This project requires full source code in ${project_dir}, not only deployment files."
        return 1
      fi
      ;;
    druzhina)
      if [ ! -f "${project_dir}/Dockerfile" ]; then
        echo "❌ druzhina: missing ${project_dir}/Dockerfile"
        return 1
      fi
      if [ ! -f "${project_dir}/deploy/Dockerfile.garage" ]; then
        echo "❌ druzhina: missing ${project_dir}/deploy/Dockerfile.garage"
        return 1
      fi
      if [ ! -f "${project_dir}/deploy/garage.toml" ]; then
        echo "❌ druzhina: missing ${project_dir}/deploy/garage.toml"
        return 1
      fi
      ;;
  esac

  return 0
}

prepare_project_env() {
  local project="$1"
  local project_dir="/opt/${project}"

  if [ ! -f "${project_dir}/.env" ] && [ -f "${project_dir}/.env.example" ]; then
    cp "${project_dir}/.env.example" "${project_dir}/.env"
    log "Created ${project_dir}/.env from .env.example"
  fi

  if [ "$project" = "crm_prvms" ]; then
    if [ ! -f "${project_dir}/.env.prod" ]; then
      if [ -f "${project_dir}/.env" ]; then
        cp "${project_dir}/.env" "${project_dir}/.env.prod"
        log "Created ${project_dir}/.env.prod from existing .env"
      elif [ -f "${project_dir}/.env.prod.example" ]; then
        cp "${project_dir}/.env.prod.example" "${project_dir}/.env.prod"
        log "Created ${project_dir}/.env.prod from .env.prod.example"
      fi
    fi
    if [ ! -f "${project_dir}/.env" ] && [ -f "${project_dir}/.env.prod" ]; then
      cp "${project_dir}/.env.prod" "${project_dir}/.env"
      log "Created ${project_dir}/.env from .env.prod for compose interpolation"
    fi
  fi
}

project_needs_build() {
  local project="$1"
  local item
  for item in "${BUILD_PROJECTS[@]}"; do
    if [ "$item" = "$project" ]; then
      return 0
    fi
  done
  return 1
}

show_failure_diagnostics() {
  local project="$1"
  local had_oom=0
  echo "🔎 Diagnostics for ${project}:"

  run_compose "$project" ps --all || true
  echo

  local ids
  ids="$(run_compose "$project" ps -q 2>/dev/null || true)"
  if [ -n "$ids" ]; then
    local cid
    for cid in $ids; do
      local cname state health exit_code
      local oom_killed
      cname="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's#^/##')"
      state="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo 'unknown')"
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$cid" 2>/dev/null || echo 'n/a')"
      exit_code="$(docker inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || echo 'n/a')"
      oom_killed="$(docker inspect -f '{{.State.OOMKilled}}' "$cid" 2>/dev/null || echo 'n/a')"
      echo "  - ${cname}: state=${state}, health=${health}, exit_code=${exit_code}, oom_killed=${oom_killed}"
      if [ "$oom_killed" = "true" ] || [ "$exit_code" = "137" ]; then
        had_oom=1
      fi
      if [ "$health" = "unhealthy" ]; then
        docker inspect -f '{{range .State.Health.Log}}{{println .Start " exit=" .ExitCode " " .Output}}{{end}}' "$cid" 2>/dev/null | tail -n 8 || true
      fi
    done
  fi

  echo
  run_compose "$project" logs --tail=80 || true
  if [ "$had_oom" -eq 1 ]; then
    echo
    echo "Possible OOM detected for ${project}. Host memory snapshot:"
    free -h || true
    echo
    echo "Recent kernel OOM lines:"
    dmesg -T 2>/dev/null | grep -Ei "out of memory|killed process" | tail -n 20 || true
  fi
  if [ "$project" = "bookstack" ]; then
    echo
    echo "Hint for fresh Bookstack setup:"
    echo "  If this is a first clean install, reset DB volume and start again:"
    echo "  docker compose -f /opt/bookstack/docker-compose.yml down -v"
    echo "  docker compose -f /opt/bookstack/docker-compose.yml up -d"
  fi
  echo "---- End diagnostics for ${project} ----"
}

start_project() {
  local project="$1"
  local project_dir="/opt/${project}"
  local compose_file="${project_dir}/docker-compose.yml"

  if [ ! -d "$project_dir" ]; then
    echo "⚠️  Skipping ${project}: directory ${project_dir} not found"
    SKIPPED+=("${project} (missing dir)")
    return 0
  fi

  if [ ! -f "$compose_file" ]; then
    echo "⚠️  Skipping ${project}: ${compose_file} not found"
    SKIPPED+=("${project} (missing compose)")
    return 0
  fi

  prepare_project_env "$project"
  sanitize_compose_file "$compose_file"
  if project_needs_build "$project"; then
    if ! check_build_prereqs "$project"; then
      FAILED+=("$project")
      return 0
    fi
  fi
  log "📦 Starting ${project}..."
  if project_needs_build "$project"; then
    log "🔨 Building images for ${project}..."
    if run_compose "$project" build; then
      if run_compose "$project" up -d --no-build; then
        echo "✅ ${project} started"
        STARTED+=("$project")
        return 0
      fi
    fi
  elif run_compose "$project" up -d; then
    echo "✅ ${project} started"
    STARTED+=("$project")
    return 0
  fi

  echo "❌ ${project} failed to start"
  FAILED+=("$project")
  show_failure_diagnostics "$project"
}

print_summary() {
  echo
  echo "========== Summary =========="
  echo "Started: ${#STARTED[@]}"
  for item in "${STARTED[@]:-}"; do
    [ -n "$item" ] && echo "  ✅ $item"
  done
  echo "Skipped: ${#SKIPPED[@]}"
  for item in "${SKIPPED[@]:-}"; do
    [ -n "$item" ] && echo "  ⚠️  $item"
  done
  echo "Failed: ${#FAILED[@]}"
  for item in "${FAILED[@]:-}"; do
    [ -n "$item" ] && echo "  ❌ $item"
  done
  echo "============================="
  echo
}

main() {
  log "🚀 Starting all services..."
  require_docker
  ensure_swarm
  ensure_proxy_network
  ensure_traefik_dirs
  check_dns_preflight

  for project in "${PROJECTS[@]}"; do
    start_project "$project"
  done

  print_summary

  if [ "${#FAILED[@]}" -gt 0 ]; then
    exit 1
  fi

  local ip
  ip="$(hostname -I | awk '{print $1}')"
  echo "Access points:"
  echo "  Traefik: http://${ip}:8080"
  echo "  Portainer: https://${ip}:9443"
}

main "$@"
