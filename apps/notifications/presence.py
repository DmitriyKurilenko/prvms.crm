from __future__ import annotations

import logging
from typing import Iterable

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

PRESENCE_KEY_PREFIX = 'presence'
PRESENCE_TTL_SECONDS = 90


_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _presence_key(tenant_schema: str, user_id: int) -> str:
    return f'{PRESENCE_KEY_PREFIX}:{tenant_schema}:{user_id}'


def mark_online(tenant_schema: str, user_id: int, ttl: int = PRESENCE_TTL_SECONDS) -> None:
    if not tenant_schema or not user_id:
        return
    try:
        _get_client().set(_presence_key(tenant_schema, user_id), '1', ex=ttl)
    except redis.RedisError:
        logger.warning('presence.mark_online failed', exc_info=True)


def mark_offline(tenant_schema: str, user_id: int) -> None:
    if not tenant_schema or not user_id:
        return
    try:
        _get_client().delete(_presence_key(tenant_schema, user_id))
    except redis.RedisError:
        logger.warning('presence.mark_offline failed', exc_info=True)


def list_online_user_ids(tenant_schema: str) -> set[int]:
    if not tenant_schema:
        return set()
    pattern = f'{PRESENCE_KEY_PREFIX}:{tenant_schema}:*'
    result: set[int] = set()
    try:
        for key in _get_client().scan_iter(match=pattern, count=100):
            try:
                result.add(int(str(key).rsplit(':', 1)[-1]))
            except (ValueError, IndexError):
                continue
    except redis.RedisError:
        logger.warning('presence.list_online_user_ids failed', exc_info=True)
    return result


def is_online(tenant_schema: str, user_id: int) -> bool:
    if not tenant_schema or not user_id:
        return False
    try:
        return bool(_get_client().exists(_presence_key(tenant_schema, user_id)))
    except redis.RedisError:
        return False


def reset_client() -> None:
    """Reset the cached redis client (primarily for tests)."""
    global _client
    _client = None


def filter_online(tenant_schema: str, user_ids: Iterable[int]) -> set[int]:
    online = list_online_user_ids(tenant_schema)
    return online.intersection(set(user_ids))
