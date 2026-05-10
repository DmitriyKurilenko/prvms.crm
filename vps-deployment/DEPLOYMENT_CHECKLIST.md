# ✅ Production Deployment Checklist

Используйте этот чеклист для убедитесь что всё правильно настроено перед запуском на production.

**Внимание:** Конфигурация оптимизирована для **4 CPU + 8 GB RAM**.  
Детали см. в [4CPU_8GB_OPTIMIZED.md](4CPU_8GB_OPTIMIZED.md)

## 📋 Подготовка VPS

- [ ] VPS с Ubuntu 22.04+ LTS
- [ ] Минимум 12 vCPU, 16 GB RAM, 200+ GB SSD
- [ ] SSH доступ настроен (по ключам, не по паролю)
- [ ] Sudo доступ без пароля для деплоя
- [ ] Firewall отключен или открыты порты 80, 443

```bash
# Проверить требования
uname -a
nproc
free -h
df -h
```

## 🐳 Docker & Docker Swarm

- [ ] Docker 24.0+ установлен
- [ ] Docker Daemon запущен
- [ ] Docker Swarm инициализирован (`docker swarm init`)
- [ ] Proxy сеть создана (`docker network create -d overlay --attachable proxy`)
- [ ] Текущий пользователь в группе docker

```bash
docker --version
docker compose version
docker node ls
docker network ls | grep proxy
```

## 📁 Структура директорий

- [ ] `/opt/` создана и доступна
- [ ] Все docker-compose.yml файлы на месте
- [ ] Скрипты в `/opt/scripts/` имеют права на выполнение
- [ ] Logs директория создана: `mkdir -p /opt/*/logs`

```bash
chmod +x /opt/scripts/*.sh
ls -la /opt/*/docker-compose.yml
```

## 🔐 DNS & SSL

- [ ] Все домены указывают на IP VPS
- [ ] DNS записи распространились (проверить `nslookup`)

```bash
for domain in rent crm druzhina kapitan slon vybra; do
  echo "Checking ${domain}.prvms.ru..."
  nslookup ${domain}.prvms.ru
done
```

- [ ] Let's Encrypt email установлен в Traefik (hvosdt@gmail.com)
- [ ] Сертификаты автоматически обновляются

## 🚀 Traefik (Reverse Proxy)

- [ ] Traefik docker-compose.yml создан
- [ ] Traefik стартанул: `cd /opt/traefik && docker compose up -d`
- [ ] Traefik dashboard доступен: http://YOUR_VPS_IP:8080
- [ ] Логи Traefik не содержат ошибок

```bash
docker compose logs traefik | grep -i error
```

## 📊 Portainer (Web UI)

- [ ] Portainer docker-compose.yml создан
- [ ] Portainer стартанул: `cd /opt/portainer && docker compose up -d`
- [ ] Портал доступен: https://YOUR_VPS_IP:9443
- [ ] Админ пароль установлен

## 🏗️ Проекты: rent_django

- [ ] Исходный код склонирован/скопирован в `/opt/rent_django`
- [ ] .env файл создан из `.env.example`
- [ ] Все переменные в .env заполнены (SECRET_KEY, DB_PASSWORD, S3 credentials)
- [ ] Dockerfile есть в корне проекта
- [ ] `docker compose up -d` успешно запущен

```bash
cd /opt/rent_django
docker compose ps
docker compose logs web | head -50
```

- [ ] Web сервис здоров (healthcheck проходит)
- [ ] PostgreSQL миграции выполнены
- [ ] Redis работает
- [ ] Celery worker работает
- [ ] Celery beat работает

## 🏗️ Проекты: crm_prvms

- [ ] Исходный код в `/opt/crm_prvms`
- [ ] `.env.prod` файл создан и заполнен
- [ ] `docker compose up -d` успешно запущен
- [ ] Все сервисы здоровы

```bash
cd /opt/crm_prvms
docker compose ps
```

## 🏗️ Проекты: остальные (druzhina, kapitan_api, kupi_slona, vybra)

Для каждого проекта:

- [ ] Исходный код загружен
- [ ] .env файл создан и заполнен
- [ ] `docker compose up -d` успешно запущен
- [ ] `docker compose ps` показывает healthy сервисы

```bash
for project in druzhina kapitan_api kupi_slona vybra; do
  echo "Checking $project..."
  cd /opt/$project
  docker compose ps
done
```

## 🌐 Доступность проектов

Проверить, что все проекты доступны через HTTPS:

```bash
# Может потребоваться добавить /etc/hosts локально для тестирования
# Или использовать curl с Host header:
curl -H "Host: arenda.kapitan-trips.ru" https://YOUR_VPS_IP/
curl -H "Host: crm.prvms.ru" https://YOUR_VPS_IP/
# и т.д.
```

- [ ] https://arenda.kapitan-trips.ru доступен (302 redirect на правильный URL)
- [ ] https://crm.prvms.ru доступен
- [ ] https://druzhina.prvms.ru доступен
- [ ] https://kapitan.prvms.ru доступен
- [ ] https://slon.prvms.ru доступен
- [ ] https://vybra.prvms.ru доступен

## 🔐 HTTPS & сертификаты

- [ ] Все сайты работают на HTTPS
- [ ] Сертификаты валидные (проверить в браузере)
- [ ] HSTS headers установлены

```bash
curl -I https://arenda.kapitan-trips.ru 2>/dev/null | grep -i "strict\|security"
```

- [ ] Редирект HTTP → HTTPS работает

```bash
curl -L http://arenda.kapitan-trips.ru 2>&1 | grep -i "location\|strict"
```

## 📊 Мониторинг & логирование

- [ ] Traefik логирует запросы: `/opt/traefik/logs/access.log`
- [ ] Docker логи accessible: `docker logs container_name`
- [ ] Логи не содержат критических ошибок

```bash
# Проверить логи всех контейнеров
docker compose logs --tail=20 | grep -i "error\|exception" || echo "No errors found"
```

## 💾 Резервные копии

- [ ] Backup скрипт готов: `/opt/scripts/backup-all.sh`
- [ ] Запустить ручной backup: `/opt/scripts/backup-all.sh`
- [ ] Бэкапы созданы в `/opt/backups/`

```bash
ls -lh /opt/backups/
```

- [ ] systemd timer настроен для автоматических бэкапов

```bash
sudo systemctl status docker-backup.timer
sudo systemctl list-timers | grep backup
```

## 🔄 Автозагрузка

- [ ] systemd units скопированы в `/etc/systemd/system/`
- [ ] systemd daemon перезагружен: `sudo systemctl daemon-reload`
- [ ] Services включены на автозагрузку

```bash
sudo systemctl enable docker-swarm-services.service
sudo systemctl is-enabled docker-swarm-services.service
```

## 🧪 Функциональное тестирование

### rent_django

- [ ] Главная страница загружается
- [ ] Авторизация работает
- [ ] Создание лодки работает
- [ ] Поиск работает
- [ ] Celery задачи выполняются

### crm_prvms

- [ ] Dashboard загружается
- [ ] CRUD операции работают
- [ ] Celery задачи выполняются
- [ ] API endpoints отвечают

### Остальные проекты

- [ ] Основной функционал работает
- [ ] Нет критических ошибок в логах
- [ ] Производительность приемлемая

## ⚡ Performance & Resources

```bash
# Проверить использование ресурсов
docker stats

# Проверить оставшееся место на диске
df -h

# Проверить использование памяти
free -h
```

- [ ] CPU использование < 80%
- [ ] RAM использование < 80%
- [ ] Disk использование < 80%
- [ ] Нет OOM (Out of Memory) ошибок

## 🛡️ Security

- [ ] Firewall открыты только нужные порты (80, 443)
- [ ] SSH доступ по ключам (не по паролю)
- [ ] sudo без пароля только для конкретных команд (если нужно)
- [ ] Все пароли в .env файлах сильные (32+ символов)
- [ ] .env файлы в .gitignore

```bash
grep ".*_PASSWORD.*" /opt/*/.env | head -5  # Проверить что пароли есть
```

- [ ] Нет секретов в исходном коде
- [ ] CORS правильно настроен (если API)
- [ ] Database не доступна с интернета

```bash
sudo ss -tlnp | grep 5432  # PostgreSQL не должен слушать 0.0.0.0
```

## 📝 Документация

- [ ] README.md скопирован на VPS: `/opt/README.md`
- [ ] SETUP_GUIDE.md скопирован: `/opt/SETUP_GUIDE.md`
- [ ] Все команды документированы в Makefile

```bash
make help
```

## 🎯 Финальная проверка

```bash
# Запустить все скрипты проверки
/opt/scripts/start-all.sh
sleep 30
/opt/scripts/status-all.sh
```

- [ ] Все сервисы `Up`
- [ ] Нет `Restarting` контейнеров
- [ ] Healthchecks проходят

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

- [ ] Все проекты доступны через HTTPS
- [ ] Нет ошибок в логах

```bash
for container in $(docker ps -q); do
  echo "Checking $(docker inspect -f '{{.Name}}' $container)..."
  docker logs $container 2>&1 | tail -3
done
```

## 🚀 Ready for Production!

Если все пункты отмечены - развертывание завершено! 🎉

---

## Постоянное обслуживание

После развертывания регулярно проверяйте:

- [ ] Еженедельно: `make status`
- [ ] Еженедельно: проверить логи на ошибки
- [ ] Ежемесячно: проверить место на диске (`df -h`)
- [ ] Ежемесячно: проверить обновления Docker
- [ ] Ежемесячно: тестировать restore из backup

```bash
# Добавить в crontab
0 9 * * 1 /opt/scripts/status-all.sh > /tmp/status.log 2>&1  # Каждый понедельник в 9 AM
```

---

**Дата создания:** 2026-04-27  
**Версия:** 1.0
