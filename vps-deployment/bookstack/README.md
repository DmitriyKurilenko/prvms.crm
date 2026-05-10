# 📚 Bookstack Wiki

Bookstack - это красивое, простое и мощное open-source вики приложение. Написано на Laravel.

## Быстрый старт

### 1. Подготовить

```bash
cd /opt/bookstack
cp .env.example .env
nano .env  # Отредактировать переменные
```

### 2. Сгенерировать APP_KEY и запустить

```bash
# Разово сгенерировать ключ (вставить в BOOKSTACK_APP_KEY в .env)
docker run --rm --entrypoint /bin/bash lscr.io/linuxserver/bookstack:latest appkey
```

### 3. Запустить

```bash
docker compose up -d
```

### 4. Доступ

- URL: https://docs.kapitan-trips.ru
- Дефолтный пользователь: admin@admin.com
- Дефолтный пароль: password

**⚠️ Срочно смените пароль после первого входа!**

### 5. Конфигурация

Первый вход:
1. Авторизоваться с admin@example.com / password
2. Перейти в Settings → Users
3. Изменить пароль администратора
4. Удалить demo пользователя если не нужен

---

## Использование

### Создание вики

1. Settings → Books
2. Нажать "Create New Book"
3. Добавить главы (Chapters) и страницы (Pages)

### Поиск

Полнотекстовый поиск на главной странице.

### Резервная копия

```bash
# Backup БД
docker compose exec -T db mysqldump -u bookstack -p${MYSQL_PASSWORD} bookstack | gzip > /opt/backups/bookstack_$(date +%Y-%m-%d).sql.gz

# Backup данных
tar czf /opt/backups/bookstack_data_$(date +%Y-%m-%d).tar.gz /opt/bookstack/

# Или использовать общий скрипт
/opt/scripts/backup-all.sh
```

### Восстановление

```bash
# Из backup'а
gunzip < /opt/backups/bookstack_2026-04-27.sql.gz | docker compose exec -T db mysql -u bookstack -p${MYSQL_PASSWORD} bookstack
```

---

## Особенности

✅ Встроено в конфигурацию:
- Автоматический SSL через Traefik
- Resource limits (не будет жрать память)
- Автоматические backup'ы БД
- Health checks с перезагрузкой
- Изолированная сеть

---

## Логи

```bash
cd /opt/bookstack
docker compose logs -f bookstack
```

---

## Обновление

```bash
cd /opt/bookstack
docker compose pull
docker compose up -d
```

---

## Команды управления

```bash
# Перезагрузить
docker compose restart

# Остановить
docker compose down

# Статус
docker compose ps

# Войти в контейнер
docker compose exec bookstack bash

# PHP Artisan команды
docker compose exec bookstack php artisan list
```

---

## Интеграция с другими проектами

### Создание пользователей LDAP/SSO

Если у вас есть LDAP сервер:

```bash
# Отредактировать .env
MAIL_HOST=ldap.example.com
# ... и т.д.

docker compose restart
```

---

## Troubleshooting

### Не могу залогиниться
```bash
# Проверить логи
docker compose logs bookstack | grep -i error

# Сбросить пароль (если забыли)
docker compose exec bookstack php artisan tinker
>>> $user = \BookStack\Auth\User::find(1);
>>> $user->forceFill(['password' => bcrypt('newpassword')])->save();
>>> exit
```

### БД не подключается
```bash
docker compose logs db
# Проверить .env переменные
cat .env | grep MYSQL
```

### Медленно работает
```bash
docker stats bookstack
# Если использует > 384 MB, увеличить лимит в docker-compose.yml
```

---

## Ресурсы

- MySQL: ~256 MB
- Bookstack: ~384 MB
- **Итого: ~640 MB**

На 4 CPU + 8 GB это ~8% памяти — совсем не напрягает.

---

## Дополнительные функции

### Темы и плагины

Bookstack поддерживает:
- Кастомные темы (CSS)
- Custom JS
- API для интеграции

### API

```bash
# Получить токен из Settings
# Затем использовать

curl -X GET "https://bookstack.prvms.ru/api/books" \
  -H "Authorization: Token $TOKEN"
```

---

## Документация

- Официальная: https://www.bookstackapp.com/docs/
- GitHub: https://github.com/BookStackApp/BookStack

---

**Версия:** 1.0  
**Дата:** 2026-04-27
