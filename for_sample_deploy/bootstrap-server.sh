#!/usr/bin/env bash

# Full first-time server bootstrap for Docker reverse proxy stack
# Installs Docker/Compose, prepares /opt/{traefik,portainer,scripts},
# creates shared proxy network and starts Traefik + Portainer.

set -Eeuo pipefail

DOMAIN=""
EMAIL=""
PORTAINER_HOST=""
DRY_RUN=false
SKIP_FIREWALL=true

TRAEFIK_DIR="/opt/traefik"
PORTAINER_DIR="/opt/portainer"
SCRIPTS_DIR="/opt/scripts"
PROXY_NETWORK="proxy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✔ $1${NC}"; }
print_error() { echo -e "${RED}✘ $1${NC}"; }
print_info() { echo -e "${YELLOW}➜ $1${NC}"; }

usage() {
    cat <<USAGE
Usage:
  sudo ./bootstrap-server.sh --domain example.com --email admin@example.com [options]

Required:
  --domain            Base domain used for service hostnames
  --email             Email for Let's Encrypt ACME registration

Optional:
  --portainer-host    FQDN for Portainer (default: portainer.<domain>)
  --with-firewall     Configure UFW (allow OpenSSH, 80/tcp, 443/tcp)
  --dry-run           Print actions without executing changes
  -h, --help          Show this help

Examples:
  sudo ./bootstrap-server.sh --domain crm.example.com --email ops@example.com
  sudo ./bootstrap-server.sh --domain example.com --email ops@example.com --with-firewall
USAGE
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

backup_if_exists() {
    local path="$1"
    if [ -f "$path" ] && [ "$DRY_RUN" = false ]; then
        cp -f "$path" "${path}.bak.$(date +%Y%m%d%H%M%S)"
    fi
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --domain)
                DOMAIN="${2:-}"
                shift 2
                ;;
            --email)
                EMAIL="${2:-}"
                shift 2
                ;;
            --portainer-host)
                PORTAINER_HOST="${2:-}"
                shift 2
                ;;
            --with-firewall)
                SKIP_FIREWALL=false
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown argument: $1"
                usage
                exit 1
                ;;
        esac
    done

    if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
        print_error "--domain and --email are required"
        usage
        exit 1
    fi

    if [ -z "$PORTAINER_HOST" ]; then
        PORTAINER_HOST="portainer.${DOMAIN}"
    fi
}

ensure_root() {
    if [ "${EUID}" -ne 0 ]; then
        print_error "Run as root (sudo)."
        exit 1
    fi
}

require_apt() {
    if ! command -v apt-get >/dev/null 2>&1; then
        print_error "This script currently supports Debian/Ubuntu only (apt-get required)."
        exit 1
    fi
}

install_base_packages() {
    print_info "Installing base packages..."
    run_cmd apt-get update -y
    run_cmd apt-get install -y ca-certificates curl gnupg lsb-release ufw
    print_success "Base packages installed"
}

install_docker_if_needed() {
    if command -v docker >/dev/null 2>&1; then
        print_success "Docker is already installed"
        return
    fi

    print_info "Installing Docker Engine + Compose plugin..."
    run_cmd install -m 0755 -d /etc/apt/keyrings
    run_cmd bash -lc "curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo \"$ID\")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg"
    run_cmd chmod a+r /etc/apt/keyrings/docker.gpg
    run_cmd bash -lc "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo \"$ID\") $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable\" > /etc/apt/sources.list.d/docker.list"
    run_cmd apt-get update -y
    run_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    print_success "Docker installed"
}

enable_docker() {
    print_info "Enabling Docker service..."
    run_cmd systemctl enable --now docker
    print_success "Docker service is enabled"
}

configure_firewall_if_requested() {
    if [ "$SKIP_FIREWALL" = true ]; then
        print_info "Firewall configuration skipped (use --with-firewall to enable)"
        return
    fi

    print_info "Configuring UFW (OpenSSH, 80, 443)..."
    run_cmd ufw allow OpenSSH
    run_cmd ufw allow 80/tcp
    run_cmd ufw allow 443/tcp

    if [ "$DRY_RUN" = false ]; then
        if ufw status | grep -qi "inactive"; then
            run_cmd ufw --force enable
        fi
    else
        echo "[dry-run] ufw --force enable"
    fi

    print_success "Firewall is configured"
}

prepare_directories() {
    print_info "Preparing /opt directories..."
    run_cmd mkdir -p "$TRAEFIK_DIR/letsencrypt" "$PORTAINER_DIR" "$SCRIPTS_DIR"

    if [ "$DRY_RUN" = false ]; then
        touch "$TRAEFIK_DIR/letsencrypt/acme.json"
        chmod 600 "$TRAEFIK_DIR/letsencrypt/acme.json"
    else
        echo "[dry-run] touch $TRAEFIK_DIR/letsencrypt/acme.json && chmod 600"
    fi

    print_success "Directories ready"
}

write_traefik_files() {
    print_info "Writing Traefik stack files..."

    if [ "$DRY_RUN" = true ]; then
        echo "[dry-run] write $TRAEFIK_DIR/.env"
        echo "[dry-run] write $TRAEFIK_DIR/docker-compose.yml"
        print_success "Traefik stack files planned"
        return
    fi

    if [ "$DRY_RUN" = false ]; then
        backup_if_exists "$TRAEFIK_DIR/.env"
        backup_if_exists "$TRAEFIK_DIR/docker-compose.yml"
    fi

    cat > "$TRAEFIK_DIR/.env" <<ENV
TRAEFIK_ACME_EMAIL=${EMAIL}
ENV

    cat > "$TRAEFIK_DIR/docker-compose.yml" <<'COMPOSE'
services:
  traefik:
    image: traefik:v3.1
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --certificatesresolvers.le.acme.email=${TRAEFIK_ACME_EMAIL}
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.le.acme.httpchallenge=true
      - --certificatesresolvers.le.acme.httpchallenge.entrypoint=web
      - --accesslog=true
      - --log.level=INFO
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    networks:
      - proxy

networks:
  proxy:
    name: proxy
COMPOSE

    print_success "Traefik stack files written"
}

write_portainer_files() {
    print_info "Writing Portainer stack files..."

    if [ "$DRY_RUN" = true ]; then
        echo "[dry-run] write $PORTAINER_DIR/.env"
        echo "[dry-run] write $PORTAINER_DIR/docker-compose.yml"
        print_success "Portainer stack files planned"
        return
    fi

    if [ "$DRY_RUN" = false ]; then
        backup_if_exists "$PORTAINER_DIR/.env"
        backup_if_exists "$PORTAINER_DIR/docker-compose.yml"
    fi

    cat > "$PORTAINER_DIR/.env" <<ENV
PORTAINER_HOST=${PORTAINER_HOST}
ENV

    cat > "$PORTAINER_DIR/docker-compose.yml" <<'COMPOSE'
services:
  portainer:
    image: portainer/portainer-ce:2.20.3
    restart: unless-stopped
    command: -H unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    networks:
      - proxy
    labels:
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.portainer.rule=Host(`${PORTAINER_HOST}`)
      - traefik.http.routers.portainer.entrypoints=websecure
      - traefik.http.routers.portainer.tls=true
      - traefik.http.routers.portainer.tls.certresolver=le
      - traefik.http.services.portainer.loadbalancer.server.port=9000

volumes:
  portainer_data:

networks:
  proxy:
    external: true
    name: proxy
COMPOSE

    print_success "Portainer stack files written"
}

write_management_scripts() {
    print_info "Writing /opt/scripts helpers..."

    local start_script="$SCRIPTS_DIR/start-all.sh"
    local stop_script="$SCRIPTS_DIR/stop-all.sh"
    local status_script="$SCRIPTS_DIR/status-all.sh"

    if [ "$DRY_RUN" = true ]; then
        echo "[dry-run] write $start_script"
        echo "[dry-run] write $stop_script"
        echo "[dry-run] write $status_script"
        print_success "Helper scripts planned"
        return
    fi

    if [ "$DRY_RUN" = false ]; then
        backup_if_exists "$start_script"
        backup_if_exists "$stop_script"
        backup_if_exists "$status_script"
    fi

    cat > "$start_script" <<'START'
#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE="docker compose"

if ! docker compose version >/dev/null 2>&1; then
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
  else
    echo "Docker Compose not found"
    exit 1
  fi
fi

echo "🚀 Starting all services..."

if ! docker network inspect proxy >/dev/null 2>&1; then
  echo "📡 Creating Docker network: proxy"
  docker network create --driver bridge proxy >/dev/null
fi

echo "📦 Starting traefik..."
$COMPOSE -f /opt/traefik/docker-compose.yml --env-file /opt/traefik/.env up -d

echo "📦 Starting portainer..."
$COMPOSE -f /opt/portainer/docker-compose.yml --env-file /opt/portainer/.env up -d

echo "✅ All core services are started"
START

    cat > "$stop_script" <<'STOP'
#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE="docker compose"

if ! docker compose version >/dev/null 2>&1; then
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
  else
    echo "Docker Compose not found"
    exit 1
  fi
fi

echo "🛑 Stopping all services..."
$COMPOSE -f /opt/portainer/docker-compose.yml --env-file /opt/portainer/.env down || true
$COMPOSE -f /opt/traefik/docker-compose.yml --env-file /opt/traefik/.env down || true

echo "✅ All core services are stopped"
STOP

    cat > "$status_script" <<'STATUS'
#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== Docker containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ""
echo "=== Docker network proxy ==="
if docker network inspect proxy >/dev/null 2>&1; then
  docker network inspect proxy --format 'name={{.Name}} containers={{len .Containers}}'
else
  echo "proxy network not found"
fi
STATUS

    run_cmd chmod +x "$start_script" "$stop_script" "$status_script"

    print_success "Helper scripts written to $SCRIPTS_DIR"
}

ensure_proxy_network() {
    print_info "Ensuring shared Docker network '$PROXY_NETWORK' exists..."
    if [ "$DRY_RUN" = false ]; then
        if docker network inspect "$PROXY_NETWORK" >/dev/null 2>&1; then
            print_success "Network '$PROXY_NETWORK' already exists"
        else
            run_cmd docker network create --driver bridge "$PROXY_NETWORK"
            print_success "Network '$PROXY_NETWORK' created"
        fi
    else
        echo "[dry-run] docker network inspect $PROXY_NETWORK || docker network create --driver bridge $PROXY_NETWORK"
    fi
}

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_BIN="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_BIN="docker-compose"
    else
        print_error "Docker Compose is not available"
        exit 1
    fi
}

validate_compose_files() {
    print_info "Validating generated compose files..."

    if [ "$DRY_RUN" = false ]; then
        $COMPOSE_BIN -f "$TRAEFIK_DIR/docker-compose.yml" --env-file "$TRAEFIK_DIR/.env" config >/dev/null
        $COMPOSE_BIN -f "$PORTAINER_DIR/docker-compose.yml" --env-file "$PORTAINER_DIR/.env" config >/dev/null
    else
        echo "[dry-run] compose config validation"
    fi

    print_success "Compose files are valid"
}

start_core_services() {
    print_info "Starting Traefik and Portainer..."

    if [ "$DRY_RUN" = false ]; then
        $COMPOSE_BIN -f "$TRAEFIK_DIR/docker-compose.yml" --env-file "$TRAEFIK_DIR/.env" up -d
        $COMPOSE_BIN -f "$PORTAINER_DIR/docker-compose.yml" --env-file "$PORTAINER_DIR/.env" up -d
    else
        echo "[dry-run] $COMPOSE_BIN -f $TRAEFIK_DIR/docker-compose.yml --env-file $TRAEFIK_DIR/.env up -d"
        echo "[dry-run] $COMPOSE_BIN -f $PORTAINER_DIR/docker-compose.yml --env-file $PORTAINER_DIR/.env up -d"
    fi

    print_success "Core services started"
}

main() {
    parse_args "$@"
    ensure_root
    require_apt

    print_info "Bootstrap started for domain: $DOMAIN"

    install_base_packages
    install_docker_if_needed
    enable_docker
    configure_firewall_if_requested

    detect_compose
    prepare_directories
    write_traefik_files
    write_portainer_files
    write_management_scripts
    ensure_proxy_network
    validate_compose_files
    start_core_services

    echo ""
    echo "========================================="
    print_success "Server bootstrap is complete"
    echo "========================================="
    echo "Portainer URL: https://$PORTAINER_HOST"
    echo "Traefik stack : $TRAEFIK_DIR"
    echo "Portainer stack: $PORTAINER_DIR"
    echo "Helper scripts: $SCRIPTS_DIR/{start-all.sh,stop-all.sh,status-all.sh}"
    echo ""
    echo "Run to verify:"
    echo "  /opt/scripts/status-all.sh"
}

main "$@"
