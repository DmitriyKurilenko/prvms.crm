# Production Deployment для 6 проектов на одном VPS

## Структура
```
/opt/
├── traefik/              # Reverse proxy + SSL
├── portainer/            # Web UI для управления
├── crm_prvms/            # CRM проект
├── druzhina/             # Druzhina проект
├── kapitan_api/          # API проект
├── kupi_slona/           # Shop проект
├── rent_django/          # Лодки
├── vybra/                # Vybra (парсинг)
├── bookstack/            # Wiki (open-source)
├── scripts/              # Управление всеми проектами
└── backups/              # Автоматические бэкапы БД
```

## Требования VPS

### Минимум (рекомендуется):
- **CPU**: 4 vCPU
- **RAM**: 8 GB (все контейнеры с лимитами, реально ~5-5.5 GB на idle с Bookstack)
- **SSD**: 200+ GB
- **OS**: Ubuntu 22.04+ или Debian 12+

### Лучше иметь:
- **CPU**: 8 vCPU
- **RAM**: 16 GB
- **SSD**: 300+ GB

**Детали**: [4CPU_8GB_OPTIMIZED.md](4CPU_8GB_OPTIMIZED.md) — оптимизировано для скромных VPS

## Быстрый старт

### Вариант A (рекомендуется): one-shot bootstrap
```bash
# На VPS под root (или через sudo):
cd /opt
# Скопируйте сюда содержимое vps-deployment (traefik/, scripts/, systemd/, ...)

chmod +x /opt/scripts/*.sh
/opt/scripts/init-server.sh
```

Скрипт `init-server.sh` автоматически:
- устанавливает Docker + docker compose plugin (если не установлены),
- инициализирует Docker Swarm (если inactive),
- создаёт overlay-сеть `proxy` (если отсутствует),
- готовит `/opt/traefik/letsencrypt/acme.json`,
- синхронизирует compose/systemd/scripts файлы в `/opt`,
- создаёт отсутствующие `.env` из шаблонов,
- запускает все сервисы через `/opt/scripts/start-all.sh`.

### Вариант B: ручной пошаговый запуск
### 1. SSH на VPS и подготовка
```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Docker + Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install -y docker-compose-plugin

# Создать директорию проектов
sudo mkdir -p /opt
sudo chown $USER:$USER /opt
cd /opt
```

### 2. Инициализировать Docker Swarm
```bash
docker swarm init

# Если несколько машин:
# docker swarm init --advertise-addr <IP>
```

### 3. Создать overlay сеть для Traefik
```bash
docker network create -d overlay --attachable proxy
```

### 4. Развернуть Traefik (reverse proxy)
```bash
cd /opt/traefik
docker compose up -d
```

### 5. Развернуть Portainer (управление)
```bash
cd /opt/portainer
docker compose up -d
```

Портал доступен на: **https://your-vps-ip:9443**

### 6. Развернуть каждый проект
```bash
# Копировать .env из шаблонов и заполнить
for project in rent_django crm_prvms druzhina kapitan_api kupi_slona vybra bookstack; do
  cd /opt/$project
  cp .env.example .env
  # Отредактировать .env с реальными значениями
  docker compose up -d
done
```

## Управление проектами

### Все проекты сразу
```bash
# Стартовать все
/opt/scripts/start-all.sh

# Остановить все
/opt/scripts/stop-all.sh

# Деплой с перестроением (после git pull)
/opt/scripts/deploy-all.sh

# Логи всех проектов
/opt/scripts/logs-all.sh service_name

# Статус всех проектов
/opt/scripts/status-all.sh

# Диагностика HTTPS/DNS/Traefik
/opt/scripts/check-https.sh
```

### Отдельный проект
```bash
cd /opt/rent_django

# Логи
docker compose logs -f web

# Перезагрузить
docker compose restart web

# Обновить (git pull + rebuild)
docker compose down
git pull origin main
docker compose up -d --build
```

## Мониторинг

### Портал Portainer
https://your-vps-ip:9443

### Traefik Dashboard
http://your-vps-ip:8080

### Логи
```bash
# Docker daemon
journalctl -u docker.service -f

# Конкретный сервис
docker logs container_name -f

# Все логи в одном месте
tail -f /opt/*/logs/*.log
```

## Бэкапы

### Автоматический бэкап БД (каждый день в 2:00 AM)
```bash
# Добавить в crontab
0 2 * * * /opt/scripts/backup-all.sh
```

### Ручной бэкап
```bash
/opt/scripts/backup-project.sh rent_django
```

## SSL сертификаты

Traefik автоматически выполняет renew через Let's Encrypt. Проверить статус:
```bash
docker exec traefik-traefik-1 ls -la /letsencrypt/certs/
```

## Troubleshooting

### Проект не стартует
```bash
cd /opt/project_name
docker compose logs  # смотреть ошибки
docker compose up -d  # попытка снова
```

### Нет связи между сервисами
```bash
# Проверить, что сеть существует
docker network ls | grep proxy

# Проверить, что сервис в сети
docker inspect service_name | grep proxy
```

### Traefik не маршрутизирует запросы
1. Проверить labels в docker-compose.yml
2. Проверить Traefik dashboard: http://vps-ip:8080
3. Проверить logs: `docker logs traefik-traefik-1`

### Out of Disk
```bash
# Очистить unused images/volumes
docker image prune -a --force
docker volume prune --force

# Проверить размер
docker system df
```

## Обновление проекта

```bash
cd /opt/project_name

# Pull latest
git pull origin main

# Rebuild и redeploy
docker compose down
docker compose up -d --build

# Verify
docker compose ps
docker compose logs web
```

## Восстановление из бэкапа

```bash
# Список бэкапов
ls -lah /opt/backups/

# Восстановить конкретный проект
/opt/scripts/restore-project.sh rent_django /opt/backups/rent_django-2026-04-27.sql.gz
```

## SSH ключи и доступ

### Добавить SSH ключ для деплоя (в GitHub Actions или локально)
```bash
# На локальной машине
ssh-keygen -t ed25519 -f ~/.ssh/vps-deploy -N ""

# На VPS добавить публичный ключ
cat ~/.ssh/vps-deploy.pub >> ~/.ssh/authorized_keys
```

### Deploy без пароля
```bash
# Добавить в ~/.ssh/config
Host vps
  HostName your-vps-ip
  User deploy
  IdentityFile ~/.ssh/vps-deploy
  StrictHostKeyChecking no
```

## Контакты и поддержка
- Email: hvosdt@gmail.com
- Traefik: http://your-vps-ip:8080
- Portainer: https://your-vps-ip:9443

---

**Создано:** 2026-04-27  
**Версия:** 1.0 (Swarm + Traefik + Portainer)
