#!/bin/bash

# SSL Certificate Setup Script using Let's Encrypt / Certbot
# Usage: sudo ./setup-ssl.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error()   { echo -e "${RED}✗ $1${NC}"; }
print_info()    { echo -e "${YELLOW}→ $1${NC}"; }

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
SSL_DIR="./nginx/ssl"

compose_cmd() {
    if docker compose version &> /dev/null; then
        docker compose -f "${COMPOSE_FILE}" "$@"
    else
        docker-compose -f "${COMPOSE_FILE}" "$@"
    fi
}

is_port_80_busy() {
    ss -ltn '( sport = :80 )' 2>/dev/null | grep -q ':80'
}

free_port_80() {
    print_info "Ensuring port 80 is free for Let's Encrypt challenge..."

    if compose_cmd ps 2>/dev/null | grep -q "nginx"; then
        print_info "Stopping docker nginx temporarily..."
        compose_cmd stop nginx || true
    fi

    for svc in nginx apache2 httpd caddy; do
        if systemctl list-unit-files 2>/dev/null | grep -q "^${svc}\.service"; then
            if systemctl is-active --quiet "$svc" 2>/dev/null; then
                print_info "Stopping system service: $svc"
                systemctl stop "$svc" || true
            fi
        fi
    done

    if is_port_80_busy; then
        print_error "Port 80 is still busy. Stop the process and re-run."
        ss -ltnp '( sport = :80 )' || true
        exit 1
    fi

    print_success "Port 80 is free"
}

if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root: sudo ./setup-ssl.sh"
    exit 1
fi

if [ ! -f "${COMPOSE_FILE}" ]; then
    print_error "${COMPOSE_FILE} not found in current directory"
    exit 1
fi

read -rp "Enter your domain name (e.g., demo.example.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    print_error "Domain name cannot be empty"
    exit 1
fi

read -rp "Enter your email for renewal notifications: " EMAIL
if [ -z "$EMAIL" ]; then
    print_error "Email cannot be empty"
    exit 1
fi

print_info "Setting up SSL for: $DOMAIN"

if ! command -v certbot &> /dev/null; then
    print_info "Installing certbot..."
    if [ -f /etc/debian_version ]; then
        apt-get update -qq
        apt-get install -y certbot
    elif [ -f /etc/redhat-release ]; then
        yum install -y certbot
    else
        print_error "Unsupported OS. Install certbot manually."
        exit 1
    fi
    print_success "Certbot installed"
fi

mkdir -p "$SSL_DIR"

free_port_80

print_info "Requesting certificate (domain + www)..."
if ! certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"; then
    print_info "www.$DOMAIN failed, retrying with $DOMAIN only..."
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN"
fi

if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    print_error "Certificate not found after certbot run"
    exit 1
fi

print_success "Certificate obtained"

install -m 644 "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/fullchain.pem"
install -m 600 "/etc/letsencrypt/live/$DOMAIN/privkey.pem"   "$SSL_DIR/privkey.pem"
install -m 644 "/etc/letsencrypt/live/$DOMAIN/chain.pem"     "$SSL_DIR/chain.pem"
print_success "Certificates copied to $SSL_DIR"

# Update ENV_FILE with nginx SSL vars
print_info "Updating ${ENV_FILE} with nginx SSL variables..."
touch "${ENV_FILE}"
sed -i.bak '/^NGINX_SERVER_NAME=/d;/^NGINX_SSL_CERT_PATH=/d;/^NGINX_SSL_KEY_PATH=/d' "${ENV_FILE}"
{
    echo "NGINX_SERVER_NAME=$DOMAIN"
    echo "NGINX_SSL_CERT_PATH=/etc/nginx/ssl/fullchain.pem"
    echo "NGINX_SSL_KEY_PATH=/etc/nginx/ssl/privkey.pem"
} >> "${ENV_FILE}"
print_success "${ENV_FILE} updated"

# Renewal hook to copy certs and restart nginx
HOOK_FILE="/etc/letsencrypt/renewal-hooks/post/reload-nginx-platform.sh"
PROJ_DIR="$(pwd)"
cat > "$HOOK_FILE" <<HOOK
#!/bin/bash
set -e
install -m 644 /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ${PROJ_DIR}/${SSL_DIR#./}/fullchain.pem
install -m 600 /etc/letsencrypt/live/${DOMAIN}/privkey.pem   ${PROJ_DIR}/${SSL_DIR#./}/privkey.pem
install -m 644 /etc/letsencrypt/live/${DOMAIN}/chain.pem     ${PROJ_DIR}/${SSL_DIR#./}/chain.pem
cd "${PROJ_DIR}"
if docker compose version >/dev/null 2>&1; then
    docker compose -f ${COMPOSE_FILE} restart nginx
else
    docker-compose -f ${COMPOSE_FILE} restart nginx
fi
HOOK
chmod +x "$HOOK_FILE"
print_success "Auto-renewal hook installed"

if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet") | crontab -
    print_success "Auto-renewal cron job added (daily at 03:00)"
fi

echo ""
echo "================================================"
print_success "SSL setup completed!"
echo "================================================"
echo ""
echo "  Domain:  $DOMAIN"
echo "  Certs:   $SSL_DIR/"
echo ""
print_info "Next steps:"
echo "  1. Run: ./deploy.sh"
echo "  2. Test: https://$DOMAIN"
echo "  3. SSL grade: https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
echo ""
