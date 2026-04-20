from __future__ import annotations

import json
import logging

import requests
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import TelegramBinding
from apps.users.models import User

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class TelegramBotWebhookView(View):
    """Receives updates from Telegram Bot API and handles /start bind_<token> commands."""

    def post(self, request):
        try:
            update = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': True})

        message = update.get('message') or update.get('edited_message')
        if not message:
            return JsonResponse({'ok': True})

        chat_id = message.get('chat', {}).get('id')
        text = (message.get('text') or '').strip()
        username = message.get('from', {}).get('username', '')

        if not chat_id:
            return JsonResponse({'ok': True})

        if text.startswith('/start bind_'):
            bind_token = text[len('/start bind_'):]
            self._handle_bind(chat_id, username, bind_token)
        else:
            self._send_message(chat_id, 'Бот для уведомлений PRVMS CRM. Используйте личный кабинет для привязки аккаунта.')

        return JsonResponse({'ok': True})

    def _handle_bind(self, chat_id: int, username: str, raw_token: str):
        signer = TimestampSigner(salt='telegram-binding')
        try:
            user_id_str = signer.unsign(raw_token, max_age=600)
            user_id = int(user_id_str)
        except (SignatureExpired, BadSignature, ValueError):
            self._send_message(chat_id, 'Ссылка устарела или недействительна. Сформируйте новую ссылку в личном кабинете.')
            return

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            self._send_message(chat_id, 'Пользователь не найден.')
            return

        TelegramBinding.objects.update_or_create(
            user=user,
            defaults={'chat_id': chat_id, 'username': username, 'is_active': True},
        )
        self._send_message(chat_id, f'Telegram привязан к аккаунту {user.email}. Уведомления будут приходить в этот чат.')

    @staticmethod
    def _send_message(chat_id: int, text: str):
        token = settings.TELEGRAM_NOTIFICATION_BOT_TOKEN
        if not token:
            return
        try:
            requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': chat_id, 'text': text},
                timeout=5,
            )
        except requests.RequestException:
            pass
