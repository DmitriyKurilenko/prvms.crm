# ⚡ Quick Reference

Быстрый справочник для выполнения основных операций.

## Запуск всего

```bash
/opt/scripts/start-all.sh
# или
make start
```

## Остановка всего

```bash
/opt/scripts/stop-all.sh
# или
make stop
```

## Статус

```bash
/opt/scripts/status-all.sh
# или
make status
```

## Логи

```bash
# Конкретного сервиса (поиск по всем проектам)
/opt/scripts/logs-all.sh web

# Или прямо в проекте
cd /opt/rent_django
docker compose logs -f web

# Ошибки
docker compose logs | grep ERROR
```

## Deploy (обновить проект)

```bash
# Все проекты
/opt/scripts/deploy-all.sh

# Один проект
cd /opt/rent_django
git pull origin main
docker compose down
docker compose up -d --build
```

## Backup

```bash
# Backup всех БД
/opt/scripts/backup-all.sh

# Все backup'ы
ls -lh /opt/backups/
```

## Restore (восстановить из backup)

```bash
/opt/scripts/restore-project.sh rent_django /opt/backups/rent_django_2026-04-27.sql.gz
```

## Ресурсы

```bash
# Текущее использование
docker stats

# Место на диске
docker system df
df -h /opt

# Память
free -h

# Процессы
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
```

## Доступ

```bash
# Traefik Dashboard
http://YOUR_VPS_IP:8080

# Portainer (управление контейнерами)
https://YOUR_VPS_IP:9443

# Проекты
https://arenda.kapitan-trips.ru
https://crm.prvms.ru
https://druzhina.prvms.ru
https://kapitan.prvms.ru
https://slon.prvms.ru
https://vybra.prvms.ru
https://docs.kapitan-trips.ru (вики)
```

## Очистка

```bash
# Удалить неиспользуемые образы
docker image prune -a --force

# Удалить неиспользуемые volume'ы
docker volume prune --force

# Очистить всё
docker system prune -a --force
```

## Перезагрузка контейнера

```bash
cd /opt/rent_django
docker compose restart web          # Перезагрузить web
docker compose restart              # Перезагрузить все
```

## Внутрь контейнера

```bash
# Входить в контейнер
docker compose exec web bash
docker compose exec web python manage.py shell

# Выполнить команду
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Проверка БД

```bash
cd /opt/rent_django

# Войти в psql
docker compose exec db psql -U boat_user -d boat_rental

# SQL команды
SELECT * FROM users;
```

## Проверка Redis

```bash
cd /opt/rent_django

# Войти в redis-cli
docker compose exec redis redis-cli -a PASSWORD

# Команды
KEYS *
GET key_name
```

## Firewall

```bash
# Проверить открытые порты
sudo ss -tlnp | grep LISTEN

# Должны быть открыты
:80    - HTTP
:443   - HTTPS
:8080  - Traefik dashboard
:9443  - Portainer
```

## SSH

```bash
# Подключиться с ключом
ssh -i ~/.ssh/vps-key root@your-vps-ip

# Или используя config
ssh vps
```

## Полезные команды Docker

```bash
# Все контейнеры
docker ps -a

# Все сети
docker network ls

# Все volume'ы
docker volume ls

# Детали контейнера
docker inspect container_name

# Детали сети
docker network inspect proxy

# Топ процессов
docker top container_name

# Статистика
docker stats container_name

# История образов
docker image history rent_django-web
```

## Сервисы Swarm

```bash
# Все сервисы
docker service ls

# Детали сервиса
docker service inspect service_name

# Логи сервиса
docker service logs service_name

# Масштабирование
docker service scale service_name=3
```

## Проблемы

```bash
# Контейнер не стартует
docker compose logs    # смотреть ошибку

# Нет сетевого доступа
docker exec container ping redis

# Проверить сеть
docker network inspect backend

# Проверить переменные окружения
docker inspect container_name | grep -A 20 Env

# Проверить volume'ы
docker inspect container_name | grep -A 10 Mounts
```

## Обновление Docker

```bash
# Проверить версию
docker --version

# Обновить (если используется script install)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Перезагрузить daemon
sudo systemctl restart docker

# Все контейнеры должны перезагрузиться автоматически
```

## Systemd

```bash
# Статус автозагрузки
sudo systemctl status docker-swarm-services

# Логи
sudo journalctl -u docker-swarm-services -f

# Таймеры
sudo systemctl list-timers

# Статус backup timer
sudo systemctl status docker-backup.timer
```

## Makefile (удобно)

```bash
cd /opt
make help           # Все команды
make start          # Запустить все
make stop           # Остановить все
make restart        # Перезагрузить все
make status         # Статус
make logs SERVICE=web   # Логи web сервиса
make deploy         # Git pull + rebuild
make backup         # Backup БД
make clean          # Удалить старые образы
```

## Файловая система

```bash
# Размер директорий
du -sh /opt/*

# Логи проектов
ls -lh /opt/*/logs/

# Backup'ы
ls -lh /opt/backups/

# Docker данные
docker system df -v | head -20
```

## Мониторинг в реальном времени

```bash
# Terminal 1: логи Traefik
tail -f /opt/traefik/logs/access.log

# Terminal 2: статистика Docker
watch docker stats

# Terminal 3: место на диске
watch df -h
```

---

**Версия:** 1.0  
**Дата:** 2026-04-27
