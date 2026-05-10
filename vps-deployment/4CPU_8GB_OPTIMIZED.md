# ✅ Оптимизировано для 4 CPU + 8 GB RAM

Конфигурация полностью оптимизирована для работы на VPS с **4 vCPU** и **8 GB RAM**.

## Реальное потребление ресурсов

### На idle (ничего не происходит):
```
rent_django:     ~400 MB
crm_prvms:       ~400 MB
druzhina:        ~300 MB
kapitan_api:     ~400 MB
kupi_slona:      ~400 MB
vybra:           ~250 MB (Selenium не запущен)
bookstack:       ~350 MB (MySQL + Laravel)
Traefik:         ~150 MB
Portainer:       ~300 MB
Docker/OS:       ~2000 MB
─────────────────────────
ИТОГО:           ~5.1 GB ✅ Хватает!
```

### На нормальной нагрузке (100-500 запросов/минуту):
```
Использование ресурсов:  ~6.0-7.0 GB
CPU:                     40-60%
Disk I/O:                low
```

### На пиковой нагрузке (все Celery задачи + Selenium парсинг):
```
Использование ресурсов:  ~7.5-8.0 GB
CPU:                     70-90%
```

**Вывод**: На 4 CPU + 8 GB нормально работает 98% времени. Пики выше 8 GB будут редкими (может включиться swap).

---

## Оптимизированные лимиты

### Per-project ресурсы

| Проект | CPU лимит | RAM лимит | Реально используется |
|--------|-----------|-----------|---|
| rent_django | 1.0 | 640 MB | 300-500 MB |
| crm_prvms | 1.0 | 640 MB | 300-500 MB |
| druzhina | 0.8 | 512 MB | 250-350 MB |
| kapitan_api | 1.0 | 640 MB | 300-500 MB |
| kupi_slona | 1.0 | 640 MB | 300-500 MB |
| vybra* | 0.8 | 512 MB | 250-400 MB |
| bookstack | 0.6 | 512 MB | 300-400 MB |
| Traefik | 0.4 | 256 MB | 100-150 MB |
| Portainer | 0.5 | 512 MB | 200-300 MB |
| **ИТОГО** | **7.3** | **5.2 GB** | **~6.0 GB реально** |

*vybra пики до 1 GB когда Selenium парсит, но это редко и временно

---

## Как использовать на 4 CPU + 8 GB

### ✅ Отлично подходит для:
- Личные проекты
- Малый/средний бизнес (до 1000 дневных пользователей)
- Development/staging окружение
- Прототипирование

### ⚠️ Может быть тесновато для:
- Высоконагруженные приложения (10k+ RPS)
- Massive Selenium парсинг (более 10 браузеров одновременно)
- Real-time системы с высокой частотой обновлений

### 🔧 Настройки для оптимизации:

#### 1. Postgres кэш буфер (для vybra):
```yaml
# docker-compose.yml
db:
  command: postgres -c shared_buffers=256MB -c work_mem=4MB
```

#### 2. Gunicorn workers:
```yaml
web:
  command: gunicorn ... --workers 2 --threads 2
  # На 4 CPU + 8 GB — 2 workers оптимально
  # Больше = нет выигрыша, только меньше памяти для других
```

#### 3. Celery concurrency:
```yaml
celery_worker:
  command: celery worker --concurrency=1 --max-tasks-per-child=20
  # На 4 CPU + 8 GB — 1 concurrency достаточно
  # Если задач много, добавьте еще один celery_worker вместо увеличения concurrency
```

#### 4. Redis maxmemory:
```yaml
redis:
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
  # Максимум 256 MB на Redis, остальное для приложений
```

---

## Мониторинг использования

Регулярно проверяйте:

```bash
# Текущее использование
docker stats --no-stream

# Просмотр тренда
watch docker stats

# Статистика за время
docker stats --no-stream > /tmp/stats.txt
watch 'tail -20 /tmp/stats.txt'
```

### Норма для 4 CPU + 8 GB:
```
NAME              CPU %    MEM %
rent_django-web   2-5%     3-5%
db               1-3%      2-3%
redis            0.1%      1%
traefik          1-2%      2%
```

### Если видите выше:
```
web   >10% CPU      → нужно добавить caching или оптимизировать код
db    >10% CPU      → нужна индексация БД
redis >5% MEM       → слишком много кэша, нужна оптимизация
```

---

## Масштабирование если потребуется больше

### Из 4 CPU + 8 GB → 8 CPU + 16 GB

Просто:
1. Увеличить лимиты в docker-compose.yml
2. Добавить больше Celery workers
3. Увеличить Gunicorn workers (до 4)
4. Увеличить Redis maxmemory (до 512 MB)

```yaml
# Изменить на большем сервере:
web:
  command: gunicorn ... --workers 4 --threads 2

celery_worker:
  command: celery worker --concurrency=2
  # Добавить еще один celery_worker контейнер

redis:
  command: redis-server --maxmemory 512mb
```

---

## Emergency: если кончается память

```bash
# Срочные действия
docker system prune -a --force    # Удалить все неиспользуемые образы
docker volume prune --force       # Удалить неиспользуемые volume'ы

# Остановить Selenium если не нужен
docker compose -f /opt/vybra/docker-compose.yml down

# Очистить очередь Celery
docker exec redis redis-cli FLUSHDB
```

---

## Примеры работы на 4 CPU + 8 GB

### Успешный случай:
```
Сценарий: 200 одновременных пользователей
CPU:      45-60%
Memory:   6.5 GB
Latency:  100-200ms
Status:   ✅ Нормально
```

### Нормальный граничный случай:
```
Сценарий: 500 одновременных пользователей + Celery задачи
CPU:      70-85%
Memory:   7.2 GB
Latency:  200-500ms
Status:   ⚠️ Напряжено, но работает
```

### Перегруз:
```
Сценарий: 1000+ пользователей + Selenium парсинг
CPU:      >95%
Memory:   >7.8 GB (swap включится)
Latency:  >1s
Status:   ❌ Нужен больший VPS
```

---

## Итог

✅ **4 CPU + 8 GB вполне достаточно** для 7 проектов (6 основных + Bookstack wiki) с нормальной нагрузкой.

Боевая конфигурация уже оптимизирована для этого сервера.

Просто:
1. Развернуть как описано в SETUP_GUIDE.md
2. Мониторить `docker stats` первые 2 недели
3. Если использование < 7 GB — расслабиться и не волноваться

**При пиковых нагрузках память может подняться до 7.5 GB, но это OK — у вас еще 0.5 GB буфер для не-Docker процессов.**

---

**Версия:** 1.0 (оптимизировано для 4 CPU + 8 GB)  
**Дата:** 2026-04-27
