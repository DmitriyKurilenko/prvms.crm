#!/usr/bin/env bash
set -Eeuo pipefail

# Initial full-server bootstrap for the vps-deployment bundle.
# Idempotent: safe to run multiple times.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SOURCE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SOURCE_DIR="${DEFAULT_SOURCE_DIR}"
ADVERTISE_ADDR=""
SKIP_SYSTEM_UPDATE=0
SKIP_DOCKER_INSTALL=0
SKIP_START=0
SKIP_SYSTEMD=0

PROJECTS=(traefik portainer rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)
CORE_DIRS=(traefik portainer rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack scripts systemd backups)

WARNINGS=()
COMPOSE_FAILS=()

usage() {
  cat <<'EOF'
Usage:
  /opt/scripts/init-server.sh [options]

Options:
  --source-dir PATH         Source directory with vps-deployment bundle.
                            Default: parent of this script.
  --advertise-addr IP       Pass explicit IP to `docker swarm init --advertise-addr`.
  --skip-system-update      Skip apt update/upgrade step.
  --skip-docker-install     Skip Docker/Compose installation checks.
  --skip-start              Prepare server, but do not start services.
  --skip-systemd            Do not install/enable systemd units.
  -h, --help                Show this help.

Examples:
  /opt/scripts/init-server.sh
  /opt/scripts/init-server.sh --advertise-addr 203.0.113.10
  /opt/scripts/init-server.sh --skip-start
EOF
}

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

warn() {
  echo "⚠️  $*" >&2
  WARNINGS+=("$*")
}

die() {
  echo "❌ $*" >&2
  exit 1
}

require_root() {
  if [ "${EUID}" -ne 0 ]; then
    die "Run this script as root (or via sudo)."
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source-dir)
        [ "$#" -ge 2 ] || die "--source-dir requires a value"
        SOURCE_DIR="$2"
        shift 2
        ;;
      --advertise-addr)
        [ "$#" -ge 2 ] || die "--advertise-addr requires a value"
        ADVERTISE_ADDR="$2"
        shift 2
        ;;
      --skip-system-update)
        SKIP_SYSTEM_UPDATE=1
        shift
        ;;
      --skip-docker-install)
        SKIP_DOCKER_INSTALL=1
        shift
        ;;
      --skip-start)
        SKIP_START=1
        shift
        ;;
      --skip-systemd)
        SKIP_SYSTEMD=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done
}

check_source_bundle() {
  [ -d "$SOURCE_DIR" ] || die "Source directory not found: $SOURCE_DIR"
  [ -d "${SOURCE_DIR}/scripts" ] || die "scripts/ not found in source directory: $SOURCE_DIR"
  [ -f "${SOURCE_DIR}/traefik/docker-compose.yml" ] || die "traefik/docker-compose.yml not found in source directory: $SOURCE_DIR"
}

apt_update_upgrade() {
  if [ "$SKIP_SYSTEM_UPDATE" -eq 1 ]; then
    log "Skipping apt update/upgrade by option"
    return
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    warn "apt-get not found. Skipping OS package update."
    return
  fi
  log "Updating OS packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get upgrade -y
}

install_system_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    warn "apt-get not found. Skipping package installation."
    return
  fi
  log "Installing base packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y ca-certificates curl gnupg lsb-release git rsync
}

install_docker_stack() {
  if [ "$SKIP_DOCKER_INSTALL" -eq 1 ]; then
    log "Skipping Docker installation checks by option"
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker Engine..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
  else
    log "Docker already installed"
  fi

  if command -v apt-get >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
    log "Installing docker compose plugin..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y docker-compose-plugin
  fi

  systemctl enable --now docker

  if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
    usermod -aG docker "${SUDO_USER}" || true
  fi

  command -v docker >/dev/null 2>&1 || die "Docker installation failed"
  docker compose version >/dev/null 2>&1 || die "docker compose plugin is unavailable"
}

ensure_opt_layout() {
  log "Creating /opt directory layout..."
  for dir in "${CORE_DIRS[@]}"; do
    mkdir -p "/opt/${dir}"
  done
}

copy_file_if_present() {
  local src="$1"
  local dst="$2"
  local mode="${3:-0644}"
  if [ ! -f "$src" ]; then
    return
  fi
  mkdir -p "$(dirname "$dst")"
  if [ "$(readlink -f "$src")" = "$(readlink -f "$dst" 2>/dev/null || true)" ]; then
    return
  fi
  install -m "$mode" "$src" "$dst"
}

run_compose() {
  local project="$1"
  shift
  local project_dir="/opt/${project}"

  if [ "$project" = "crm_prvms" ] && [ -f "${project_dir}/.env.prod" ]; then
    (cd "$project_dir" && docker compose --env-file "${project_dir}/.env.prod" "$@")
  else
    (cd "$project_dir" && docker compose "$@")
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

sync_bundle_to_opt() {
  log "Syncing deployment bundle files to /opt..."

  for project in "${PROJECTS[@]}"; do
    copy_file_if_present "${SOURCE_DIR}/${project}/docker-compose.yml" "/opt/${project}/docker-compose.yml"
    copy_file_if_present "${SOURCE_DIR}/${project}/.env.example" "/opt/${project}/.env.example"
    copy_file_if_present "${SOURCE_DIR}/${project}/.env.prod.example" "/opt/${project}/.env.prod.example"
    copy_file_if_present "${SOURCE_DIR}/${project}/README.md" "/opt/${project}/README.md"
  done

  for script in "${SOURCE_DIR}"/scripts/*.sh; do
    [ -f "$script" ] || continue
    copy_file_if_present "$script" "/opt/scripts/$(basename "$script")" "0755"
  done

  for unit_file in "${SOURCE_DIR}"/systemd/*; do
    [ -f "$unit_file" ] || continue
    copy_file_if_present "$unit_file" "/opt/systemd/$(basename "$unit_file")" "0644"
  done
}

prepare_traefik_runtime() {
  log "Preparing Traefik runtime directories..."
  mkdir -p /opt/traefik/letsencrypt /opt/traefik/logs
  touch /opt/traefik/letsencrypt/acme.json
  chmod 600 /opt/traefik/letsencrypt/acme.json
}

ensure_swarm() {
  local state
  state="$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo "unknown")"
  case "$state" in
    active)
      log "Docker Swarm already active"
      ;;
    inactive)
      log "Initializing Docker Swarm..."
      if [ -n "$ADVERTISE_ADDR" ]; then
        docker swarm init --advertise-addr "$ADVERTISE_ADDR"
      else
        docker swarm init
      fi
      ;;
    *)
      die "Unexpected Docker Swarm state: ${state}. Resolve manually and rerun."
      ;;
  esac
}

cleanup_stale_proxy_networks() {
  # Compose creates "<project>_proxy" networks when the external "proxy" did
  # not exist at the moment of `docker compose up`. They split Traefik and
  # services into different networks, so HTTPS routing breaks silently.
  local stale
  stale="$(docker network ls --format '{{.Name}}' | grep -E '_proxy$' || true)"
  if [ -z "$stale" ]; then
    return
  fi

  log "Stale compose-created *_proxy networks detected. Stopping projects to clean up..."
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
    if [ "$driver" != "overlay" ] || [ "$attachable" != "true" ]; then
      warn "Network 'proxy' has wrong driver/attachable (driver=${driver}, attachable=${attachable}). Recreating."
      # Best-effort: detach all containers from it before deletion.
      local cid
      while IFS= read -r cid; do
        [ -n "$cid" ] || continue
        docker network disconnect -f proxy "$cid" >/dev/null 2>&1 || true
      done < <(docker network inspect -f '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' proxy 2>/dev/null)
      docker network rm proxy >/dev/null 2>&1 || die "Cannot remove existing 'proxy' network. Stop services first."
    else
      log "Network proxy already exists (overlay, attachable)"
      return
    fi
  fi

  log "Creating overlay network: proxy"
  docker network create -d overlay --attachable proxy >/dev/null
}

ensure_env_file() {
  local project="$1"
  local template_name="$2"
  local target_name="$3"
  local template_path="/opt/${project}/${template_name}"
  local target_path="/opt/${project}/${target_name}"

  if [ -f "$target_path" ]; then
    return
  fi

  if [ -f "$template_path" ]; then
    cp "$template_path" "$target_path"
    warn "${target_path} created from template. Fill secrets before production use."
  fi
}

provision_env_files() {
  log "Ensuring env files exist..."
  ensure_env_file "rent_django" ".env.example" ".env"
  ensure_env_file "crm_prvms" ".env.prod.example" ".env.prod"
  ensure_env_file "druzhina" ".env.example" ".env"
  ensure_env_file "kapitan_api" ".env.example" ".env"
  ensure_env_file "kupi_slona" ".env.example" ".env"
  ensure_env_file "vybra" ".env.example" ".env"
  ensure_env_file "bookstack" ".env.example" ".env"

  if [ ! -f /opt/crm_prvms/.env.prod ] && [ -f /opt/crm_prvms/.env ]; then
    cp /opt/crm_prvms/.env /opt/crm_prvms/.env.prod
    warn "/opt/crm_prvms/.env.prod created from existing .env (compose expects .env.prod)"
  fi

  if [ ! -f /opt/crm_prvms/.env ] && [ -f /opt/crm_prvms/.env.prod ]; then
    cp /opt/crm_prvms/.env.prod /opt/crm_prvms/.env
    warn "/opt/crm_prvms/.env created from .env.prod for compose interpolation compatibility"
  fi
}

check_placeholders() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return
  fi
  if grep -Eiv '^\s*#|^\s*$' "$file" | grep -Eiq 'CHANGE_ME|YOUR_|your-email@gmail\.com|your-app-password|example\.com'; then
    warn "Placeholder values detected in ${file}"
  fi
}

check_env_placeholders() {
  log "Checking .env placeholders..."
  check_placeholders /opt/rent_django/.env
  check_placeholders /opt/crm_prvms/.env.prod
  check_placeholders /opt/druzhina/.env
  check_placeholders /opt/kapitan_api/.env
  check_placeholders /opt/kupi_slona/.env
  check_placeholders /opt/vybra/.env
  check_placeholders /opt/bookstack/.env
}

validate_compose_files() {
  log "Validating docker-compose files..."
  local project
  for project in "${PROJECTS[@]}"; do
    local compose_file="/opt/${project}/docker-compose.yml"
    if [ ! -f "$compose_file" ]; then
      warn "Missing compose file: ${compose_file}"
      continue
    fi
    sanitize_compose_file "$compose_file"
    if ! run_compose "$project" -f "$compose_file" config >/dev/null; then
      COMPOSE_FAILS+=("$project")
      warn "Compose validation failed for ${project}"
    fi
  done
}

validate_build_contexts() {
  log "Checking build context prerequisites..."
  [ -f /opt/rent_django/Dockerfile ] || warn "Missing /opt/rent_django/Dockerfile"
  [ -f /opt/crm_prvms/Dockerfile ] || warn "Missing /opt/crm_prvms/Dockerfile"
  [ -f /opt/druzhina/Dockerfile ] || warn "Missing /opt/druzhina/Dockerfile"
  [ -f /opt/druzhina/deploy/Dockerfile.garage ] || warn "Missing /opt/druzhina/deploy/Dockerfile.garage"
  [ -f /opt/druzhina/deploy/garage.toml ] || warn "Missing /opt/druzhina/deploy/garage.toml"
  [ -f /opt/kapitan_api/Dockerfile ] || warn "Missing /opt/kapitan_api/Dockerfile"
  [ -f /opt/kupi_slona/Dockerfile ] || warn "Missing /opt/kupi_slona/Dockerfile"
  [ -f /opt/vybra/Dockerfile ] || warn "Missing /opt/vybra/Dockerfile"
}

install_systemd_units() {
  if [ "$SKIP_SYSTEMD" -eq 1 ]; then
    log "Skipping systemd unit installation by option"
    return
  fi

  log "Installing systemd units..."
  local service_file timer_file

  for service_file in /opt/systemd/*.service; do
    [ -f "$service_file" ] || continue
    install -m 0644 "$service_file" "/etc/systemd/system/$(basename "$service_file")"
  done
  for timer_file in /opt/systemd/*.timer; do
    [ -f "$timer_file" ] || continue
    install -m 0644 "$timer_file" "/etc/systemd/system/$(basename "$timer_file")"
  done

  systemctl daemon-reload
  systemctl enable docker-swarm-services.service >/dev/null 2>&1 || true
  systemctl enable docker-backup.timer >/dev/null 2>&1 || true
}

start_services() {
  if [ "$SKIP_START" -eq 1 ]; then
    log "Skipping service start by option"
    return
  fi
  if [ "${#COMPOSE_FAILS[@]}" -gt 0 ]; then
    warn "Skipping service start because compose validation has failures."
    return
  fi
  log "Starting services via /opt/scripts/start-all.sh..."
  /opt/scripts/start-all.sh
  if [ -x /opt/scripts/check-https.sh ]; then
    log "Running HTTPS/DNS diagnostics..."
    /opt/scripts/check-https.sh || true
  fi
}

print_summary() {
  echo
  echo "========== Bootstrap summary =========="
  if [ "${#COMPOSE_FAILS[@]}" -eq 0 ]; then
    echo "Compose validation: OK"
  else
    echo "Compose validation failures: ${COMPOSE_FAILS[*]}"
  fi

  if [ "${#WARNINGS[@]}" -eq 0 ]; then
    echo "Warnings: none"
  else
    echo "Warnings (${#WARNINGS[@]}):"
    local item
    for item in "${WARNINGS[@]}"; do
      echo "  - ${item}"
    done
  fi
  echo "======================================="
}

main() {
  parse_args "$@"
  require_root
  check_source_bundle

  log "Starting initial server setup..."
  log "Source directory: ${SOURCE_DIR}"

  apt_update_upgrade
  install_system_packages
  install_docker_stack
  ensure_opt_layout
  sync_bundle_to_opt
  prepare_traefik_runtime
  ensure_swarm
  ensure_proxy_network
  provision_env_files
  check_env_placeholders
  validate_compose_files
  validate_build_contexts
  install_systemd_units
  start_services
  print_summary

  if [ "${#COMPOSE_FAILS[@]}" -gt 0 ]; then
    die "Bootstrap completed with compose validation errors."
  fi

  log "Initial server setup completed."
}

main "$@"
