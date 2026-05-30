# План реализации: канал ВКонтакте

**Статус:** план согласован, реализация не начата
**Дата составления:** 2026-05-30
**Связанные документы:** DECISIONS.md (будет добавлен DEC-038), DEV_LOG.md, RELEASE_NOTES.md

---

## 1. Что должно получиться (бизнес-результат)

Пользователь подключает к своей CRM сообщество ВКонтакте одной кнопкой и сразу начинает получать личные сообщения от клиентов в раздел «Чаты», а каждое новое обращение автоматически становится сделкой (если включён `auto_create_lead`). Ответы оператора из CRM уходят клиенту в ВК.

Внешне новый канал ведёт себя точно так же, как существующие Telegram/MAX/WhatsApp:
- Появляется в списке мессенджер-каналов
- Имеет статус «Активен / Ошибка / Отключён»
- Сообщения попадают в `ChatSession` + `MessageLog`
- Создание сделки идёт через тот же путь, что и у других мессенджеров
- Real-time уведомления через WebSocket работают без изменений

Канал работает **только с личными сообщениями сообществу**. Комментарии под постами, лайки, лид-формы, упоминания — игнорируются (DEC-038, принципиальное ограничение области).

---

## 2. Пользовательский сценарий

### 2.1 Подключение (первый раз)

1. Пользователь заходит в **Настройки → Мессенджеры**.
2. Видит кнопку **«Подключить ВКонтакте»** рядом с другими типами каналов.
3. Жмёт кнопку.
4. Браузер уходит на сайт vk.com на стандартный экран согласия ВКонтакте:
   > Приложение **PRVMS CRM** запрашивает доступ к управлению сообществами.
   > Выберите сообщество, для которого предоставить доступ.
   > [список сообществ, которыми пользователь администрирует]
5. Пользователь отмечает одно или несколько сообществ, жмёт «Разрешить».
6. ВКонтакте редиректит браузер на `https://наш-домен/oauth/vk/callback`.
7. Наш фронтенд показывает спиннер «Подключаем ВКонтакте…», параллельно завершает настройку на бэкенде.
8. Через 1-3 секунды — экран «Подключено N сообществ» с кнопкой «Перейти к мессенджерам».
9. На странице мессенджеров новые каналы видны как обычные строки списка с названием сообщества и аватаркой, статус «Активен».

### 2.2 Получение входящих

- Клиент пишет в ВК сообществу — сообщение мгновенно появляется в разделе «Чаты» CRM
- Если канал настроен с `auto_create_lead=true` — автоматически создаётся сделка в указанной воронке/стадии (та же логика, что и для Telegram/MAX, см. `apps/channels/tasks.py:_auto_create_lead`)
- Оператор отвечает в CRM — ответ доставляется клиенту в ВК

### 2.3 Удаление канала

- Пользователь нажимает «Удалить» на строке канала
- На бэкенде: вызываем VK API `groups.deleteCallbackServer`, удаляем запись `MessengerChannel`
- Если вызов к ВК упал (например, токен отозван) — всё равно удаляем запись локально, но логируем ошибку

### 2.4 Что пользователь НЕ видит и НЕ настраивает руками

- ID приложения ВКонтакте
- Access token сообщества
- ID сообщества (group_id)
- URL вебхука
- Код подтверждения (confirmation code)
- Секретный ключ
- Тип события (`message_new`)

Всё это создаётся и сохраняется автоматически.

---

## 3. Разовая настройка платформы (делается один раз владельцем)

Это не часть кодовой задачи — это инструкция администратору платформы. Должна быть задокументирована в `docs/user-guide/admin/vk-app-setup.md` (новая статья) и в комментарии к `.env.example`.

### Шаги:

1. Зайти на https://vk.com/dev → «Мои приложения» → «Создать приложение».
2. Тип: **Standalone-приложение** (важно — именно standalone, а не веб-сайт, чтобы не требовался client_secret).
3. Название: `PRVMS CRM`, описание произвольное.
4. После создания зайти в **Настройки** приложения:
   - **Доверенные redirect URI**: добавить `https://наш-домен/oauth/vk/callback`
   - **Состояние приложения**: «Приложение включено и видно всем»
5. Скопировать **ID приложения** (число в верхней части настроек).
6. Положить ID в `.env`:
   ```
   VK_APP_ID=12345678
   ```
7. В `.env.example` оставить плейсхолдер и комментарий с этими шагами.
8. Перезапустить backend-контейнеры.

### Почему Standalone, а не «веб-сайт»

ВКонтакте для управления сообществом требует токен сообщества (community access token). Получить его можно только через так называемый Implicit Flow — токен возвращается прямо в браузер в адресной строке после знака `#`. Этот режим работает только со Standalone-приложениями и не требует никаких серверных секретов: безопасность держится на привязке к доверенному redirect URI, который указан в настройках приложения. Никаких `client_secret` хранить не нужно. Это упрощает multi-tenant эксплуатацию: одно приложение PRVMS обслуживает все тенанты.

---

## 4. Архитектурные решения и обоснования

### 4.1 Почему OAuth через фронтенд, а не через бэкенд

У amoCRM и Битрикс24 (`apps/integrations/oauth_api.py:46`) используется классическая схема Authorization Code Flow: бэкенд получает `code` через GET-параметр callback'а и обменивает его на токен через серверный вызов. Это безопасно и стандартно.

С ВКонтакте так не получится. Для community access token (необходимого для отправки сообщений от лица сообщества) ВК поддерживает только Implicit Flow: токен возвращается во **фрагменте URL** (после `#`), а фрагмент браузер на сервер не передаёт — его видит только JavaScript на странице.

Поэтому схема такая:
- **`/api/channels/oauth/vk/start/`** (бэкенд) — собирает authorize URL с подписанной меткой (state), отдаёт фронтенду адрес для редиректа.
- **`/oauth/vk/callback`** (фронтенд-роут, не SPA-страница приложения) — после возврата ВК читает `window.location.hash`, парсит токены, отправляет на бэкенд.
- **`/api/channels/oauth/vk/complete/`** (бэкенд) — принимает токены + state, валидирует метку, создаёт `MessengerChannel`-записи, регистрирует webhook через VK API.

Метка (state) — подписанная Django `signing.dumps` структура с `{tenant_id, user_id, nonce}`, TTL 1 час. Это защита от того, чтобы чужой человек не подсунул чужие токены в нашу систему.

### 4.2 Авторегистрация webhook'а

Сразу после `/complete/` для каждого подключённого сообщества вызываем три метода ВК API подряд:

1. `groups.getCallbackConfirmationCode(group_id=...)` → строка-код подтверждения. Сохраняем в `credentials.confirmation_code`.
2. `groups.addCallbackServer(group_id=..., url=..., title=PRVMS CRM, secret_key=...)` → числовой `server_id`. Сохраняем в `credentials.server_id`. `secret_key` генерируем сами (`secrets.token_urlsafe(32)`), сохраняем в `credentials.secret_key`.
3. `groups.setCallbackSettings(group_id=..., server_id=..., message_new=1, api_version='5.199')` → активируем нужный тип событий. Только `message_new` — больше ничего не включаем.

Если любой из этих вызовов упал — создание канала откатывается (записи в БД нет, токен в VK не висит зарегистрированным, но это не страшно — он истекает или будет перерегистрирован при повторе).

### 4.3 Обработка входящих

Когда ВКонтакте присылает событие на наш webhook, тело имеет такую форму:

```json
{
  "type": "message_new",
  "object": {
    "message": {
      "from_id": 12345,
      "peer_id": 12345,
      "text": "Привет",
      "id": 67890,
      "date": 1234567890,
      "attachments": [...]
    },
    "client_info": {...}
  },
  "group_id": 222222222,
  "secret": "наш-секрет"
}
```

Особый случай — самый первый запрос от ВК после регистрации webhook'а:

```json
{
  "type": "confirmation",
  "group_id": 222222222
}
```

На него надо ответить **plain-text строкой** — той самой confirmation_code, которую мы получили на шаге 1 и сохранили в `credentials`. Если не ответить или ответить чем-то другим — ВК пометит сервер как неподтверждённый и не будет слать события.

### 4.4 Отправка исходящих

Метод ВК: `messages.send` с параметрами `peer_id`, `message`, `random_id`, `access_token`, `v=5.199`.

Особенность: ВКонтакте требует от каждого исходящего сообщения уникальный **random_id** (защита от случайных дублей при ретраях). Берём `secrets.randbits(31)` (положительное 32-битное число). В таблице `MessageLog` уже есть поле `external_message_id` — туда сохраняем message_id из ответа ВК для последующей корреляции.

### 4.5 Вариант А для множественного выбора сообществ

Пользователь на экране согласия ВК может отметить несколько сообществ. ВК тогда вернёт во фрагменте URL отдельные пары для каждого:

```
#access_token_222222222=abc...&access_token_333333333=def...&expires_in=0
```

Фронтенд парсит все пары `access_token_<group_id>=<token>`, отправляет на бэкенд массивом. Бэкенд в цикле для каждой пары создаёт `MessengerChannel` и регистрирует webhook. Если по одному из сообществ что-то упало — остальные всё равно создаются, упавшее возвращается в ответе с описанием ошибки. Фронтенд показывает итог: «Подключено N из M, ошибки: …».

### 4.6 Что НЕ делаем в этой задаче

- **Лид-формы ВК** (`lead_forms_new`) — отдельная сущность, не чат, не входит в область
- **Комментарии под постами / wall_reply** — не используется как «входящее обращение»
- **Long Poll-режим** — Callback API нам достаточно
- **Загрузка вложений из ВК в нашу медиатеку** — пока сохраняем только метаданные вложений в `MessageLog.attachments`, физический файл оставляем на серверах ВК (как сейчас с другими каналами)
- **Отправка вложений из CRM в ВК** — только текст в первой версии; вложения можно добавить отдельной задачей
- **OAuth-refresh для community token** — community access token у ВК **бессрочный** (или живёт до явного отзыва пользователем). Refresh-механики не нужно. Если токен внезапно перестал работать (`error_code=5` от ВК) — помечаем канал статусом `error` с подсказкой «Переподключите ВКонтакте», пользователь снова жмёт кнопку.

---

## 5. Состав изменений

### 5.1 Бэкенд

#### Новые файлы

**`apps/channels/oauth_api.py`** (по образцу `apps/integrations/oauth_api.py`)

Содержит два эндпоинта, ниже их контракт:

```
POST /api/channels/oauth/vk/start/
Auth: required (require_roles: owner, admin)
Body: {} (пустое; tenant и user берутся из request)
Response: {
  "authorize_url": "https://oauth.vk.com/authorize?...",
  "state": "подписанный-токен"
}
```

```
POST /api/channels/oauth/vk/complete/
Auth: required (require_roles: owner, admin)
Body: {
  "state": "подписанный-токен из /start/",
  "tokens": [
    {"group_id": 222222222, "access_token": "abc..."},
    {"group_id": 333333333, "access_token": "def..."}
  ]
}
Response: {
  "created": [
    {"channel_id": 17, "group_id": 222222222, "name": "Моё сообщество"},
    ...
  ],
  "failed": [
    {"group_id": 333333333, "error": "Не удалось зарегистрировать webhook: ..."}
  ]
}
```

Реализация `/complete/`:
1. Распаковка и проверка state (signing.loads с salt='vk-channel-oauth', max_age=3600)
2. Проверка `tenant_id` из state совпадает с `get_request_tenant(request).id`
3. Для каждой пары `(group_id, access_token)`:
   - Вызов `groups.getById` → получение имени и аватарки сообщества
   - Создание `MessengerChannel(channel_type='vk', name=имя, credentials={group_id, access_token, app_id}, status='active')`
   - Вызов `register_vk_callback(channel, webhook_base_url, tenant_slug)` (см. ниже)
   - Если webhook не зарегистрировался — `channel.delete()` и добавление в `failed`
4. Возврат списков `created` / `failed`

#### Изменения в существующих файлах

**`apps/channels/models.py`**
- В `MessengerChannel.CHANNEL_TYPE_CHOICES` добавить `('vk', 'ВКонтакте')`
- `max_length=20` уже достаточно
- Создать миграцию `apps/channels/migrations/00XX_messengerchannel_vk_choice.py` — изменение choices (Django сгенерирует автоматически через `makemigrations`)

**`apps/channels/providers.py`** — добавить четыре функции и две ветки:

```
def get_vk_group_info(access_token: str, group_id: int | str) -> dict
    # GET https://api.vk.com/method/groups.getById?group_id=...&access_token=...&v=5.199
    # Возвращает {'name': '...', 'photo_200': '...'} или {'error': '...'}

def register_vk_callback(channel: MessengerChannel, webhook_base_url: str, tenant_slug: str) -> tuple[bool, str]
    # 1. groups.getCallbackConfirmationCode → credentials.confirmation_code
    # 2. Генерация secrets.token_urlsafe(32) → credentials.secret_key
    # 3. groups.addCallbackServer → credentials.server_id
    # 4. groups.setCallbackSettings(message_new=1)
    # Возвращает (True, 'ok') или (False, описание ошибки)

def unregister_vk_callback(channel: MessengerChannel) -> tuple[bool, str]
    # groups.deleteCallbackServer(group_id, server_id)

def get_vk_callback_info(access_token: str, group_id: int | str) -> dict
    # groups.getCallbackServers — для диагностики в админке
```

Ветка `vk` в `normalize_incoming_payload`:
- Если `payload.get('type') != 'message_new'` — вернуть `None` (игнор confirmation, wall_reply и пр.)
- Извлечь `object.message`: `from_id`, `peer_id`, `text`, `id`, `attachments`
- Вернуть стандартный dict: `{'chat_id': str(peer_id), 'username': '', 'phone': '', 'text': text, 'message_id': str(id), 'attachments': attachments}`
- Имя пользователя оставляем пустым — заполним отдельным вызовом `users.get` в `_auto_create_lead`, если потребуется (вынесено за рамки этой задачи; в первой версии имя контакта будет «Клиент ВК <id>»)

Ветка `vk` в `send_outgoing`:
- POST `https://api.vk.com/method/messages.send` с параметрами `peer_id=external_chat_id`, `message=text`, `random_id=secrets.randbits(31)`, `access_token=credentials['access_token']`, `v='5.199'`
- Проверка ответа: если `body.get('response')` — успех, возвращаем `(True, str(body['response']))`, иначе `(False, body.get('error', {}).get('error_msg', 'unknown'))`

**`apps/channels/public_views.py`** — расширить функцию, обрабатывающую `/channels/webhook/<tenant_slug>/<provider>/<channel_id>/`:

Ветка `provider == 'vk'`:
1. Парсинг JSON-тела запроса
2. Если `payload.get('type') == 'confirmation'`:
   - Достать `MessengerChannel.objects.get(id=channel_id, channel_type='vk')`
   - Вернуть `HttpResponse(channel.credentials['confirmation_code'], content_type='text/plain')`
3. Иначе:
   - Сверить `payload.get('secret')` с `channel.credentials['secret_key']`
   - Если не совпадает — `HttpResponse('forbidden', status=403)`
   - Передать payload в Celery-задачу `process_incoming_message.delay(channel_id, payload)` (та же задача, что и для других провайдеров)
   - Вернуть `HttpResponse('ok', content_type='text/plain')`

**`config/api.py`** — зарегистрировать новый роутер из `apps/channels/oauth_api.py`:
```python
from apps.channels.oauth_api import router as vk_oauth_router
api.add_router('/channels/oauth/vk', vk_oauth_router)
```

**`config/settings.py`** — добавить:
```python
VK_APP_ID = os.getenv('VK_APP_ID', '')
VK_API_VERSION = '5.199'
```

**`.env.example`** — добавить блок:
```
# ВКонтакте: ID standalone-приложения для OAuth подключения каналов.
# Регистрируется один раз на vk.com/dev. См. docs/user-guide/admin/vk-app-setup.md
VK_APP_ID=
```

#### Что НЕ меняется

- `apps/channels/tasks.py` — `process_incoming_message`, `_auto_create_lead`, `_find_pipeline_and_stage` уже provider-agnostic, работают как есть
- `apps/channels/consumers.py` — WebSocket-логика канал-агностична
- `apps/channels/api.py` — CRUD каналов работает без изменений (новый тип просто добавится в `CHANNEL_TYPE_CHOICES`)

### 5.2 Фронтенд

#### Новые файлы

**`frontend/src/views/oauth/VkCallbackView.vue`**

Минимальная страница без layout (вне `AppLayout`):
```
<template>
  <div class="vk-callback">
    <PProgressSpinner v-if="loading" />
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <h2>ВКонтакте подключён</h2>
      <p>Создано каналов: {{ result.created.length }}</p>
      <ul v-if="result.failed.length"><li v-for="f in result.failed">{{ f.group_id }}: {{ f.error }}</li></ul>
      <PButton label="К мессенджерам" @click="goBack" />
    </div>
  </div>
</template>

<script setup lang="ts">
// onMounted:
// 1. const hash = window.location.hash.slice(1)
// 2. const params = new URLSearchParams(hash)
// 3. Собрать массив tokens: для каждого ключа, начинающегося с 'access_token_', взять суффикс как group_id, значение как access_token
// 4. const state = sessionStorage.getItem('vk_oauth_state')
// 5. POST /api/channels/oauth/vk/complete/ с {state, tokens}
// 6. Показать результат, через 2 секунды редирект на /app/settings/messengers
</script>
```

**`frontend/src/api/channels.ts`** (если ещё нет — расширить, иначе создать) — методы:
```typescript
async function startVkOauth(): Promise<{authorize_url: string, state: string}>
async function completeVkOauth(payload: {state: string, tokens: Array<{group_id: number, access_token: string}>}): Promise<{created: ..., failed: ...}>
```

#### Изменения

**`frontend/src/router/index.ts`** — добавить публичный роут (без auth-guard, потому что после редиректа от ВК пользователь может прийти не до конца авторизованным; но фактически он залогинен — мы откроем страницу из его же сессии. На всякий случай оставим без жёсткого guard, проверку прав сделает сам бэкенд при `/complete/`):

```typescript
{
  path: '/oauth/vk/callback',
  component: () => import('@/views/oauth/VkCallbackView.vue'),
  meta: { public: true }
}
```

**`frontend/src/views/settings/MessengersView.vue`** (или эквивалент — найти текущий компонент списка каналов):
- В секцию «Добавить канал» добавить кнопку **«Подключить ВКонтакте»**
- Обработчик клика:
  ```typescript
  const {authorize_url, state} = await startVkOauth()
  sessionStorage.setItem('vk_oauth_state', state)
  window.location.href = authorize_url
  ```
- В отображении канала: если `channel_type === 'vk'` — показывать иконку ВКонтакте (добавить SVG в `frontend/src/assets/icons/vk.svg`), название сообщества из `channel.name`

**`frontend/src/views/ChatsView.vue`** (или где список чатов) — никаких изменений не требуется, чаты работают на уровне `ChatSession`, тип канала отображается через метаданные.

### 5.3 Тесты

**`apps/channels/tests/test_vk_provider.py`** — новый файл:
- `test_normalize_message_new` — парсинг стандартного payload `message_new`
- `test_normalize_ignores_confirmation` — confirmation возвращает None
- `test_normalize_ignores_wall_reply` — другие типы возвращают None
- `test_normalize_handles_attachments` — пустые/непустые attachments
- `test_send_outgoing_success` — мок `requests.post`, проверка параметров (peer_id, random_id, access_token, v)
- `test_send_outgoing_error` — VK вернула `{"error": {...}}` → (False, error_msg)
- `test_register_vk_callback_full_flow` — мок трёх HTTP-вызовов подряд, проверка сохранения confirmation_code/secret_key/server_id в credentials

**`apps/channels/tests/test_vk_webhook.py`** — новый файл:
- `test_confirmation_returns_code` — POST с `type=confirmation` возвращает plain-text код
- `test_message_new_with_correct_secret` — payload с правильным secret вызывает `process_incoming_message.delay`, ответ `ok`
- `test_wrong_secret_returns_403` — payload с неверным secret → 403, задача не вызывается
- `test_missing_channel_returns_404` — несуществующий channel_id

**`apps/channels/tests/test_vk_oauth_api.py`** — новый файл:
- `test_start_returns_authorize_url` — содержит `oauth.vk.com/authorize`, `client_id=VK_APP_ID`, валидный state
- `test_complete_creates_channels` — мок VK API, проверка создания `MessengerChannel`-записей
- `test_complete_invalid_state_returns_400` — подмена state → 400
- `test_complete_state_from_other_tenant_rejected` — state с чужим tenant_id → 400
- `test_complete_partial_failure` — один токен валиден, другой — нет; created содержит первый, failed — второй
- `test_start_requires_admin` — viewer/manager → 403

### 5.4 Документация

**`docs/DECISIONS.md`** — добавить запись:
```
## DEC-038 (2026-XX-XX): Канал ВКонтакте через Standalone OAuth + Callback API

**Решение:** канал ВК подключается через одно standalone-приложение PRVMS на vk.com/dev.
OAuth использует Implicit Flow (токен во фрагменте URL); доставка токенов с фронтенда
на бэкенд через `POST /api/channels/oauth/vk/complete/`. Webhook регистрируется
автоматически в момент complete. Принимаются только события `message_new`
(личные сообщения сообществу). Лид-формы, комментарии, упоминания — out of scope.

**Альтернативы:**
- Ручной ввод access_token — отклонено из-за плохого UX
- Long Poll — отклонено, требует постоянного воркера
- Покрытие лид-форм — выделено в отдельную будущую задачу

**Инварианты:**
- VK_APP_ID хранится в env, един для всей платформы
- Один MessengerChannel = одно сообщество
- credentials.secret_key проверяется при каждом входящем webhook
- При первом запросе ВК (`type=confirmation`) отвечаем plain-text кодом
- random_id обязателен в каждом messages.send
```

**`docs/DEV_LOG.md`** — запись по факту реализации с датой, перечнем файлов, прогоном тестов.

**`docs/RELEASE_NOTES.md`** — пользовательская формулировка:
```
## 0.5.0 — Канал ВКонтакте

Добавлена возможность принимать сообщения от клиентов прямо из сообщества ВКонтакте.
Подключается одной кнопкой через ваш аккаунт ВК — никаких токенов и настроек.
Сообщения попадают в раздел «Чаты», каждое новое обращение автоматически создаёт
сделку. Ответы из CRM уходят клиенту в ВК.
```

**`docs/user-guide/vk-channel.md`** — новая статья:
- Как подключить (3 шага: нажать кнопку → выбрать сообщество → разрешить)
- Что приходит и что не приходит (только личные сообщения сообществу)
- Как переподключить, если перестало работать
- FAQ: «почему ВК просит доступ к управлению сообществом?» — потому что для отправки ответов нам нужен токен сообщества; этот токен мы используем только для чтения входящих и отправки исходящих сообщений, ничего другого мы не делаем

**`docs/user-guide/admin/vk-app-setup.md`** — новая статья (для администратора платформы):
- Пошаговая инструкция регистрации Standalone-приложения на vk.com/dev
- Настройка доверенного redirect URI
- Куда положить `VK_APP_ID`

**`docs/TASK_STATE.md`** — добавить строку в активные задачи во время реализации, перенести в «завершённые» по факту.

**`docs/KNOWN_ISSUES.md`** — после реализации зафиксировать ограничения:
- Имя контакта при создании сделки из ВК — «Клиент ВК <id>» (не запрашиваем `users.get` в первой версии)
- Вложения исходящих сообщений не поддерживаются
- Стикеры/опросы/геолокация из входящих сохраняются только как метаданные attachments, не отображаются в UI

---

## 6. Порядок реализации

Один согласованный коммит, но логически — следующая последовательность:

1. **Модель и миграция** — `MessengerChannel.CHANNEL_TYPE_CHOICES`, `makemigrations channels`
2. **Провайдер** — `apps/channels/providers.py` (4 функции + 2 ветки) + unit-тесты
3. **Webhook** — расширение `apps/channels/public_views.py` + тесты
4. **OAuth API** — `apps/channels/oauth_api.py` + регистрация роутера в `config/api.py` + тесты
5. **Settings/env** — `config/settings.py`, `.env.example`
6. **Фронтенд** — `VkCallbackView.vue`, роут, кнопка в `MessengersView`, метод в `api/channels.ts`, SVG-иконка
7. **Документация** — DECISIONS, DEV_LOG, RELEASE_NOTES, user-guide
8. **Валидация** (см. раздел 7)

---

## 7. Валидационный гейт перед сдачей

Обязательно (зелёное — иначе не сдаём):
- `docker compose run --rm web python manage.py check` — 0 issues
- `docker compose run --rm web python manage.py migrate_schemas --tenant --noinput` — миграция применяется чисто
- `docker compose run --rm web python manage.py test apps.channels` — все существующие + новые тесты зелёные
- `docker compose exec frontend npm run typecheck` — EXIT=0
- `docker compose exec frontend npm run build` — EXIT=0
- `docker compose exec frontend npm run test` — зелёные

Ручная проверка (без живого VK API — мокаем или используем тестовое сообщество):
- В Vite-окружении открыть `/app/settings/messengers`, увидеть кнопку «Подключить ВКонтакте»
- Клик по кнопке → редирект ушёл на oauth.vk.com (проверить URL глазами)
- Перехватить редирект, вручную перейти на `/oauth/vk/callback#access_token_111=fake&expires_in=0` — увидеть, что фронтенд парсит и пытается POST'ить (с фейковым токеном бэкенд вернёт ошибку — ок, проверяем сам факт цепочки)

Полная проверка на реальном сообществе ВКонтакте — отдельным заходом администратора платформы после получения настоящего `VK_APP_ID`.

---

## 8. Открытые вопросы (требуют ответа до начала кодинга)

Все вопросы по архитектуре закрыты. Возможные точки уточнения по ходу:

- **Имя пользователя в чате** — оставляем заглушку «Клиент ВК <id>» или сразу делаем `users.get`? (Текущий план: заглушка, `users.get` отдельной задачей.)
- **Куда положить кнопку «Подключить ВКонтакте» на странице мессенджеров** — это вопрос UX, разрешается в момент правки `MessengersView.vue` исходя из текущей раскладки.
- **Стиль иконки ВК** — взять официальный SVG-логотип ВКонтакте (доступен в брендбуке).

---

## 9. Что задача НЕ решает (явно вынесено за рамки)

- Отправка вложений (фото/файлы/голос) из CRM в ВК
- Получение и отображение стикеров/опросов/геолокации
- Лид-формы ВК
- Комментарии под постами
- Реклама ВКонтакте, статистика, любые другие API ВК кроме messages.send + groups.*
- Подключение **личного** профиля ВК (только сообщества)
- Множественные администраторы одного канала с разными токенами

Любой из этих пунктов — отдельная задача после релиза базовой версии.
