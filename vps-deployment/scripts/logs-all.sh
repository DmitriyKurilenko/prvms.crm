#!/bin/bash

if [ $# -eq 0 ]; then
  echo "Usage: $0 <service_name> [lines]"
  echo ""
  echo "Examples:"
  echo "  $0 web              # Last 50 lines of web service logs"
  echo "  $0 web 100          # Last 100 lines of web service logs"
  echo "  $0 celery -f        # Follow celery logs live"
  echo ""
  exit 1
fi

SERVICE=$1
LINES=${2:--50}

echo "📋 Searching for service: $SERVICE"
echo ""

# Search in all projects
for project in rent_django crm_prvms druzhina kapitan_api kupi_slona vybra; do
  cd /opt/$project

  # Check if service exists in this project
  if docker compose ps | grep -q "$SERVICE"; then
    echo "Found in $project:"
    docker compose logs $LINES "$SERVICE"
    exit 0
  fi
done

echo "❌ Service '$SERVICE' not found in any project"
exit 1
