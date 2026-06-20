"""Backwards-compatible aggregator for `apps.users.api`.

Real endpoints live in `auth_api`, `team_api`, `managers_api`. This shim
keeps `from apps.users.api import auth_router, users_router` working for
`config/api.py` and any other importer.

`managers_api` is imported for its side-effect of attaching manager
endpoints onto the shared `users_router` — do not remove the import.
"""
# Side-effect: register manager endpoints on users_router.
from . import managers_api  # noqa: F401
from .auth_api import auth_router
from .team_api import users_router

__all__ = ['auth_router', 'users_router']
