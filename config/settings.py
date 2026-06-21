from datetime import timedelta
from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['*']),
)

BASE_DIR = Path(__file__).resolve().parent.parent

env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# ---------- Database ----------
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env.db('DATABASE_URL').get('NAME', 'platform_db'),
        'USER': env.db('DATABASE_URL').get('USER', 'platform'),
        'PASSWORD': env.db('DATABASE_URL').get('PASSWORD', 'platform_dev'),
        'HOST': env.db('DATABASE_URL').get('HOST', 'db'),
        'PORT': env.db('DATABASE_URL').get('PORT', '5432'),
    }
}

DATABASE_ROUTERS = ('django_tenants.routers.TenantSyncRouter',)

# ---------- django-tenants ----------
TENANT_MODEL = 'tenants.Tenant'
TENANT_DOMAIN_MODEL = 'tenants.Domain'
# In development we allow unknown hostnames to resolve to the public schema.
# This keeps health checks and bootstrap endpoints available before any tenant/domain
# is created.
SHOW_PUBLIC_IF_NO_TENANT_FOUND = env.bool('SHOW_PUBLIC_IF_NO_TENANT_FOUND', default=DEBUG)

SHARED_APPS = [
    'django_tenants',
    'apps.tenants',
    'apps.billing',
    'apps.users',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ninja_jwt',
    'ninja_jwt.token_blacklist',
    'corsheaders',
    'channels',
]

TENANT_APPS = [
    'apps.documents',
    'apps.distribution',
    'apps.integrations',
    'apps.channels',
    'apps.telephony',
    'apps.crm',
    'apps.audit',
    'apps.notifications',
    'apps.ai_assistant',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

AUTH_USER_MODEL = 'users.User'

# ---------- Middleware ----------
MIDDLEWARE = [
    'apps.core.middleware.HealthCheckBypassMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django_tenants.middleware.main.TenantMainMiddleware',
    'apps.core.middleware.EnsureTenantContextMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------- ASGI + Channels ----------
ASGI_APPLICATION = 'config.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://redis:6379/0')],
        },
    },
}

WSGI_APPLICATION = 'config.wsgi.application'

# ---------- Auth ----------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------- JWT (ninja-jwt) ----------
NINJA_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# ---------- CORS ----------
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:5173'])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-slug',
]

# ---------- Production Security ----------
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------- i18n ----------
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# ---------- Static / Media ----------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------- Redis / Celery ----------
REDIS_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'expire-signing-sessions-every-30-min': {
        'task': 'apps.documents.tasks.expire_signing_sessions',
        'schedule': timedelta(minutes=30),
    },
    'check-plan-limits-hourly': {
        'task': 'apps.billing.tasks.check_plan_limits',
        'schedule': timedelta(hours=1),
    },
    'check-crm-health-every-15-min': {
        'task': 'apps.integrations.tasks.check_crm_connections_health',
        'schedule': timedelta(minutes=15),
    },
    'check-overdue-tasks-hourly': {
        'task': 'apps.crm.tasks.check_overdue_tasks',
        'schedule': timedelta(hours=1),
    },
}

# ---------- Caches ----------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ---------- Logging ----------
# Единая точка наблюдаемости. До этого проект полагался на дефолты Django,
# из-за чего «самодиагностика» интеграций (логи Exolve/ЮKassa/CRM-webhook,
# см. KNOWN_ISSUES #23) не была настроена структурно. disable_existing_loggers
# намеренно False — чтобы не глушить логгеры Django/Celery/django-tenants.
LOG_LEVEL = env('LOG_LEVEL', default='INFO')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Доменные логгеры внешних интеграций — единая точка наблюдения за
        # граничными вызовами (Exolve, внешние CRM, ЮKassa, мессенджеры, ЭДО).
        'apps.telephony': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'apps.integrations': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'apps.billing': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'apps.channels': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'apps.documents': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'apps.ai_assistant': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
    },
}

# ---------- Encryption ----------
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='')
SALT_KEY = env.list('SALT_KEY', default=[FIELD_ENCRYPTION_KEY or SECRET_KEY])

# ---------- Email ----------
# Транспорт читается из nodemailer-стиля env-переменных (SMTP_*/CONTACT_*),
# которые задаёт хостинг (Beget), и маппится на Django EMAIL_*.
# Если EMAIL_BACKEND не задан явно, выбираем SMTP при наличии внешнего хоста,
# иначе падаем обратно к console (безопасный dev-режим). Это исключает
# молчаливую потерю писем, когда SMTP_HOST заполнен, а backend остался console.
_smtp_host = env('SMTP_HOST', default='')
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default=(
        'django.core.mail.backends.smtp.EmailBackend'
        if _smtp_host and _smtp_host not in ('localhost', '127.0.0.1')
        else 'django.core.mail.backends.console.EmailBackend'
    ),
)
EMAIL_HOST = env('SMTP_HOST', default='localhost')
EMAIL_PORT = env.int('SMTP_PORT', default=587)
EMAIL_HOST_USER = env('SMTP_USER', default='')
EMAIL_HOST_PASSWORD = env('SMTP_PASS', default='')
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=10)
# nodemailer `secure`: true → неявный TLS (SMTPS, порт 465); false → STARTTLS (587).
# Django требует взаимоисключающие USE_SSL/USE_TLS — деривация гарантирует это.
EMAIL_USE_SSL = env.bool('SMTP_SECURE', default=False)
EMAIL_USE_TLS = (not EMAIL_USE_SSL) and EMAIL_HOST not in ('', 'localhost')
# From-адрес писем и адрес-получатель заявок с лендинга.
DEFAULT_FROM_EMAIL = env('CONTACT_FROM', default=env('DEFAULT_FROM_EMAIL', default='noreply@platform.ru'))
SUPPORT_EMAIL = env('CONTACT_TO', default='')

# ---------- Pricing Calculator ----------
PRICING_CUSTOM = {
    'user': 1000,
    'messenger': 1000,
    'inbound_channel': 1000,
    'documents_per_100': 200,
    'signatures_per_50': 500,
}

# ---------- Platform ----------
PLATFORM_DOMAIN = env('PLATFORM_DOMAIN', default='localhost:8000')
PLATFORM_PROTOCOL = env('PLATFORM_PROTOCOL', default='http')
FRONTEND_APP_URL = env('FRONTEND_APP_URL', default='http://localhost:5173')
BITRIX24_APP_ID = env('BITRIX24_APP_ID', default='')
BITRIX24_APP_SECRET = env('BITRIX24_APP_SECRET', default='')
AMOCRM_CLIENT_ID = env('AMOCRM_CLIENT_ID', default='')
AMOCRM_CLIENT_SECRET = env('AMOCRM_CLIENT_SECRET', default='')
AMOCRM_REDIRECT_URI = env('AMOCRM_REDIRECT_URI', default='')

# ---------- S3 Storage ----------
if env('S3_BUCKET_NAME', default=''):
    STORAGES = {
        'default': {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    AWS_STORAGE_BUCKET_NAME = env('S3_BUCKET_NAME')
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
    AWS_S3_ENDPOINT_URL = env('S3_ENDPOINT_URL', default='')
    AWS_S3_REGION_NAME = env('S3_REGION', default='ru-msk')
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False
    MEDIA_URL = f"{env('S3_ENDPOINT_URL', default='')}/{env('S3_BUCKET_NAME', default='')}/"

# ---------- Telephony: MTS Exolve ----------
# Облачная телефония MTS Exolve (Numbering API + SIP API + Web Voice SDK).
# Один API-ключ приложения на всю платформу; номера и SIP-аккаунты заводятся
# автоматически через API. Подробности — docs/DECISIONS.md (DEC телефония).
EXOLVE_API_BASE = env('EXOLVE_API_BASE', default='https://api.exolve.ru')
EXOLVE_API_KEY = env('EXOLVE_API_KEY', default='')
EXOLVE_SIP_DOMAIN = env('EXOLVE_SIP_DOMAIN', default='sip.exolve.ru')
# WSS-эндпоинт WebRTC Exolve для Web Voice SDK. Если пусто — SDK использует
# собственный дефолт. Реальное значение задаётся из ЛК/документации Exolve.
EXOLVE_WSS_URL = env('EXOLVE_WSS_URL', default='')
# Секрет, добавляемый в URL IPCR/Call-Events webhook-ов (?key=…).
EXOLVE_WEBHOOK_SECRET = env('EXOLVE_WEBHOOK_SECRET', default='')
# Публичный HTTPS-базовый URL для webhook-ов (если отличается от PLATFORM_*).
EXOLVE_PUBLIC_BASE_URL = env('EXOLVE_PUBLIC_BASE_URL', default='')
# Резервный номер, на который Exolve уведёт звонок при недоступности IPCR-URL.
EXOLVE_IPCR_RESERVE = env('EXOLVE_IPCR_RESERVE', default='')

# ---------- SMS ----------
SMS_PROVIDER = env('SMS_PROVIDER', default='stub')
SMS_API_KEY = env('SMS_API_KEY', default='')
SMS_SENDER_NAME = env('SMS_SENDER_NAME', default='Platform')

# ---------- Telegram ----------
TELEGRAM_NOTIFICATION_BOT_TOKEN = env('TELEGRAM_NOTIFICATION_BOT_TOKEN', default='')
TELEGRAM_NOTIFICATION_BOT_USERNAME = env('TELEGRAM_NOTIFICATION_BOT_USERNAME', default='')

# ---------- Hermes AI Assistant ----------
HERMES_API_URL = env('HERMES_API_URL', default='http://prvmscrm-hermes:8642')
HERMES_API_KEY = env('HERMES_API_KEY', default='')
HERMES_WEBHOOK_SECRET = env('HERMES_WEBHOOK_SECRET', default='')

# ---------- Webhooks ----------
WEBHOOK_BASE_URL = env('WEBHOOK_BASE_URL', default='')

# ---------- VK ----------
VK_APP_ID = env('VK_APP_ID', default='')
VK_API_VERSION = '5.199'

# ---------- YooKassa ----------
YOOKASSA_SHOP_ID = env('YOOKASSA_SHOP_ID', default='')
YOOKASSA_SECRET_KEY = env('YOOKASSA_SECRET_KEY', default='')
YOOKASSA_RETURN_URL = env('YOOKASSA_RETURN_URL', default=f'{FRONTEND_APP_URL}/app/subscription')
