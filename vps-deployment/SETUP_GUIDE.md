# 🚀 Production Deployment Setup Guide

Complete guide для развертывания всех 6 проектов на одном VPS с Docker Swarm + Traefik + Portainer.

## Требования

- **VPS**: Ubuntu 22.04 LTS (или Debian 12)
- **CPU**: 12+ cores
- **RAM**: 16+ GB  
- **Disk**: 200+ GB SSD
- **Network**: Публичный IP с доступом на порты 80, 443, 8000, 9443

## Быстрый путь (автоматически)

Если структура `vps-deployment` уже скопирована в `/opt`, можно выполнить полную первичную настройку одной командой:

```bash
chmod +x /opt/scripts/*.sh
/opt/scripts/init-server.sh
```

`init-server.sh` сделает установку Docker/Compose (если нужно), инициализацию Swarm, создание сети `proxy`, подготовку Traefik, env-файлов и запуск сервисов.

## Шаг 1: Подготовка VPS

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git wget htop

# Отключить swap для Docker Swarm
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

# Выставить правильные лимиты
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## Шаг 2: Установка Docker

```bash
# Установить Docker + Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавить текущего пользователя в docker группу
sudo usermod -aG docker $USER
newgrp docker

# Проверить версию
docker --version
docker compose version
```

## Шаг 3: Инициализация Docker Swarm

```bash
# Инициализировать Swarm
docker swarm init

# Если на этой машине несколько IP:
# docker swarm init --advertise-addr <YOUR_MAIN_IP>

# Проверить статус
docker node ls
```

## Шаг 4: Создание директорий и загрузка конфигов

```bash
# Создать структуру
sudo mkdir -p /opt
sudo chown $USER:$USER /opt
cd /opt

# Скачать конфиги (или скопировать из этого repo)
# Option 1: Clone from Git
git clone https://github.com/yourrepo/vps-deployment.git /tmp/deploy
cp -r /tmp/deploy/* /opt/

# Option 2: Или скопировать файлы вручную
# Убедитесь что структура:
# /opt/
# ├── traefik/docker-compose.yml
# ├── portainer/docker-compose.yml
# ├── rent_django/docker-compose.yml
# ├── crm_prvms/docker-compose.yml
# ├── druzhina/docker-compose.yml
# ├── kapitan_api/docker-compose.yml
# ├── kupi_slona/docker-compose.yml
# ├── vybra/docker-compose.yml
# ├── scripts/
# └── systemd/

# Выставить права на скрипты
chmod +x /opt/scripts/*.sh
```

## Шаг 5: DNS и сертификаты

Убедитесь что все домены указывают на VPS:

```bash
# Проверить DNS
nslookup arenda.kapitan-trips.ru
nslookup crm.prvms.ru
nslookup druzhina.prvms.ru
nslookup kapitan.prvms.ru
nslookup slon.prvms.ru
nslookup vybra.prvms.ru

# Все должны вернуть IP вашего VPS
```

## Шаг 6: Создание Proxy сети

```bash
# Создать overlay сеть для Traefik и всех проектов
docker network create -d overlay --attachable proxy

# Проверить
docker network ls | grep proxy
```

## Шаг 7: Запуск Traefik (Reverse Proxy + SSL)

```bash
cd /opt/traefik

# Создать директории для логов и сертификатов
mkdir -p letsencrypt logs
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json

# Запустить
docker compose up -d

# Проверить логи
docker compose logs -f traefik
```

Traefik доступен на: **http://YOUR_VPS_IP:8080** (Dashboard)

## Шаг 8: Запуск Portainer (Web UI)

```bash
cd /opt/portainer

docker compose up -d

# Проверить
docker compose logs portainer
```

Portainer доступен на: **https://YOUR_VPS_IP:9443**

Первый запуск: установить пароль администратора.

## Шаг 9: Подготовка проектов

Для каждого проекта нужно подготовить:
1. `.env` файл с переменными
2. Исходный код (git clone или копия)

### Пример для rent_django:

```bash
cd /opt/rent_django

# Скопировать исходный код проекта
# (Если его ещё нет, клонировать из гита)
git clone https://github.com/yourrepo/rent_django.git .

# Создать .env из шаблона
cp .env.example .env

# Редактировать .env
nano .env
# Установить: SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD, S3 credentials и т.д.

# То же самое для остальных проектов
for project in crm_prvms druzhina kapitan_api kupi_slona vybra; do
  cd /opt/$project
  # ... скопировать код и создать .env
done
```

## Шаг 10: Запуск всех проектов

```bash
# Запустить все
/opt/scripts/start-all.sh

# Или запустить по одному:
cd /opt/rent_django && docker compose up -d
cd /opt/crm_prvms && docker compose up -d
# и т.д.

# Проверить статус
/opt/scripts/status-all.sh

# Проверить HTTPS/DNS/Traefik
/opt/scripts/check-https.sh

# Смотреть логи
docker compose logs -f web  # в директории проекта
```

## Шаг 11: Автозапуск при перезагрузке VPS

```bash
# Скопировать systemd units
sudo cp /opt/systemd/*.service /etc/systemd/system/
sudo cp /opt/systemd/*.timer /etc/systemd/system/

# Включить при загрузке
sudo systemctl daemon-reload
sudo systemctl enable docker-swarm-services.service
sudo systemctl enable docker-backup.timer

# Проверить
sudo systemctl status docker-swarm-services.service
sudo systemctl list-timers
```

## Шаг 12: Настройка резервных копий

```bash
# Проверить, что backup скрипт работает
/opt/scripts/backup-all.sh

# Проверить бэкапы
ls -lh /opt/backups/

# Для ручного расписания в crontab:
# 0 2 * * * /opt/scripts/backup-all.sh > /var/log/backups.log 2>&1

# Или используйте systemd timer (уже установлен выше)
```

## Шаг 13: Настройка SSL

Traefik автоматически получает сертификаты через Let's Encrypt. Проверить:

```bash
# Посмотреть сертификаты
docker exec traefik-traefik-1 ls -la /letsencrypt/certs/

# Проверить логи Traefik
docker logs traefik-traefik-1 | grep -i "acme\|certificate"
```

## Шаг 14: Bookstack Wiki (опционально)

Если хотите вики:

```bash
cd /opt/bookstack
cp .env.example .env
nano .env  # Отредактировать

docker compose up -d

# Дефолтные credentials:
# Email: admin@example.com
# Password: password

# ⚠️ Срочно смените пароль!
```

Детали: [bookstack/README.md](bookstack/README.md)

## Готово! ✅

Все проекты должны быть доступны:

- 🏠 **arenda.kapitan-trips.ru** - Лодки
- 💼 **crm.prvms.ru** - CRM
- 🏛 **druzhina.prvms.ru** - Druzhina
- ⚓ **kapitan.prvms.ru** - Капитан API
- 🐘 **slon.prvms.ru** - Купи Слона
- 👁 **vybra.prvms.ru** - Vybra (парсинг)
- 📚 **docs.kapitan-trips.ru** - Bookstack Wiki

---

## Частые команды

```bash
# Статус всех сервисов
/opt/scripts/status-all.sh

# Диагностика HTTPS/DNS/Traefik
/opt/scripts/check-https.sh

# Просмотр логов
docker compose -f /opt/rent_django/docker-compose.yml logs -f web

# Перезагрузить проект
cd /opt/rent_django && docker compose restart

# Обновить проект
cd /opt/rent_django && git pull && docker compose up -d --build

# Очистить место на диске
docker image prune -a --force
docker volume prune --force

# Резервная копия
/opt/scripts/backup-all.sh

# Восстановление
/opt/scripts/restore-project.sh rent_django /opt/backups/rent_django_2026-04-27.sql.gz
```

## Troubleshooting

### Проект не стартует
```bash
cd /opt/project_name
docker compose logs   # смотреть ошибки
docker compose ps     # проверить статус
```

### Нет SSL сертификатов
```bash
# Проверить Traefik
docker logs traefik-traefik-1

# Проверить, что DNS работает
nslookup arenda.kapitan-trips.ru

# Проверить, что порты открыты
sudo ss -tlnp | grep 80
sudo ss -tlnp | grep 443
```

### Out of disk
```bash
docker system df
docker image prune -a --force
docker volume prune --force
```

### Контейнер крашится при перезагрузке
```bash
# Проверить лог с момента загрузки
docker compose logs --tail=100 service_name

# Проверить ресурсы
docker stats
```

## Monitoring и Maintenance

```bash
# Посмотреть использование ресурсов
docker stats

# Долгоживущие процессы
ps aux | grep docker

# Проверить сеть между контейнерами
docker exec rent_django-web-1 ping -c 1 redis
```

## Контакты

- Email: hvosdt@gmail.com
- Документация: [README.md](README.md)

---

**Версия:** 1.0  
**Дата:** 2026-04-27  
**Автор:** Dmitriy Kurilenko
