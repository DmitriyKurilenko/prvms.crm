#!/usr/bin/env bash
#
# prvms.crm production deploy.
# Run on the VPS, from /opt/crm_prvms (the git checkout).
#
# Usage:
#   ./deploy.sh                  # full deploy (git pull + build + migrate + up)
#   ./deploy.sh --no-pull        # skip git pull (useful when deploying a hotfix branch already checked out)
#   ./deploy.sh --no-build       # reuse existing images (faster, only restarts containers)
#   ./deploy.sh --dry-run        # validate env + compose, do not change running containers

set -Eeuo pipefail

ENV_FILE=".env.prod"
COMPOSE_FILE="docker-compose.yml"
DRY_RUN=false
SKIP_PULL=false
SKIP_BUILD=false
COMPOSE_BIN=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✔ $1${NC}"; }
print_error()   { echo -e "${RED}✘ $1${NC}"; }
print_info()    { echo -e "${YELLOW}➜ $1${NC}"; }

usage() {
  cat <<USAGE
Usage: ./deploy.sh [options]

Options:
  --no-pull    Skip 'git pull' (deploy whatever is checked out)
  --no-build   Skip 'docker compose build' (reuse existing images)
  --dry-run    Validate env + compose only, do not touch containers
  -h, --help   Show this help
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-pull)  SKIP_PULL=true;  shift ;;
    --no-build) SKIP_BUILD=true; shift ;;
    --dry-run)  DRY_RUN=true;    shift ;;
    -h|--help)  usage; exit 0 ;;
    *) print_error "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

# ---------- Compose detection -------------------------------------------------

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="docker-compose"
  else
    print_error "Docker Compose is not installed"
    exit 1
  fi
}

compose_cmd() {
  ${COMPOSE_BIN} -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

# ---------- Env file validation ----------------------------------------------

get_env_value() {
  local key="$1"
  grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d '=' -f2- || true
}

REQUIRED_KEYS=(
  PUBLIC_HOSTNAME
  DB_NAME
  DB_USER
  DB_PASSWORD
  DATABASE_URL
  REDIS_PASSWORD
  REDIS_URL
  SECRET_KEY
  ALLOWED_HOSTS
  CSRF_TRUSTED_ORIGINS
  FRONTEND_APP_URL
  FIELD_ENCRYPTION_KEY
)

check_required_env() {
  print_info "Validating ${ENV_FILE}..."
  if [ ! -f "${ENV_FILE}" ]; then
    print_error "${ENV_FILE} not found. Copy .env.prod.example and fill in real values."
    exit 1
  fi
  local missing=()
  for key in "${REQUIRED_KEYS[@]}"; do
    local value
    value="$(get_env_value "$key")"
    if [ -z "${value}" ] || [[ "${value}" == CHANGE_ME* ]]; then
      missing+=("$key")
    fi
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    print_error "Missing or placeholder values for: ${missing[*]}"
    exit 1
  fi
  print_success "All required env keys present"
}

# ---------- Compose interpolation pinning ------------------------------------

pin_runtime_env_from_file() {
  # Compose interpolation favours shell env over --env-file. Re-export the
  # public hostname (used in Traefik labels) so substitution is deterministic.
  print_info "Pinning runtime env vars used during compose interpolation..."
  export PUBLIC_HOSTNAME="$(get_env_value PUBLIC_HOSTNAME)"
  print_success "Pinned PUBLIC_HOSTNAME=${PUBLIC_HOSTNAME}"
}

validate_compose() {
  print_info "Validating ${COMPOSE_FILE}..."
  compose_cmd config >/dev/null
  print_success "Compose file is valid"
}

# ---------- Network / runtime dirs -------------------------------------------

ensure_proxy_network() {
  if docker network inspect proxy >/dev/null 2>&1; then
    print_success "Docker network 'proxy' exists"
  else
    print_error "Docker network 'proxy' is missing — run /opt/scripts/init-server.sh first"
    exit 1
  fi
}

ensure_runtime_dirs() {
  print_info "Ensuring runtime dirs exist..."
  mkdir -p /opt/crm_prvms/logs /opt/crm_prvms/media /opt/backups/crm_prvms
  print_success "Runtime dirs ready"
}

# ---------- Git ---------------------------------------------------------------

git_pull() {
  if [ "$SKIP_PULL" = true ]; then
    print_info "Skipping git pull (--no-pull)"
    return
  fi
  if [ ! -d .git ]; then
    print_error "Not a git checkout (no .git in $(pwd)). Clone the repo into /opt/crm_prvms first."
    exit 1
  fi
  print_info "Pulling latest commits..."
  git fetch --all --prune
  git pull --ff-only
  print_success "Up to date: $(git rev-parse --short HEAD)"
}

# ---------- Backup -----------------------------------------------------------

backup_database() {
  if ! compose_cmd ps db | grep -q 'Up'; then
    print_info "DB container not running — skipping backup"
    return
  fi
  local dir="/opt/backups/crm_prvms"
  local file
  file="${dir}/db_$(date +%Y%m%d_%H%M%S).sql.gz"
  mkdir -p "${dir}"
  print_info "Creating database backup -> ${file}"
  compose_cmd exec -T db sh -c "pg_dumpall -U $(get_env_value DB_USER)" | gzip > "${file}"
  print_success "Backup written"
}

# ---------- Build / migrate / up ---------------------------------------------

build_images() {
  if [ "$SKIP_BUILD" = true ]; then
    print_info "Skipping docker compose build (--no-build)"
    return
  fi
  print_info "Building images (web + frontend-app)..."
  compose_cmd build --pull
  print_success "Images built"
}

run_migrate_and_collectstatic() {
  # Compose's depends_on already gates web on `migrate` finishing successfully,
  # but running it explicitly here surfaces migration errors before we restart
  # public-facing containers.
  print_info "Running migrations + collectstatic..."
  compose_cmd run --rm migrate
  print_success "Migrate + collectstatic completed"
}

bring_up() {
  print_info "Bringing up containers..."
  compose_cmd up -d --remove-orphans
  print_success "Compose up -d completed"
}

# ---------- Health checks -----------------------------------------------------

wait_for_health() {
  print_info "Waiting for services to become healthy..."
  local timeout=180
  local elapsed=0
  while [ $elapsed -lt $timeout ]; do
    local web_ok frontend_ok
    web_ok=$(compose_cmd ps web | tail -n +2 | grep -c "healthy" || true)
    frontend_ok=$(compose_cmd ps frontend-app | tail -n +2 | grep -c "healthy" || true)
    if [ "$web_ok" -ge 1 ] && [ "$frontend_ok" -ge 1 ]; then
      print_success "web + frontend-app are healthy"
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
    echo -n "."
  done
  echo ""
  print_error "Services did not become healthy within ${timeout}s"
  print_info "Container status:"
  compose_cmd ps
  print_info "Recent web logs:"
  compose_cmd logs --tail=80 web || true
  exit 1
}

show_status() {
  print_info "Final container status:"
  compose_cmd ps
}

# ---------- Main --------------------------------------------------------------

main() {
  echo "==========================================="
  echo " prvms.crm production deploy"
  echo "==========================================="
  echo ""

  detect_compose
  check_required_env
  pin_runtime_env_from_file
  validate_compose
  ensure_proxy_network

  if [ "$DRY_RUN" = true ]; then
    print_success "Dry-run passed. No changes applied."
    return 0
  fi

  ensure_runtime_dirs
  git_pull
  backup_database
  build_images
  run_migrate_and_collectstatic
  bring_up
  wait_for_health
  show_status

  echo ""
  echo "==========================================="
  print_success "Deploy completed: https://$(get_env_value PUBLIC_HOSTNAME)"
  echo "==========================================="
}

main "$@"
