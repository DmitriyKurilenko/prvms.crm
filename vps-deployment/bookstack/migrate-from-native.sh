#!/bin/bash
# Восстановление Bookstack из бекапа нативной установки в Docker
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📚 Bookstack Migration: Native → Docker"
echo "======================================="
echo ""

if [ $# -lt 2 ]; then
  echo "Usage: $0 <db_backup.sql.gz> <uploads_backup.tar.gz>"
  echo ""
  echo "Example:"
  echo "  $0 bookstack_db.sql.gz bookstack_uploads.tar.gz"
  exit 1
fi

DB_BACKUP=$1
FILES_BACKUP=$2

# Проверить файлы
if [ ! -f "$DB_BACKUP" ]; then
  echo "❌ DB backup not found: $DB_BACKUP"
  exit 1
fi

if [ ! -f "$FILES_BACKUP" ]; then
  echo "❌ Files backup not found: $FILES_BACKUP"
  exit 1
fi

# Проверить .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "❌ .env not found. Copy from .env.example and fill in passwords."
  exit 1
fi

source "$SCRIPT_DIR/.env"

cd $SCRIPT_DIR

echo "🗄️  Step 1: Starting MySQL..."
docker compose up -d db
echo "   Waiting for MySQL to initialize..."
sleep 25

until docker compose exec -T db mysqladmin ping -u bookstack -p"$MYSQL_PASSWORD" --silent 2>/dev/null; do
  echo "   Still waiting..."
  sleep 5
done
echo "   ✅ MySQL ready"
echo ""

echo "🗄️  Step 2: Restoring database..."
gunzip < "$DB_BACKUP" | docker compose exec -T db mysql \
  -u "$MYSQL_USER" \
  -p"$MYSQL_PASSWORD" \
  "$MYSQL_DATABASE"
echo "   ✅ Database restored"
echo ""

echo "🚀 Step 3: Starting Bookstack..."
docker compose up -d
echo "   Waiting for Bookstack to start..."
sleep 40
echo "   ✅ Bookstack started"
echo ""

echo "📁 Step 4: Restoring uploaded files..."
VOLUME_PATH=$(docker inspect bookstack-bookstack-1 \
  --format='{{range .Mounts}}{{if eq .Destination "/config"}}{{.Source}}{{end}}{{end}}' 2>/dev/null)

if [ -z "$VOLUME_PATH" ]; then
  echo "   ⚠️  Could not find volume path automatically."
  echo "   Run manually:"
  echo "   docker inspect bookstack-bookstack-1 | grep -A2 '/config'"
else
  echo "   Volume: $VOLUME_PATH"

  # Распаковать во временную директорию
  TMP_DIR=$(mktemp -d)
  tar xzf "$FILES_BACKUP" -C "$TMP_DIR"

  # Найти папки uploads в бекапе
  STORAGE_UPLOADS=$(find "$TMP_DIR" -type d -name "uploads" -path "*/storage/*" | head -1)
  PUBLIC_UPLOADS=$(find "$TMP_DIR" -type d -name "uploads" -path "*/public/*" | head -1)

  if [ -n "$STORAGE_UPLOADS" ]; then
    mkdir -p "$VOLUME_PATH/www/storage/uploads"
    cp -r "$STORAGE_UPLOADS/." "$VOLUME_PATH/www/storage/uploads/"
    echo "   ✅ storage/uploads restored"
  fi

  if [ -n "$PUBLIC_UPLOADS" ]; then
    mkdir -p "$VOLUME_PATH/www/public/uploads"
    cp -r "$PUBLIC_UPLOADS/." "$VOLUME_PATH/www/public/uploads/"
    echo "   ✅ public/uploads restored"
  fi

  # Права
  docker compose exec bookstack chown -R abc:abc \
    /config/www/storage/uploads \
    /config/www/public/uploads 2>/dev/null || true

  rm -rf "$TMP_DIR"
  echo "   ✅ Files restored"
fi

echo ""
echo "🔄 Step 5: Restarting Bookstack..."
docker compose restart bookstack
sleep 15
echo "   ✅ Restarted"
echo ""

echo "✅ Migration complete!"
echo ""
echo "Open: https://${BOOKSTACK_DOMAIN:-docs.kapitan-trips.ru}"
echo ""
echo "⚠️  Check:"
echo "  1. Login works (old credentials from native install)"
echo "  2. Images and attachments are visible"
echo "  3. docker compose logs bookstack | grep ERROR"
