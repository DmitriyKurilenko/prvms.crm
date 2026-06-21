from __future__ import annotations

from ninja.errors import HttpError

from apps.core.access import require_crm_permission

from ._api_common import _ensure_builtin, _scoped_object_or_error, crm_router
from .models import Contact, Deal, Segment, Tag
from .schemas import SegmentIn, SegmentPatchIn, TagAssignIn, TagIn, TagPatchIn


def _serialize_tag(t: Tag) -> dict:
    return {'id': t.id, 'name': t.name, 'color': t.color}


def _get_tag_or_404(tag_id: int) -> Tag:
    tag = Tag.objects.filter(id=tag_id).first()
    if tag is None:
        raise HttpError(404, 'Not found')
    return tag


# --- Tags -------------------------------------------------------------------

@crm_router.get('/tags/')
def list_tags(request):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    return [_serialize_tag(t) for t in Tag.objects.all()]


@crm_router.post('/tags/')
def create_tag(request, payload: TagIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    if Tag.objects.filter(name=payload.name).exists():
        raise HttpError(400, 'Тег с таким именем уже существует')
    tag = Tag.objects.create(name=payload.name, color=payload.color)
    return {'id': tag.id}


@crm_router.patch('/tags/{tag_id}/')
def patch_tag(request, tag_id: int, payload: TagPatchIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    _get_tag_or_404(tag_id)
    changes = payload.dict(exclude_unset=True)
    if changes:
        Tag.objects.filter(id=tag_id).update(**changes)
    return {'detail': 'ok'}


@crm_router.delete('/tags/{tag_id}/')
def delete_tag(request, tag_id: int):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    _get_tag_or_404(tag_id)
    Tag.objects.filter(id=tag_id).delete()
    return {'detail': 'deleted'}


# --- Assign tags to entities ------------------------------------------------

@crm_router.patch('/contacts/{contact_id}/tags/')
def set_contact_tags(request, contact_id: int, payload: TagAssignIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    contact = _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='update')
    contact.tags.set(Tag.objects.filter(id__in=payload.tag_ids))
    return {'detail': 'ok'}


@crm_router.patch('/deals/{deal_id}/tags/')
def set_deal_tags(request, deal_id: int, payload: TagAssignIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    deal.tags.set(Tag.objects.filter(id__in=payload.tag_ids))
    return {'detail': 'ok'}


# --- Segments (saved filters) -----------------------------------------------

@crm_router.get('/segments/')
def list_segments(request, entity: str | None = None):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    qs = Segment.objects.all()
    if entity:
        qs = qs.filter(entity=entity)
    return [{'id': s.id, 'name': s.name, 'entity': s.entity, 'filters': s.filters} for s in qs]


@crm_router.post('/segments/')
def create_segment(request, payload: SegmentIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    s = Segment.objects.create(name=payload.name, entity=payload.entity, filters=payload.filters)
    return {'id': s.id}


@crm_router.patch('/segments/{segment_id}/')
def patch_segment(request, segment_id: int, payload: SegmentPatchIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    if not Segment.objects.filter(id=segment_id).exists():
        raise HttpError(404, 'Not found')
    changes = payload.dict(exclude_unset=True)
    if changes:
        Segment.objects.filter(id=segment_id).update(**changes)
    return {'detail': 'ok'}


@crm_router.delete('/segments/{segment_id}/')
def delete_segment(request, segment_id: int):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    if not Segment.objects.filter(id=segment_id).exists():
        raise HttpError(404, 'Not found')
    Segment.objects.filter(id=segment_id).delete()
    return {'detail': 'deleted'}
