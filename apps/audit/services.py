from .models import AuditEvent


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_event(request, action: str, instance=None, changes: dict = None, **kwargs):
    """Универсальная функция записи в аудит. Вызывается из view/service."""
    actor = None
    if hasattr(request, 'auth') and getattr(request.auth, 'is_authenticated', False):
        actor = request.auth
    elif hasattr(request, 'user') and request.user.is_authenticated:
        actor = request.user

    AuditEvent.objects.create(
        user=actor,
        action=action,
        model_name=instance.__class__.__name__ if instance else kwargs.get('model_name', ''),
        object_id=str(instance.pk) if instance else kwargs.get('object_id', ''),
        object_repr=str(instance)[:300] if instance else kwargs.get('object_repr', ''),
        changes=changes or {},
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )
