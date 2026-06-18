from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.template import Context, Template
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from weasyprint import HTML

from apps.billing.guards import check_limit
from apps.core.access import require_feature_access, require_roles
from apps.core.tenant import get_request_tenant
from apps.crm.models import Deal
from .models import Document, DocumentTemplate, FieldMapping
from .services import create_document_from_deal, send_for_signing, SigningError

documents_router = Router(tags=['documents'], auth=JWTAuth())


class DocumentTemplateIn(Schema):
    name: str
    html_body: str
    document_type: str = 'contract'
    variable_schema: list[dict] = []
    is_active: bool = True


class DocumentTemplatePatchIn(Schema):
    name: str | None = None
    html_body: str | None = None
    document_type: str | None = None
    variable_schema: list[dict] | None = None
    is_active: bool | None = None


class DocumentGenerateIn(Schema):
    template_id: int
    deal_id: int | None = None
    filled_data: dict | None = None
    signing_method: str = 'sms_otp'


class SendForSigningIn(Schema):
    recipient: str


@documents_router.get('/templates/')
def list_templates(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'documents')
    templates = DocumentTemplate.objects.all().order_by('-id')
    return [
        {
            'id': t.id,
            'name': t.name,
            'document_type': t.document_type,
            'version': t.version,
            'is_active': t.is_active,
            'is_system': t.is_system,
            'html_body': t.html_body,
            'variable_schema': t.variable_schema,
            'created_at': t.created_at.isoformat(),
            'updated_at': t.updated_at.isoformat(),
        }
        for t in templates
    ]


@documents_router.post('/templates/')
def create_template(request, payload: DocumentTemplateIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'documents')
    t = DocumentTemplate.objects.create(
        name=payload.name,
        document_type=payload.document_type,
        html_body=payload.html_body,
        variable_schema=payload.variable_schema,
        is_active=payload.is_active,
    )
    return {'id': t.id}


@documents_router.patch('/templates/{template_id}/')
def update_template(request, template_id: int, payload: DocumentTemplatePatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'documents')
    t = DocumentTemplate.objects.get(id=template_id)
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(t, key, value)
    t.version += 1
    t.save()
    return {'detail': 'ok'}


@documents_router.get('/templates/{template_id}/preview/')
def preview_template(request, template_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'documents')
    template = DocumentTemplate.objects.get(id=template_id)
    sample_data = {item.get('key', f'var_{index}'): item.get('sample', f'example_{index}') for index, item in enumerate(template.variable_schema, start=1)}
    rendered = Template(template.html_body).render(Context(sample_data))
    return {'html': rendered}


@documents_router.get('/templates/{template_id}/mappings/')
def list_mappings(request, template_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'documents')
    rows = FieldMapping.objects.filter(template_id=template_id)
    return [
        {
            'id': row.id,
            'crm_connection_id': row.crm_connection_id,
            'variable_key': row.variable_key,
            'crm_field_path': row.crm_field_path,
        }
        for row in rows
    ]


@documents_router.put('/templates/{template_id}/mappings/{connection_id}/')
def save_mappings(request, template_id: int, connection_id: int, payload: list[dict]):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'documents')
    conn_id = None if connection_id == 0 else connection_id
    FieldMapping.objects.filter(template_id=template_id, crm_connection_id=conn_id).delete()
    created = 0
    for item in payload:
        FieldMapping.objects.create(
            template_id=template_id,
            crm_connection_id=conn_id,
            variable_key=item['variable_key'],
            crm_field_path=item['crm_field_path'],
        )
        created += 1
    return {'created': created}


@documents_router.get('/')
def list_documents(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'documents')
    qs = Document.objects.select_related('template', 'created_by', 'deal__contact').order_by('-created_at')
    from .models import SigningSession
    session_map = {}
    for s in SigningSession.objects.filter(document__in=qs).order_by('document_id', '-otp_sent_at'):
        if s.document_id not in session_map:
            session_map[s.document_id] = s.token
    base_url = f'{request.scheme}://{request.get_host()}'
    return [
        {
            'id': d.id,
            'document_type': d.document_type,
            'template_name': d.template.name if d.template else None,
            'status': d.status,
            'signing_method': d.signing_method,
            'created_at': d.created_at.isoformat(),
            'signed_at': d.signed_at.isoformat() if d.signed_at else None,
            'crm_entity_type': d.crm_entity_type,
            'crm_entity_id': d.crm_entity_id,
            'contact_phone': d.deal.contact.phone if d.deal and d.deal.contact else '',
            'signing_url': f'{base_url}/sign/{session_map[d.id]}/' if d.id in session_map else None,
        }
        for d in qs
    ]


@documents_router.post('/generate', response={200: dict, 400: dict})
def generate_document(request, payload: DocumentGenerateIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'documents')
    tenant = get_request_tenant(request)
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_documents = Document.objects.filter(created_at__gte=month_start).count()
    if not check_limit(tenant, 'max_documents_per_month', monthly_documents):
        return 400, {'detail': 'Documents monthly limit reached'}
    template = DocumentTemplate.objects.get(id=payload.template_id)

    if payload.deal_id:
        deal = Deal.objects.get(id=payload.deal_id)
        document = create_document_from_deal(deal, template, created_by=request.auth)
    else:
        data = payload.filled_data or {}
        html = Template(template.html_body).render(Context(data))
        pdf = HTML(string=html).write_pdf()
        pdf_hash = hashlib.sha256(pdf).hexdigest()
        document = Document(
            template=template,
            template_version=template.version,
            document_type=template.document_type,
            crm_entity_type='manual',
            crm_entity_id='manual',
            filled_data=data,
            html_snapshot=html,
            signing_method=payload.signing_method,
            created_by=request.auth,
            pdf_hash=pdf_hash,
        )
        document.pdf_file.save('manual_document.pdf', ContentFile(pdf), save=False)
        document.save()
    return {'id': document.id}


@documents_router.get('/{document_id}/')
def get_document(request, document_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'documents')
    d = Document.objects.get(id=document_id)
    return {
        'id': d.id,
        'document_type': d.document_type,
        'status': d.status,
        'signing_method': d.signing_method,
        'filled_data': d.filled_data,
        'html_snapshot': d.html_snapshot,
        'crm_entity_type': d.crm_entity_type,
        'crm_entity_id': d.crm_entity_id,
        'pdf_hash': d.pdf_hash,
        'signature_data': d.signature_data,
        'signed_at': d.signed_at.isoformat() if d.signed_at else None,
        'created_at': d.created_at.isoformat(),
    }


@documents_router.get('/{document_id}/pdf/', auth=None)
def get_document_pdf(request, document_id: int):
    # Auth via ?token= query param (window.open() can't send Authorization header)
    query_token = request.GET.get('token')
    if not query_token:
        raise HttpError(401, 'Token required')
    from apps.users.models import User
    from ninja_jwt.exceptions import TokenError
    from ninja_jwt.tokens import AccessToken
    try:
        validated = AccessToken(query_token)
        request.auth = User.objects.get(id=validated['user_id'])
    except (TokenError, User.DoesNotExist, KeyError):
        raise HttpError(401, 'Invalid token')
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'documents')
    document = Document.objects.get(id=document_id)
    if not document.pdf_file:
        raise HttpError(404, 'PDF not found')
    return FileResponse(document.pdf_file.open('rb'), filename=f'document_{document.id}.pdf')


@documents_router.post('/{document_id}/send-for-signing/')
def send_document_for_signing(request, document_id: int, payload: SendForSigningIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'document_signing')
    document = Document.objects.get(id=document_id)
    session = send_for_signing(document, payload.recipient)
    signing_url = f'{request.scheme}://{request.get_host()}/sign/{session.token}/'
    return {'detail': 'sent', 'token': str(session.token), 'signing_url': signing_url}


class VerifySigningIn(Schema):
    code: str


@documents_router.post('/{document_id}/verify-signing/')
def verify_document_signing(request, document_id: int, payload: VerifySigningIn):
    """Verify OTP code for a sent document (from CRM UI)."""
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'document_signing')
    document = Document.objects.get(id=document_id)
    session = document.signing_sessions.order_by('-otp_sent_at').first()
    if not session:
        raise HttpError(400, 'No signing session found')

    from .services import verify_signing as _verify, SigningError
    try:
        result = _verify(str(session.token), payload.code, request.META.get('REMOTE_ADDR'), request.META.get('HTTP_USER_AGENT'))
    except SigningError as exc:
        raise HttpError(400, str(exc))
    return {'detail': 'ok', 'status': result.status}
