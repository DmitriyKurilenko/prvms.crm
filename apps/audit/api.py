import csv
import io
import json
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth
from django.http import HttpResponse
from apps.core.access import require_roles
from .models import AuditEvent

audit_router = Router(tags=['audit'], auth=JWTAuth())


class AuditEventOut(Schema):
    id: int
    user_id: int | None
    user_email: str | None
    action: str
    model_name: str
    object_id: str
    object_repr: str
    changes: dict
    ip_address: str | None
    created_at: str


class AuditListOut(Schema):
    total: int
    items: list[AuditEventOut]


def _build_qs(action, model_name, user_id, date_from, date_to):
    qs = AuditEvent.objects.select_related('user').all()
    if action:
        qs = qs.filter(action=action)
    if model_name:
        qs = qs.filter(model_name=model_name)
    if user_id:
        qs = qs.filter(user_id=user_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


def _event_out(e: AuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=e.id,
        user_id=e.user_id,
        user_email=e.user.email if e.user else None,
        action=e.action,
        model_name=e.model_name,
        object_id=e.object_id,
        object_repr=e.object_repr,
        changes=e.changes,
        ip_address=e.ip_address,
        created_at=e.created_at.isoformat(),
    )


@audit_router.get('/events/', response=AuditListOut)
def list_events(
    request,
    action: str = None,
    model_name: str = None,
    user_id: int = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 50,
    offset: int = 0,
):
    require_roles(request, ['owner', 'admin'])
    qs = _build_qs(action, model_name, user_id, date_from, date_to)
    total = qs.count()
    items = [_event_out(e) for e in qs[offset:offset + limit]]
    return AuditListOut(total=total, items=items)


@audit_router.get('/events/export/')
def export_events(
    request,
    action: str = None,
    model_name: str = None,
    user_id: int = None,
    date_from: str = None,
    date_to: str = None,
):
    require_roles(request, ['owner', 'admin'])
    qs = _build_qs(action, model_name, user_id, date_from, date_to).order_by('-created_at')[:10000]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'created_at', 'user_email', 'action', 'model_name', 'object_repr', 'object_id', 'ip_address', 'changes'])
    for e in qs:
        writer.writerow([
            e.id,
            e.created_at.isoformat(),
            e.user.email if e.user else '',
            e.action,
            e.model_name,
            e.object_repr,
            e.object_id,
            e.ip_address or '',
            json.dumps(e.changes, ensure_ascii=False),
        ])
    response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="audit_events.csv"'
    return response


@audit_router.get('/events/{event_id}/', response=AuditEventOut)
def get_event(request, event_id: int):
    require_roles(request, ['owner', 'admin'])
    e = AuditEvent.objects.select_related('user').get(id=event_id)
    return _event_out(e)
