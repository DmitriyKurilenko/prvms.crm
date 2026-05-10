from ninja import NinjaAPI
from ninja_jwt.authentication import JWTAuth

api = NinjaAPI(
    title='CRM Platform API',
    version='0.1.0',
    auth=JWTAuth(),
    urls_namespace='api',
)

# Public endpoints (no auth)
from apps.users.api import auth_router
api.add_router('/auth/', auth_router)

# Tenant-scoped endpoints
from apps.tenants.api import tenant_router
api.add_router('/tenant/', tenant_router)

from apps.users.api import users_router
api.add_router('/users/', users_router)

from apps.billing.api import billing_router
api.add_router('/billing/', billing_router)

from apps.audit.api import audit_router
api.add_router('/audit/', audit_router)

from apps.notifications.api import notifications_router
api.add_router('/notifications/', notifications_router)

from apps.integrations.api import integrations_router
api.add_router('/integrations/', integrations_router)

from apps.contracts.api import contracts_router
api.add_router('/contracts/', contracts_router)

from apps.distribution.api import distribution_router
api.add_router('/distribution/', distribution_router)

from apps.crm.api import crm_router
api.add_router('/crm/', crm_router)

from apps.crm.dashboard_api import dashboard_router
api.add_router('/dashboard/', dashboard_router)

from apps.channels.api import messenger_channels_router
api.add_router('/channels/', messenger_channels_router)

from apps.telephony.api import telephony_router
api.add_router('/telephony/', telephony_router)

from apps.tenants.onboarding_api import onboarding_router
api.add_router('/onboarding/', onboarding_router)

from apps.ai_assistant.api import ai_router
api.add_router('/ai/', ai_router)

# Health check (public, no auth)
@api.get('/healthz', auth=None, tags=['system'])
def healthz(request):
    return {'status': 'ok'}
