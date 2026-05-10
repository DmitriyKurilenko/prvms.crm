#!/bin/bash
set -e

echo "🚀 Deploying all services (git pull + rebuild)..."

PROJECTS=(rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack)

for project in "${PROJECTS[@]}"; do
  echo ""
  echo "📦 Deploying $project..."
  cd /opt/$project

  # Check if it's a git repo
  if [ -d .git ]; then
    echo "  📥 Git pull..."
    git pull origin main || true
  fi

  echo "  🔨 Building and restarting..."
  docker compose down
  docker compose up -d --build

  echo "  ✅ $project deployed"
done

echo ""
echo "🎉 All services deployed!"
echo ""
echo "Check status with: /opt/scripts/status-all.sh"
