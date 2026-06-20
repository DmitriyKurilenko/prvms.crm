from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.ai_assistant.public_views import hermes_webhook
from apps.billing.public_views import pricing_calculator_quote, pricing_telephony_request
from apps.billing.webhook_views import yookassa_webhook
from apps.channels.public_views import channel_webhook
from apps.documents.public_views import (
    sign_download_pdf,
    sign_esign_agreement,
    sign_page,
    sign_request_otp,
    sign_send_email,
    sign_verify,
)
from apps.integrations.webhook_views import incoming_crm_webhook
from apps.notifications.views import TelegramBotWebhookView
from apps.telephony.public_views import exolve_events, exolve_ipcr

from .api import api
from .views import frontend_entry, healthz, landing_page

urlpatterns = [
    path('', landing_page),
    path('login', frontend_entry, {'path': 'login'}),
    path('login/', frontend_entry, {'path': 'login'}),
    path('register', frontend_entry, {'path': 'register'}),
    path('register/', frontend_entry, {'path': 'register'}),
    path('invite/accept', frontend_entry, {'path': 'invite/accept'}),
    path('invite/accept/', frontend_entry, {'path': 'invite/accept'}),
    path('app', frontend_entry, {'path': 'app'}),
    path('app/', frontend_entry, {'path': 'app'}),
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('healthz', healthz),
    path('healthz/', healthz),
    path('sign/<uuid:token>/', sign_page),
    path('sign/<uuid:token>/esign-agreement/', sign_esign_agreement),
    path('sign/<uuid:token>/request-otp/', sign_request_otp),
    path('sign/<uuid:token>/verify/', sign_verify),
    path('sign/<uuid:token>/download/', sign_download_pdf),
    path('sign/<uuid:token>/send-email/', sign_send_email),
    path('wh/<slug:tenant_slug>/<uuid:webhook_uuid>/', incoming_crm_webhook),
    path('channels/webhook/<slug:tenant_slug>/<str:channel_type>/<int:channel_id>/', channel_webhook),
    path('telephony/exolve/ipcr/', exolve_ipcr),
    path('telephony/exolve/events/', exolve_events),
    path('billing/yookassa/webhook/', yookassa_webhook),
    path('api/public/pricing/quote/', pricing_calculator_quote),
    path('api/public/pricing/telephony-request/', pricing_telephony_request),
    path('notifications/telegram/bot-webhook/', TelegramBotWebhookView.as_view()),
    path('ai/hermes-webhook/', hermes_webhook),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
