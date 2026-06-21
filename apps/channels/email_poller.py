"""IMAP-приём для email-каналов.

Изолирует стык со стандартным `imaplib` (RFC 3501). `fetch(RFC822)` помечает
письмо флагом ``\\Seen``, поэтому повторно оно через ``UNSEEN`` не вернётся;
дополнительно вызывающий код дедуплицирует по ``Message-ID``.

Разбор письма вынесен в чистую `parse_email(raw_bytes)` — её можно тестировать
без IMAP-соединения. Тело берётся из ``text/plain``; при отсутствии — из
``text/html`` с удалением разметки. Метаданные вложений собираются в список.

Граница достоверности: реальное IMAP-соединение проверяется только на боевом
ящике; в тестах разбор проверяется через `parse_email`, а `fetch_new_messages`
мокируется.
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from html.parser import HTMLParser

logger = logging.getLogger('channels.email')


def _decode(value: str | None) -> str:
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except (ValueError, LookupError):
        return str(value)


class _HTMLTextExtractor(HTMLParser):
    """Извлекает видимый текст из HTML, пропуская script/style."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ('script', 'style'):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ('script', 'style') and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._chunks.append(data)

    @property
    def text(self) -> str:
        return ' '.join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — некорректный HTML не должен ронять разбор письма
        logger.warning('html parse failed; returning raw fragment')
        return re.sub(r'<[^>]+>', ' ', html).strip()
    return re.sub(r'\s+', ' ', parser.text).strip()


def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ''
    charset = part.get_content_charset() or 'utf-8'
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode(charset, errors='replace')
    return str(payload)


def _extract_body(msg: Message) -> str:
    """text/plain в приоритете; иначе — text/html, очищенный от разметки."""
    plain = ''
    html = ''
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition:
                continue
            ctype = part.get_content_type()
            if ctype == 'text/plain' and not plain:
                plain = _part_text(part)
            elif ctype == 'text/html' and not html:
                html = _part_text(part)
    else:
        if msg.get_content_type() == 'text/html':
            html = _part_text(msg)
        else:
            plain = _part_text(msg)
    if plain.strip():
        return plain
    return _html_to_text(html) if html else ''


def _extract_attachments(msg: Message) -> list[dict]:
    """Метаданные вложений (имя, тип). Содержимое в первой версии не сохраняется."""
    out: list[dict] = []
    if not msg.is_multipart():
        return out
    for part in msg.walk():
        disposition = str(part.get('Content-Disposition', ''))
        filename = part.get_filename()
        if filename or 'attachment' in disposition:
            out.append(
                {
                    'filename': _decode(filename) or 'attachment',
                    'content_type': part.get_content_type(),
                }
            )
    return out


def parse_email(raw: bytes) -> dict:
    """Разбирает сырое письмо в нормализованный диалоговый dict.

    Возвращает ``{message_id, from_email, from_name, subject, text, attachments}``.
    Чистая функция — тестируется без IMAP.
    """
    msg = email.message_from_bytes(raw)
    from_name, from_email = parseaddr(_decode(msg.get('From')))
    return {
        'message_id': (msg.get('Message-ID') or '').strip(),
        'from_email': from_email,
        'from_name': from_name or from_email,
        'subject': _decode(msg.get('Subject')),
        'text': _extract_body(msg),
        'attachments': _extract_attachments(msg),
    }


def fetch_new_messages(creds: dict) -> list[dict]:
    """Возвращает список новых входящих писем (см. `parse_email`).

    Стык [граница]: реальный IMAP-сервер.
    """
    host = creds.get('imap_host', '')
    port = int(creds.get('imap_port', 993))
    use_ssl = bool(creds.get('imap_ssl', True))
    username = creds.get('username', '')
    password = creds.get('password', '')
    folder = creds.get('poll_folder', 'INBOX')

    if not host or not username:
        logger.warning('email poll skipped: host/username not configured')
        return []

    box = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    out: list[dict] = []
    try:
        box.login(username, password)
        box.select(folder)
        typ, data = box.search(None, 'UNSEEN')
        if typ != 'OK' or not data or not data[0]:
            return out
        for num in data[0].split():
            typ, msg_data = box.fetch(num, '(RFC822)')
            if typ != 'OK' or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            out.append(parse_email(raw))
        logger.info('email poll host=%s user=%s new=%s', host, username, len(out))
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001 — закрытие соединения не должно ронять задачу
            logger.warning('imap logout failed for %s', username)
    return out
