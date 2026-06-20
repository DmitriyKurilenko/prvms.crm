from functools import wraps

from django.http import JsonResponse

from apps.core.tenant import get_request_tenant


def require_feature(feature_code: str):
    """Декоратор для view/API. Проверяет, что функция доступна в плане тенанта."""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            tenant = get_request_tenant(request, required=False)
            if tenant is None:
                return JsonResponse({'detail': 'Tenant context is required'}, status=400)
            if not tenant.plan.has_feature(feature_code):
                return JsonResponse(
                    {
                        'detail': f'Функция "{feature_code}" недоступна в вашем тарифе. '
                                  f'Текущий план: {tenant.plan.name}.',
                    },
                    status=403,
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_limit(tenant, limit_field: str, current_count: int) -> bool:
    """Проверка лимитов плана. None = безлимит."""
    limit = getattr(tenant.plan, limit_field)
    if limit is None:
        return True
    return current_count < limit
