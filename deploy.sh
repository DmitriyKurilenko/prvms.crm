#!/bin/bash

# Production deployment script for prvms.crm Platform
# Usage:
#   ./deploy.sh
#   ./deploy.sh --dry-run

set -euo pipefail

ENV_FILE=".env"
DRY_RUN=false
COMPOSE_BIN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error()   { echo -e "${RED}✗ $1${NC}"; }
print_info()    { echo -e "${YELLOW}→ $1${NC}"; }

detect_compose() {
    if docker compose version &> /dev/null; then
        COMPOSE_BIN="docker compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_BIN="docker-compose"
    else
        print_error "Docker Compose is not installed"
        exit 1
    fi
}

compose_cmd() {
    ${COMPOSE_BIN} -f docker-compose.prod.yml --env-file "${ENV_FILE}" "$@"
}

get_env_value() {
    local key="$1"
    local default_value="$2"
    local value
    value=$(grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | tail -n 1 | cut -d '=' -f2-)
    echo "${value:-$default_value}"
}

pin_runtime_env_from_file() {
    print_info "Pinning runtime env from ${ENV_FILE}..."
    export DEBUG="$(get_env_value "DEBUG" "False")"
    export SECURE_SSL_REDIRECT="$(get_env_value "SECURE_SSL_REDIRECT" "True")"
    export SESSION_COOKIE_SECURE="$(get_env_value "SESSION_COOKIE_SECURE" "True")"
    export CSRF_COOKIE_SECURE="$(get_env_value "CSRF_COOKIE_SECURE" "True")"
    export SECURE_HSTS_INCLUDE_SUBDOMAINS="$(get_env_value "SECURE_HSTS_INCLUDE_SUBDOMAINS" "True")"
    print_success "Pinned runtime env values from ${ENV_FILE}"
}

is_valid_bool() {
    local value_lower
    value_lower=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    case "$value_lower" in
        true|false|1|0|yes|no|on|off|'') return 0 ;;
        *) return 1 ;;
    esac
}

validate_bool_env() {
    local key="$1"
    local default_value="$2"
    local value
    value=$(get_env_value "$key" "$default_value")
    if ! is_valid_bool "$value"; then
        print_error "Invalid boolean value for ${key}: '${value}'"
        exit 1
    fi
}

validate_env_values() {
    print_info "Validating ${ENV_FILE} values..."
    validate_bool_env "DEBUG" "False"
    validate_bool_env "SECURE_SSL_REDIRECT" "True"
    validate_bool_env "SESSION_COOKIE_SECURE" "True"
    validate_bool_env "CSRF_COOKIE_SECURE" "True"
    validate_bool_env "SECURE_HSTS_INCLUDE_SUBDOMAINS" "True"
    print_success "Env values format is valid"
}

check_required_env() {
    local missing=()
    local required_keys=(
        "SECRET_KEY"
        "ALLOWED_HOSTS"
        "DB_NAME"
        "DB_USER"
        "DB_PASSWORD"
        "REDIS_PASSWORD"
        "TRAEFIK_HOST"
        "FIELD_ENCRYPTION_KEY"
    )

    print_info "Checking required env variables..."

    for key in "${required_keys[@]}"; do
        local value
        value=$(get_env_value "$key" "")
        if [ -z "$value" ]; then
            missing+=("$key")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        print_error "Missing required env variables: ${missing[*]}"
        exit 1
    fi

    print_success "Required env variables present"
}

check_requirements() {
    print_info "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    detect_compose

    if [ ! -f "${ENV_FILE}" ]; then
        print_error "${ENV_FILE} not found"
        print_info "Copy .env.prod.example to ${ENV_FILE} and fill in the values"
        exit 1
    fi

    print_success "Requirements met"
}

check_traefik() {
    print_info "Checking shared Traefik proxy..."

    if ! docker network inspect traefik >/dev/null 2>&1; then
        print_error "Docker network 'traefik' does not exist. Create it first: docker network create traefik"
        exit 1
    fi

    if ! docker ps --format '{{.Names}}' | grep -q '^traefik$'; then
        print_error "Traefik container is not running. Start the shared Traefik instance first."
        exit 1
    fi

    print_success "Traefik proxy is ready"
}

validate_compose() {
    print_info "Validating docker-compose.prod.yml..."
    compose_cmd config > /dev/null
    print_success "Compose configuration is valid"
}

backup_database() {
    print_info "Creating database backup..."
    mkdir -p ./backups

    local db_user db_name backup_file
    db_user=$(get_env_value "DB_USER" "platform")
    db_name=$(get_env_value "DB_NAME" "platform_db")
    backup_file="./backups/db_backup_$(date +%Y%m%d_%H%M%S).sql"

    if compose_cmd ps --services --status running 2>/dev/null | grep -qx "db"; then
        compose_cmd exec -T db pg_dump -U "$db_user" "$db_name" > "$backup_file"
        print_success "Database backup: $backup_file"
    else
        print_info "Database not running, skipping backup"
    fi
}

build_images() {
    print_info "Building Docker images..."
    compose_cmd build
    print_success "Images built"
}

run_migrations() {
    print_info "Running schema migrations..."
    compose_cmd run --rm migrate
    print_success "Migrations done"
}

collect_static() {
    print_info "Collecting static files..."
    compose_cmd run --rm web python manage.py collectstatic --noinput
    print_success "Static files collected"
}

django_check() {
    print_info "Running Django deploy check..."
    compose_cmd run --rm web python manage.py check --deploy
    print_success "Django check passed"
}

restart_services() {
    print_info "Restarting services..."
    compose_cmd down
    compose_cmd up -d
    print_success "Services started"
}

service_is_up() {
    local service_name="$1"
    compose_cmd ps --services --status running 2>/dev/null | grep -qx "$service_name"
}

wait_for_services() {
    print_info "Waiting for services to be healthy..."

    local max_attempts=30 attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if service_is_up "web" && service_is_up "frontend-app"; then
            echo ""
            print_success "Services are up"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    print_error "Services failed to start"
    compose_cmd ps
    compose_cmd logs --tail=80 web frontend-app db
    return 1
}

show_status() {
    print_info "Service status:"
    compose_cmd ps
}

main() {
    echo "================================================"
    echo "   prvms.crm Platform — Production Deployment"
    echo "================================================"
    echo ""

    check_requirements
    pin_runtime_env_from_file
    validate_compose
    check_required_env
    validate_env_values

    if [ "$DRY_RUN" = true ]; then
        print_success "Dry run passed. No changes made."
        return 0
    fi

    check_traefik

    if [ "${SKIP_BACKUP:-false}" != "true" ]; then
        backup_database
    fi

    build_images
    run_migrations
    collect_static
    django_check
    restart_services
    wait_for_services
    show_status

    echo ""
    echo "================================================"
    print_success "Deployment completed!"
    echo "================================================"
    echo ""
    print_info "Useful commands:"
    echo "  Logs:     docker compose -f docker-compose.prod.yml logs -f"
    echo "  Status:   docker compose -f docker-compose.prod.yml ps"
    echo "  Shell:    docker compose -f docker-compose.prod.yml exec web bash"
    echo ""
}

main "$@"
