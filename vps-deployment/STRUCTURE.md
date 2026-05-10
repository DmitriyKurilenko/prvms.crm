# 📦 VPS Deployment - Структура проекта

Полная боевая конфигурация для запуска 6 проектов на одном VPS с Docker Swarm + Traefik + Portainer.

## Структура файлов

```
vps-deployment/
├── README.md                        # Основная документация
├── SETUP_GUIDE.md                   # Пошаговое руководство установки
├── DEPLOYMENT_CHECKLIST.md          # Чеклист перед production
├── STRUCTURE.md                     # Этот файл
├── 4CPU_8GB_OPTIMIZED.md            # Оптимизация для скромных VPS
├── REQUIREMENTS.md                  # Детальные требования
├── Makefile                         # Удобные команды (make start/stop/status)
│
├── traefik/
│   ├── docker-compose.yml           # Traefik (reverse proxy + SSL)
│   ├── letsencrypt/                 # Let's Encrypt сертификаты
│   └── logs/                        # Traefik логи
│
├── portainer/
│   └── docker-compose.yml           # Portainer (Web UI для Docker)
│
├── rent_django/                     # Проект #1 - Лодки
│   ├── docker-compose.yml           # Compose файл (DB, Redis, Web, Celery)
│   ├── .env.example                 # Шаблон переменных окружения
│   └── [исходный код проекта]       # Скопировать из репозитория
│
├── crm_prvms/                       # Проект #2 - CRM
│   ├── docker-compose.yml
│   ├── .env.prod.example
│   └── [исходный код проекта]
│
├── druzhina/                        # Проект #3 - Druzhina (PostGIS)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── [исходный код проекта]
│
├── kapitan_api/                     # Проект #4 - Капитан API
│   ├── docker-compose.yml
│   ├── .env.example
│   └── [исходный код проекта]
│
├── kupi_slona/                      # Проект #5 - Купи Слона
│   ├── docker-compose.yml
│   ├── .env.example
│   └── [исходный код проекта]
│
├── vybra/                           # Проект #6 - Vybra (парсинг)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── [исходный код проекта]
│
├── bookstack/                       # Проект #7 - Wiki (open-source)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── README.md
│
├── scripts/
│   ├── init-server.sh               # Полная первичная настройка сервера
│   ├── start-all.sh                 # Запустить все проекты
│   ├── stop-all.sh                  # Остановить все проекты
│   ├── status-all.sh                # Статус всех проектов
│   ├── check-https.sh               # Диагностика HTTPS/DNS/Traefik
│   ├── logs-all.sh                  # Логи сервисов
│   ├── deploy-all.sh                # Git pull + rebuild для всех
│   ├── backup-all.sh                # Backup всех БД
│   └── restore-project.sh           # Восстановить из backup
│
├── systemd/
│   ├── docker-swarm-services.service   # Автозагрузка всех сервисов
│   ├── docker-swarm-services.timer     # (опционально)
│   ├── docker-backup.service           # Автоматический backup
│   └── docker-backup.timer             # Расписание backup
│
└── backups/                         # Директория для backup'ов БД
    └── (автоматически создаётся)
```

## Быстрый старт

### 1. На локальной машине подготовить конфиги:

```bash
# Скопировать этот репозиторий на VPS
scp -r vps-deployment/ your-vps:/opt/

# Или клонировать через git
ssh your-vps
cd /opt
git clone https://github.com/yourrepo/vps-deployment.git .
```

### 2. На VPS выполнить setup:

```bash
ssh your-vps
cd /opt

# Читать документацию
cat SETUP_GUIDE.md

# Следовать инструкциям (13 шагов):
# 1. Установить Docker
# 2. Инициализировать Swarm
# 3. Создать proxy сеть
# 4. Запустить Traefik
# 5. Запустить Portainer
# 6. Загрузить исходные коды проектов
# 7. Создать .env файлы для 6 основных проектов
# 8. Запустить основные проекты
# 9. (опционально) Запустить Bookstack wiki
```

### 3. Запустить все:

```bash
/opt/scripts/start-all.sh

# Проверить HTTPS/DNS/Traefik
/opt/scripts/check-https.sh

# Или
make start
```

## Содержимое 6 основных проектов + Bookstack

### 6 собственных проектов (rent_django, crm_prvms и т.д.)

Каждый содержит:

### docker-compose.yml
```yaml
services:
  db:              # PostgreSQL (или другая БД)
  redis:           # Redis кэш/Celery broker
  web:             # Django/FastAPI приложение
  celery:          # Celery worker (опционально)
  celery-beat:     # Celery scheduler (опционально)
  selenium:        # Selenium для парсинга (только для vybra)

networks:
  backend:         # Внутренняя сеть для БД и кэша
  proxy:           # Внешняя сеть (подключается к Traefik)
```

### .env файл
Содержит все переменные окружения:
- Database credentials
- Redis password
- Django SECRET_KEY
- S3/file storage credentials
- Email configuration
- API keys и т.д.

### Dockerfile
Содержит инструкции для построения образа приложения.

### Bookstack (7-й проект — open-source вики)

Специальный случай (не требует исходного кода):

```yaml
services:
  db:        # MySQL (автоматически настраивается)
  bookstack: # Готовый образ от linuxserver/bookstack
```

Достаточно только:
- docker-compose.yml
- .env файл
- Никакого исходного кода не нужно!

## Как это работает

```
Интернет
   ↓ (80, 443)
┌─────────────────────────────┐
│      Traefik                │  ← Reverse proxy + SSL termination
│  (автоматический routing)   │
└──────────────┬──────────────┘
               │ (внутренняя сеть "proxy")
       ┌───────┴────────┬──────────────┬────────────────┐
       ↓                ↓              ↓                ↓
  ┌────────┐       ┌────────┐    ┌─────────┐      ┌───────┐
  │ rent   │       │ crm    │    │druzhina │ ...  │vybra  │
  │ (8000) │       │(8000)  │    │ (8080)  │      │(8000) │
  └──┬─────┘       └──┬─────┘    └────┬────┘      └───┬───┘
     │                │              │                │
  ┌──┴────────────────┴──────────────┴────────────────┴──┐
  │  docker network "proxy" (overlay)                    │
  └──────────────────────────────────────────────────────┘
     │
  ┌──┴──────────────────────────────────────────────────┐
  │  каждый проект имеет свою внутреннюю сеть "backend" │
  │                                                      │
  │  ┌────────────────────────────────────────────────┐  │
  │  │  rent_django                                   │  │
  │  │  ├── PostgreSQL (5432)                         │  │
  │  │  ├── Redis (6379)                              │  │
  │  │  ├── Web app (8000)                            │  │
  │  │  ├── Celery worker                             │  │
  │  │  └── Celery beat                               │  │
  │  └────────────────────────────────────────────────┘  │
  │                                                      │
  │  ┌────────────────────────────────────────────────┐  │
  │  │  crm_prvms                                     │  │
  │  │  ├── PostgreSQL (5432)                         │  │
  │  │  ├── Redis (6379)                              │  │
  │  │  ├── Web app (8000)                            │  │
  │  │  └── Celery                                    │  │
  │  └────────────────────────────────────────────────┘  │
  │                                                      │
  │  [аналогично для остальных 4 проектов]             │
  │                                                      │
  └──────────────────────────────────────────────────────┘
```

## Resource limits

Каждый контейнер имеет лимиты на ресурсы:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'      # Максимум 0.5 CPU
      memory: 512M     # Максимум 512 MB памяти
    reservations:
      cpus: '0.1'      # Гарантированно 0.1 CPU
      memory: 128M     # Гарантированно 128 MB
```

Это предотвращает одному контейнеру захватить все ресурсы VPS.

## Основные команды

```bash
# Сразу все сервисы
make start                    # Запустить все
make stop                     # Остановить все
make status                   # Статус всех
make deploy                   # Git pull + rebuild всех
make backup                   # Backup всех БД
make logs SERVICE=web         # Логи сервиса

# Отдельный проект
cd /opt/rent_django
docker compose logs -f web    # Follow logs
docker compose restart        # Перезагрузить
docker compose down           # Остановить
docker compose up -d --build  # Стартовать с перестроением

# Управление сервисами
docker service ls             # Все сервисы Swarm
docker ps                     # Все контейнеры
docker logs container_name    # Логи контейнера
```

## Дополнительно

### Traefik Dashboard
- URL: http://YOUR_VPS_IP:8080
- Показывает все routes, backends, сертификаты

### Portainer Web UI
- URL: https://YOUR_VPS_IP:9443
- Управление контейнерами, сетями, volume'ами через web

### Logs
- Traefik: `/opt/traefik/logs/access.log`
- Docker logs: `docker logs <container>`
- Project logs: `/opt/<project>/logs/` (если настроено)

### Monitoring
```bash
# Использование ресурсов в реальном времени
docker stats

# Информация о диске
docker system df

# Подробная информация о контейнере
docker inspect container_name
```

## Файлы которые нужно отредактировать

1. **Все `.env` файлы**
   - Заменить CHANGE_ME на реальные значения
   - Установить сильные пароли (32+ символов)

2. **Traefik labels** (если меняются домены)
   - В каждом docker-compose.yml проекта
   - Поле `traefik.http.routers.*.rule=Host(...)`

3. **Email для Let's Encrypt**
   - В `/opt/traefik/docker-compose.yml`
   - `--certificatesresolvers.le.acme.email=YOUR_EMAIL`

4. **Исходные коды проектов**
   - Скопировать/клонировать в соответствующие папки
   - Убедитесь что Dockerfile присутствует

## Troubleshooting

### Контейнер не стартует
```bash
cd /opt/project_name
docker compose logs   # смотреть ошибки
```

### Нет SSL сертификатов
```bash
docker logs traefik-traefik-1 | grep -i "certificate\|acme"
```

### Out of disk space
```bash
docker system df
docker image prune -a --force
docker volume prune --force
```

### Проекты не коммуницируют
```bash
docker exec container_name ping redis    # проверить сеть
docker network inspect proxy             # детали сети
```

## Архитектурные решения

### Почему Docker Swarm?
- Встроен в Docker (не нужен отдельный кластер)
- Простой в управлении (только 1 машина)
- Достаточно мощный для 6 проектов
- Меньше resource overhead чем Kubernetes

### Почему Traefik вместо Nginx?
- Автоматический routing по Docker labels
- Автоматический SSL через Let's Encrypt
- Горячая перезагрузка без downtime
- Dashboard для мониторинга

### Почему overlay сеть для Traefik?
- Позволяет Traefik общаться со всеми контейнерами
- Изолирует backend сети каждого проекта
- Масштабируется если добавить больше машин

## Production best practices

✅ Используется в конфиге:
- Resource limits для всех контейнеров
- Health checks для автоматического перезагрузки
- Изолированные сети (backend/proxy)
- Автоматические резервные копии
- SSL/HTTPS для всех сайтов
- Слои безопасности (firewall, изоляция)

❌ Не используется (добавить если нужно):
- Kubernetes (оverkill для 1 машины)
- Distributed logging (ELK stack)
- Distributed monitoring (Prometheus)
- Automatic failover (нужны 2+ машины)
- Advanced security (WAF, DDoS protection)

## Лицензия и контакты

- Email: hvosdt@gmail.com
- Created: 2026-04-27
- Version: 1.0 (Docker Swarm + Traefik + Portainer)
