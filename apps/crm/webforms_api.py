from __future__ import annotations

from django.db import transaction
from django_tenants.utils import schema_context
from ninja.errors import HttpError

from apps.audit.services import log_event
from apps.core.access import require_crm_permission
from apps.core.tenant import get_request_tenant

from ._api_common import _ensure_builtin, crm_router
from .models import WebForm
from .schemas import WebFormIn, WebFormPatchIn


def _embed_snippet(request, token) -> str:
    base = f'{request.scheme}://{request.get_host()}'
    return (
        f'<script src="{base}/widget/crm-webform.js" '
        f'data-token="{token}" data-base="{base}" async></script>'
    )


def _serialize(request, f: WebForm) -> dict:
    return {
        'id': f.id,
        'name': f.name,
        'public_token': str(f.public_token),
        'fields_schema': f.fields_schema,
        'pipeline_id': f.pipeline_id,
        'stage_id': f.stage_id,
        'source': f.source,
        'auto_distribute': f.auto_distribute,
        'success_message': f.success_message,
        'allowed_origins': f.allowed_origins,
        'is_active': f.is_active,
        'submissions_count': f.submissions_count,
        'created_at': f.created_at.isoformat(),
        'embed_snippet': _embed_snippet(request, f.public_token),
    }


def _get_or_404(form_id: int) -> WebForm:
    # Формы — общеорганизационный ресурс без владельца; scope-фильтрация неприменима,
    # доступ контролируется action-флагом через require_crm_permission.
    form = WebForm.objects.filter(id=form_id).first()
    if form is None:
        raise HttpError(404, 'Not found')
    return form


@crm_router.get('/webforms/')
def list_webforms(request):
    require_crm_permission(request, 'webforms', 'view')
    _ensure_builtin(request)
    return [_serialize(request, f) for f in WebForm.objects.all().order_by('-created_at')]


@crm_router.post('/webforms/')
def create_webform(request, payload: WebFormIn):
    require_crm_permission(request, 'webforms', 'create')
    _ensure_builtin(request)
    tenant = get_request_tenant(request)
    data = payload.dict()
    with transaction.atomic():
        form = WebForm.objects.create(
            name=data['name'],
            fields_schema=data['fields_schema'],
            pipeline_id=data['pipeline_id'],
            stage_id=data['stage_id'],
            source=data['source'],
            auto_distribute=data['auto_distribute'],
            success_message=data['success_message'],
            allowed_origins=data['allowed_origins'],
            is_active=data['is_active'],
        )
        with schema_context('public'):
            from apps.tenants.models import WebFormLookup
            WebFormLookup.objects.create(token=form.public_token, tenant=tenant, is_active=form.is_active)
    log_event(request, action='create', instance=form)
    return _serialize(request, form)


@crm_router.get('/webforms/{form_id}/')
def get_webform(request, form_id: int):
    require_crm_permission(request, 'webforms', 'view')
    _ensure_builtin(request)
    return _serialize(request, _get_or_404(form_id))


@crm_router.patch('/webforms/{form_id}/')
def patch_webform(request, form_id: int, payload: WebFormPatchIn):
    require_crm_permission(request, 'webforms', 'update')
    _ensure_builtin(request)
    form = _get_or_404(form_id)
    changes = payload.dict(exclude_unset=True)
    if changes:
        WebForm.objects.filter(id=form_id).update(**changes)
        # Синхронизируем активность в shared-lookup.
        if 'is_active' in changes:
            with schema_context('public'):
                from apps.tenants.models import WebFormLookup
                WebFormLookup.objects.filter(token=form.public_token).update(is_active=changes['is_active'])
        log_event(request, action='update', instance=form)
    return {'detail': 'ok'}


@crm_router.delete('/webforms/{form_id}/')
def delete_webform(request, form_id: int):
    require_crm_permission(request, 'webforms', 'delete')
    _ensure_builtin(request)
    form = _get_or_404(form_id)
    token = form.public_token
    log_event(request, action='delete', instance=form)
    WebForm.objects.filter(id=form_id).delete()
    with schema_context('public'):
        from apps.tenants.models import WebFormLookup
        WebFormLookup.objects.filter(token=token).delete()
    return {'detail': 'deleted'}
