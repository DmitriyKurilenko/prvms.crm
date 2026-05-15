from __future__ import annotations

from apps.billing.guards import check_limit
from apps.core.access import require_crm_permission, require_roles
from apps.core.tenant import get_request_tenant
from ._api_common import _ensure_builtin, crm_router
from .models import Deal, Pipeline, Stage
from .schemas import PipelineIn, PipelinePatchIn, StageIn, StagePatchIn


@crm_router.get('/pipelines/')
def list_pipelines(request):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    return [
        {'id': p.id, 'name': p.name, 'is_default': p.is_default, 'sort_order': p.sort_order, 'is_active': p.is_active}
        for p in Pipeline.objects.all().order_by('sort_order', 'id')
    ]


@crm_router.post('/pipelines/')
def create_pipeline(request, payload: PipelineIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    tenant = get_request_tenant(request)
    current = Pipeline.objects.count()
    if not check_limit(tenant, 'max_pipelines', current):
        return 400, {'detail': 'Pipeline limit reached'}
    p = Pipeline.objects.create(**payload.dict())
    return {'id': p.id}


@crm_router.patch('/pipelines/{pipeline_id}/')
def patch_pipeline(request, pipeline_id: int, payload: PipelinePatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Pipeline.objects.filter(id=pipeline_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@crm_router.delete('/pipelines/{pipeline_id}/')
def delete_pipeline(request, pipeline_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    if Deal.objects.filter(pipeline_id=pipeline_id).exists():
        return 400, {'detail': 'Pipeline has deals'}
    Pipeline.objects.filter(id=pipeline_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/pipelines/{pipeline_id}/stages/')
def list_stages(request, pipeline_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    return [
        {'id': s.id, 'name': s.name, 'stage_type': s.stage_type, 'color': s.color, 'sort_order': s.sort_order, 'auto_action': s.auto_action}
        for s in Stage.objects.filter(pipeline_id=pipeline_id).order_by('sort_order', 'id')
    ]


@crm_router.post('/pipelines/{pipeline_id}/stages/')
def create_stage(request, pipeline_id: int, payload: StageIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    s = Stage.objects.create(pipeline_id=pipeline_id, **payload.dict())
    return {'id': s.id}


@crm_router.patch('/stages/{stage_id}/')
def patch_stage(request, stage_id: int, payload: StagePatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Stage.objects.filter(id=stage_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@crm_router.delete('/stages/{stage_id}/')
def delete_stage(request, stage_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    if Deal.objects.filter(stage_id=stage_id).exists():
        return 400, {'detail': 'Stage has deals'}
    Stage.objects.filter(id=stage_id).delete()
    return {'detail': 'deleted'}


@crm_router.post('/pipelines/{pipeline_id}/stages/reorder/')
def reorder_stages(request, pipeline_id: int, payload: list[int]):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    for index, stage_id in enumerate(payload):
        Stage.objects.filter(id=stage_id, pipeline_id=pipeline_id).update(sort_order=index)
    return {'detail': 'ok'}
