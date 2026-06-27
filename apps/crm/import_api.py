"""Импорт/экспорт и слияние дублей контактов/компаний.

Экспорт повторяет паттерн `apps/audit/api.py` (StringIO → text/csv). Импорт
принимает файл (`UploadedFile`), парсит CSV/XLSX в `services.import_export`,
ставит фоновую задачу `import_records`. Слияние необратимо — пишется в аудит.
Права переиспользуют сущности `contacts`/`companies`: экспорт → view,
импорт → create, слияние → delete.
"""
from __future__ import annotations

import json

from django.http import HttpResponse
from ninja import File, Form
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.audit.services import log_event
from apps.core.access import (
    ensure_crm_object_scope,
    filter_crm_queryset_by_scope,
    require_crm_permission,
)
from apps.core.tenant import get_request_tenant

from ._api_common import _ensure_builtin, crm_router
from .models import Company, Contact, ImportJob
from .schemas import MergeIn

_ENTITIES = ('contacts', 'companies')
# Импорт/экспорт охватывают и сделки; слияние/дубли — только справочные сущности.
_IO_ENTITIES = ('contacts', 'companies', 'deals')
_MAX_IMPORT_ROWS = 10000


def _check_entity(entity: str) -> str:
    if entity not in _ENTITIES:
        raise HttpError(400, 'Поддерживаются только contacts и companies')
    return entity


def _check_io_entity(entity: str) -> str:
    if entity not in _IO_ENTITIES:
        raise HttpError(400, 'Поддерживаются только contacts, companies и deals')
    return entity


# --- Импорт -----------------------------------------------------------------

@crm_router.post('/import/preview/')
def import_preview(request, entity: str = Form(...), file: UploadedFile = File(...)):
    _check_io_entity(entity)
    require_crm_permission(request, entity, 'create')
    _ensure_builtin(request)
    from .services.import_export import allowed_fields, parse_file, suggest_mapping

    try:
        headers, rows = parse_file(file.name, file.read())
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    if len(rows) > _MAX_IMPORT_ROWS:
        raise HttpError(400, f'Слишком много строк (макс. {_MAX_IMPORT_ROWS})')
    return {
        'headers': headers,
        'sample': rows[:10],
        'total_rows': len(rows),
        'suggested_mapping': suggest_mapping(entity, headers),
        'allowed_fields': list(allowed_fields(entity)),
    }


@crm_router.post('/import/run/')
def import_run(
    request,
    entity: str = Form(...),
    mapping: str = Form(...),
    file: UploadedFile = File(...),
):
    _check_io_entity(entity)
    require_crm_permission(request, entity, 'create')
    _ensure_builtin(request)
    from .services.import_export import parse_file
    from .tasks import import_records

    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise HttpError(400, 'Некорректный mapping (ожидается JSON)') from exc
    if not isinstance(mapping_dict, dict) or not mapping_dict:
        raise HttpError(400, 'Пустое сопоставление колонок')
    try:
        _, rows = parse_file(file.name, file.read())
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    if not rows:
        raise HttpError(400, 'В файле нет строк данных')
    if len(rows) > _MAX_IMPORT_ROWS:
        raise HttpError(400, f'Слишком много строк (макс. {_MAX_IMPORT_ROWS})')

    tenant = get_request_tenant(request)
    job = ImportJob.objects.create(entity=entity, created_by=request.auth)
    import_records.delay(tenant.schema_name, job.id, entity, rows, mapping_dict)
    return {'job_id': job.id, 'total': len(rows)}


@crm_router.get('/import/jobs/{job_id}/')
def import_job_status(request, job_id: int):
    _ensure_builtin(request)
    job = ImportJob.objects.filter(id=job_id).first()
    if job is None:
        raise HttpError(404, 'Задание не найдено')
    require_crm_permission(request, job.entity, 'create')
    return {
        'id': job.id,
        'entity': job.entity,
        'status': job.status,
        'total': job.total,
        'processed': job.processed,
        'created': job.created,
        'updated': job.updated,
        'errors': job.errors,
        'created_at': job.created_at.isoformat(),
    }


# --- Экспорт ----------------------------------------------------------------

@crm_router.get('/export/{entity}/')
def export_entity(request, entity: str, source: str | None = None):
    _check_io_entity(entity)
    require_crm_permission(request, entity, 'view')
    _ensure_builtin(request)
    from .services.import_export import export_companies_csv, export_contacts_csv, export_deals_csv

    if entity == 'contacts':
        qs = filter_crm_queryset_by_scope(request, Contact.objects.select_related('company').all(), 'contacts')
        if source:
            qs = qs.filter(source=source)
        body = export_contacts_csv(qs.order_by('-created_at'))
        filename = 'contacts.csv'
    elif entity == 'deals':
        from .models import Deal

        qs = filter_crm_queryset_by_scope(
            request, Deal.objects.select_related('pipeline', 'stage', 'contact').all(), 'deals',
        )
        if source:
            qs = qs.filter(source=source)
        body = export_deals_csv(qs.order_by('-created_at'))
        filename = 'deals.csv'
    else:
        qs = filter_crm_queryset_by_scope(request, Company.objects.all(), 'companies')
        body = export_companies_csv(qs.order_by('-created_at'))
        filename = 'companies.csv'
    response = HttpResponse(body, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# --- Дубли и слияние --------------------------------------------------------

@crm_router.get('/duplicates/{entity}/')
def list_duplicates(request, entity: str):
    _check_entity(entity)
    require_crm_permission(request, entity, 'view')
    _ensure_builtin(request)
    from .services.merge import find_duplicate_companies, find_duplicate_contacts

    return find_duplicate_contacts() if entity == 'contacts' else find_duplicate_companies()


@crm_router.post('/merge/{entity}/')
def merge_entity(request, entity: str, payload: MergeIn):
    _check_entity(entity)
    require_crm_permission(request, entity, 'delete')
    _ensure_builtin(request)
    from .services.merge import merge_companies, merge_contacts

    model = Contact if entity == 'contacts' else Company
    primary = model.objects.filter(id=payload.primary_id).first()
    if primary is None:
        raise HttpError(404, 'Основная запись не найдена')
    ensure_crm_object_scope(request, entity, 'delete', primary)
    for mid in payload.merged_ids:
        if mid == payload.primary_id:
            continue
        obj = model.objects.filter(id=mid).first()
        if obj is None:
            raise HttpError(404, f'Запись {mid} не найдена')
        ensure_crm_object_scope(request, entity, 'delete', obj)

    if entity == 'contacts':
        result = merge_contacts(payload.primary_id, payload.merged_ids)
    else:
        result = merge_companies(payload.primary_id, payload.merged_ids)
    primary.refresh_from_db()
    log_event(request, action='update', instance=primary,
              changes={'Слияние дублей': {'before': str(payload.merged_ids), 'after': result}})
    return result
