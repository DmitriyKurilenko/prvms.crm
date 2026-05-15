"""Backwards-compatible aggregator for `apps.crm.api`.

Real endpoints live in the domain modules `contacts_api`, `companies_api`,
`pipelines_api`, `deals_api`, `activities_api`, `stats_api`. Each module
imports the shared `crm_router` from `_api_common` and attaches its
endpoints via decorators. This shim imports every domain module for that
side-effect and re-exports `crm_router` so `config/api.py` (and any other
importer) keeps working unchanged.

The import order below preserves the original route-registration order.
Do not remove these imports — they are required for endpoint registration.
"""
from ._api_common import crm_router

from . import (  # noqa: F401
    stats_api,
    contacts_api,
    companies_api,
    pipelines_api,
    deals_api,
    activities_api,
)

__all__ = ['crm_router']
