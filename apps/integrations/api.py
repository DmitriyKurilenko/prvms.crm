"""Backwards-compatible aggregator for `apps.integrations.api`.

Real endpoints live in the domain modules `connections_api`,
`webhooks_api`, `oauth_api`. Each imports the shared
`integrations_router` from `_api_common` and attaches its endpoints via
decorators. This shim imports every domain module for that side-effect
and re-exports `integrations_router` for `config/api.py`.

The import order below preserves the original route-registration order.

`check_crm_connections_health` and `sync_crm_users` are re-exported here
because the test suite patches them at `apps.integrations.api.<task>.delay`.
They are the same Celery task singletons the domain modules call, so the
patch applies regardless of which module invokes `.delay()`. Do not
remove these imports.
"""
from . import (  # noqa: F401
    connections_api,
    oauth_api,
    webhooks_api,
)
from ._api_common import integrations_router
from .tasks import check_crm_connections_health, sync_crm_users  # noqa: F401  (test patch target)

__all__ = ['integrations_router', 'check_crm_connections_health', 'sync_crm_users']
