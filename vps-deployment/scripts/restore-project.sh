#!/bin/bash
set -e

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project_name> <backup_file>"
  echo ""
  echo "Examples:"
  echo "  $0 rent_django /opt/backups/rent_django_2026-04-27_02-00-00.sql.gz"
  echo ""
  exit 1
fi

PROJECT=$1
BACKUP_FILE=$2

if [ ! -f "$BACKUP_FILE" ]; then
  echo "❌ Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "⚠️  WARNING: This will restore the database from backup!"
echo "Project: $PROJECT"
echo "Backup: $BACKUP_FILE"
echo ""
read -p "Are you sure? (yes/no) " -n 3
echo ""

if [ "$REPLY" != "yes" ]; then
  echo "❌ Cancelled"
  exit 1
fi

cd /opt/$PROJECT

echo ""
echo "🔄 Restoring from backup..."

# Get DB service
DB_SERVICE=$(docker compose ps -q db 2>/dev/null)

if [ -z "$DB_SERVICE" ]; then
  echo "❌ Database service not found"
  exit 1
fi

# Drop all connections and restore
docker compose exec -T db psql -U ${DB_USER:-postgres} -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname IS NOT NULL;" 2>/dev/null || true

gunzip < "$BACKUP_FILE" | docker compose exec -T db psql -U ${DB_USER:-postgres}

echo ""
echo "✅ Restore completed!"
