#!/bin/bash
set -e

BACKUP_DIR="/opt/backups"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

echo "💾 Starting backup for all projects..."
echo "Backup directory: $BACKUP_DIR"
echo ""

PROJECTS=(rent_django crm_prvms druzhina kapitan_api kupi_slona vybra)

for project in "${PROJECTS[@]}"; do
  echo "🔄 Backing up $project..."
  cd /opt/$project

  # Get DB service name
  DB_SERVICE=$(docker compose ps -q db 2>/dev/null || echo "")

  if [ -z "$DB_SERVICE" ]; then
    echo "  ⚠️  No database service found in $project, skipping..."
    continue
  fi

  # Determine database type
  DB_IMAGE=$(docker inspect "$DB_SERVICE" --format='{{.Config.Image}}')

  if [[ "$DB_IMAGE" == *"postgis"* ]] || [[ "$DB_IMAGE" == *"postgres"* ]]; then
    echo "  📦 PostgreSQL database detected"

    DB_NAME=$(docker compose exec -T db psql -U ${DB_USER:-postgres} -t -c "SELECT datname FROM pg_database WHERE datistemplate = false;" 2>/dev/null | head -1)
    DB_NAME=${DB_NAME:- ${DB_NAME:-$project}}

    BACKUP_FILE="$BACKUP_DIR/${project}_${DATE}.sql.gz"

    docker compose exec -T db pg_dump -U ${DB_USER:-postgres} -d ${DB_NAME} | gzip > $BACKUP_FILE

    echo "  ✅ Backed up to $BACKUP_FILE"
  fi
done

echo ""
echo "🧹 Cleaning old backups (keeping last $RETENTION_DAYS days)..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo ""
echo "🎉 Backup completed!"
ls -lh $BACKUP_DIR | tail -10
