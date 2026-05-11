#!/usr/bin/env bash
set -Eeuo pipefail

PROJECTS=(traefik portainer rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)
ERRORS=0
WARNINGS=0
SERVER_IP=""

ok() {
  echo "✅ $*"
}

warn() {
  echo "⚠️  $*"
  WARNINGS=$((WARNINGS + 1))
}

err() {
  echo "❌ $*"
  ERRORS=$((ERRORS + 1))
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
  local project="$2"
  local domains

  if command -v rg >/dev/null 2>&1; then
    domains="$(rg -o 'Host\(`[^`]+`\)' "$compose_file" 2>/dev/null \
      | sed -E 's/Host\(`([^`]+)`\)/\1/' \
      | sort -u)"
  else
    domains="$(grep -oE 'Host\(`[^`]+`\)' "$compose_file" 2>/dev/null \
      | sed -E 's/Host\(`([^`]+)`\)/\1/' \
      | sort -u)"
  fi

  # For crm_prvms, resolve ${PUBLIC_HOSTNAME} from .env.prod
  if [ "$project" = "crm_prvms" ] && echo "$domains" | grep -q 'PUBLIC_HOSTNAME'; then
    local env_file="/opt/crm_prvms/.env.prod"
    if [ -f "$env_file" ]; then
      local hostname
      hostname="$(grep -E '^PUBLIC_HOSTNAME=' "$env_file" | tail -n 1 | cut -d '=' -f2- || true)"
      if [ -n "$hostname" ]; then
        domains="$(echo "$domains" | sed "s/\${PUBLIC_HOSTNAME}/${hostname}/g")"
      fi
    fi
  fi

  echo "$domains"
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

check_prerequisites() {
  command -v docker >/dev/null 2>&1 || {
    err "Docker is not installed."
    return
  }

  if docker ps --format '{{.Names}}' | grep -q '^traefik-traefik-1$'; then
    ok "Traefik container is running"
  else
    err "Traefik container is not running (expected: traefik-traefik-1)"
  fi

  if docker network inspect proxy >/dev/null 2>&1; then
    local driver attachable
    driver="$(docker network inspect -f '{{.Driver}}' proxy)"
    attachable="$(docker network inspect -f '{{.Attachable}}' proxy)"
    if [ "$driver" = "overlay" ] && [ "$attachable" = "true" ]; then
      ok "Docker network 'proxy' exists (overlay, attachable)"
    else
      err "Docker network 'proxy' has wrong driver/attachable (driver=${driver}, attachable=${attachable})"
    fi
  else
    err "Docker network 'proxy' does not exist"
  fi

  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk 'NR > 1 {print $4}' | grep -Eq '(:80$|:443$)'; then
      ok "Host listens on 80/443"
    else
      err "Host does not listen on 80/443"
    fi
  else
    warn "Command 'ss' not found. Port check skipped."
  fi
}

check_traefik_routes() {
  echo
  echo "Traefik routers:"
  local routers_json
  routers_json="$(curl -s http://localhost:8080/api/http/routers 2>/dev/null || true)"
  if [ -z "$routers_json" ] || [ "$routers_json" = "null" ]; then
    err "Cannot reach Traefik API at http://localhost:8080/api/http/routers"
    return
  fi

  local project compose_file rname
  for project in "${PROJECTS[@]}"; do
    compose_file="/opt/${project}/docker-compose.yml"
    [ -f "$compose_file" ] || continue
    rname=""
    case "$project" in
      crm_prvms)  rname="crm-spa" ;;
      rent_django) rname="rent_django" ;;
      kapitan_api) rname="kapitan_api" ;;
      kupi_slona) rname="kupi_slona" ;;
      bookstack)  rname="bookstack" ;;
      druzhina)   rname="druzhina" ;;
      vybra)      rname="vybra" ;;
      *)          continue ;;
    esac
    if [ -n "$rname" ] && echo "$routers_json" | grep -q "\"${rname}\""; then
      ok "Router '${rname}' (${project}) found"
    else
      err "Router '${rname}' (${project}) NOT found in Traefik"
    fi
  done
}

check_dns() {
  local host_ip
  host_ip="$(get_server_ip)"
  if [ -z "$host_ip" ]; then
    err "Cannot detect server IP for DNS checks."
    return
  fi
  echo "Server IP: ${host_ip}"

  local checked=0
  local project compose_file domain resolved
  for project in "${PROJECTS[@]}"; do
    compose_file="/opt/${project}/docker-compose.yml"
    [ -f "$compose_file" ] || continue
    while IFS= read -r domain; do
      [ -n "$domain" ] || continue
      if [[ "$domain" == *'${'* ]]; then
        warn "Skipped templated domain in ${project}: ${domain}"
        continue
      fi
      checked=$((checked + 1))
      resolved="$(resolve_domain_ip "$domain")"
      if [ -z "$resolved" ]; then
        err "DNS unresolved: ${domain}"
      elif [ "$resolved" = "$host_ip" ]; then
        ok "DNS ${domain} -> ${resolved}"
      else
        err "DNS mismatch ${domain} -> ${resolved} (expected ${host_ip})"
      fi
    done < <(extract_domains_from_compose "$compose_file" "$project")
  done

  if [ "$checked" -eq 0 ]; then
    warn "No concrete domains found in compose labels."
  fi
}

check_traefik_logs() {
  if ! docker ps --format '{{.Names}}' | grep -q '^traefik-traefik-1$'; then
    return
  fi

  echo
  echo "Traefik ACME/errors (last 200 lines):"
  local log_excerpt
  log_excerpt="$(docker logs traefik-traefik-1 --tail=200 2>&1 | grep -Ei 'acme|certificate|router|error' || true)"
  if [ -n "$log_excerpt" ]; then
    echo "$log_excerpt"
  else
    warn "No ACME/router/error lines found in last 200 Traefik log lines."
  fi
}

main() {
  echo "🔎 HTTPS diagnostics"
  echo "==================="
  check_prerequisites
  echo
  check_dns
  check_traefik_routes
  check_traefik_logs
  echo
  echo "Summary: errors=${ERRORS}, warnings=${WARNINGS}"

  if [ "$ERRORS" -gt 0 ]; then
    exit 1
  fi
}

main "$@"
