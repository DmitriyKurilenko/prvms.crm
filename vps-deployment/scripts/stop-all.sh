#!/bin/bash
set -e

echo "🛑 Stopping all services..."

PROJECTS=(bookstack vybra kupi_slona kapitan_api druzhina crm_prvms rent_django portainer traefik)

for project in "${PROJECTS[@]}"; do
  echo "🛑 Stopping $project..."
  cd /opt/$project
  docker compose down
  echo "✅ $project stopped"
done

echo ""
echo "✅ All services stopped!"
