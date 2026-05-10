#!/usr/bin/env bash
set -Eeuo pipefail

PROJECTS=(traefik portainer rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)

echo "📊 Service Status Report"
echo "======================="
echo

echo "🐋 Docker Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo
echo "📚 Compose Projects:"
for project in "${PROJECTS[@]}"; do
  echo
  echo "▶️  ${project}:"
  if [ ! -d "/opt/${project}" ]; then
    echo "  ⚠️  /opt/${project} not found"
    continue
  fi
  if [ ! -f "/opt/${project}/docker-compose.yml" ]; then
    echo "  ⚠️  /opt/${project}/docker-compose.yml not found"
    continue
  fi

  if [ "$project" = "crm_prvms" ] && [ -f "/opt/${project}/.env.prod" ]; then
    (cd "/opt/${project}" && docker compose --env-file "/opt/${project}/.env.prod" ps) || true
  else
    (cd "/opt/${project}" && docker compose ps) || true
  fi
done

echo
echo "🌐 Docker Networks:"
docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" | grep -E "NAME|proxy|backend" || true

echo
echo "💾 Disk Usage:"
docker system df

echo
echo "📊 Memory Usage:"
free -h

if [ -x /opt/scripts/check-https.sh ]; then
  echo
  /opt/scripts/check-https.sh || true
fi
