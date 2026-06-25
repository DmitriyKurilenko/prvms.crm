"""Клиент Deepgram pre-recorded ASR (Фаза 2).

Контракт сверён живым зондом против установленного API (2026-06):
- `POST {base}/v1/listen` с query `model`/`language`/`smart_format`/`punctuate`;
- заголовок `Authorization: Token <DEEPGRAM_API_KEY>`;
- для сырых байтов `Content-Type: audio/mpeg` (mp3), тело — байты аудио;
- ответ: `results.channels[0].alternatives[0].transcript` и `.confidence`,
  `metadata.duration` и `metadata.request_id`.
Реальный ответ зонда: confidence 0.998, request_id 019ef8db-… — форма подтверждена.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger('apps.telephony.transcription')

_TIMEOUT = 300  # запись разговора может быть длинной


class DeepgramError(Exception):
    """Граничная ошибка распознавания (нет ключа / сетевой сбой / плохой ответ)."""


def transcribe(audio: bytes, *, content_type: str = 'audio/mpeg', language: str | None = None,
               model: str | None = None) -> dict:
    """Распознаёт аудиобайты и возвращает {text, confidence, language, duration, request_id}."""
    api_key = settings.DEEPGRAM_API_KEY
    if not api_key:
        raise DeepgramError('DEEPGRAM_API_KEY не настроен')
    if not audio:
        raise DeepgramError('Пустые аудиоданные')

    params = {
        'model': model or settings.DEEPGRAM_MODEL,
        'language': language or settings.DEEPGRAM_LANGUAGE,
        'smart_format': 'true',
        'punctuate': 'true',
    }
    url = f"{settings.DEEPGRAM_API_BASE.rstrip('/')}/v1/listen"
    headers = {'Authorization': f'Token {api_key}', 'Content-Type': content_type}

    try:
        resp = requests.post(url, params=params, data=audio, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning('Deepgram request failed: %s', exc)
        raise DeepgramError(f'Сбой запроса к Deepgram: {exc}') from exc
    except ValueError as exc:  # невалидный JSON
        raise DeepgramError(f'Невалидный ответ Deepgram: {exc}') from exc

    try:
        alt = data['results']['channels'][0]['alternatives'][0]
        meta = data.get('metadata', {})
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepgramError(f'Неожиданная структура ответа Deepgram: {exc}') from exc

    result = {
        'text': alt.get('transcript', ''),
        'confidence': alt.get('confidence'),
        'language': params['language'],
        'duration': meta.get('duration'),
        'request_id': meta.get('request_id'),
    }
    logger.info('Deepgram done request_id=%s duration=%s len=%s',
                result['request_id'], result['duration'], len(result['text']))
    return result
