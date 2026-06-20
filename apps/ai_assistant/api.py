from __future__ import annotations

from typing import Optional

from django.utils import timezone
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_membership
from apps.core.tenant import get_request_tenant

from .models import AIConversation, AIMessage
from .services import send_to_hermes

ai_router = Router(tags=['ai_assistant'], auth=JWTAuth())


class ChatMessageIn(Schema):
    content: str
    conversation_id: Optional[int] = None
    channel_id: Optional[int] = None
    deal_id: Optional[int] = None


class ChatMessageOut(Schema):
    conversation_id: int
    message_id: int
    content: str
    role: str


@ai_router.post('/chat/')
def chat(request, payload: ChatMessageIn):
    require_membership(request)
    tenant = get_request_tenant(request)
    user = request.user

    conversation = None
    if payload.conversation_id:
        with schema_context(tenant.schema_name):
            conversation = AIConversation.objects.filter(
                id=payload.conversation_id,
                user=user,
            ).first()

    if not conversation:
        with schema_context(tenant.schema_name):
            conversation = AIConversation.objects.create(
                user=user,
                channel_id=payload.channel_id,
                deal_id=payload.deal_id,
                title=payload.content[:100] if payload.content else 'Новый диалог',
            )

    with schema_context(tenant.schema_name):
        AIMessage.objects.create(
            conversation=conversation,
            role='user',
            content=payload.content,
        )

    context_data = {}
    if payload.channel_id:
        from apps.channels.models import ChatSession
        with schema_context(tenant.schema_name):
            session = ChatSession.objects.filter(id=payload.channel_id).first()
            if session and session.crm_lead_id:
                context_data['chat_session_id'] = str(session.id)
                context_data['crm_lead_id'] = session.crm_lead_id
                if session.crm_contact_id:
                    context_data['crm_contact_id'] = session.crm_contact_id

    if payload.deal_id:
        context_data['deal_id'] = str(payload.deal_id)

    ai_content = send_to_hermes(
        tenant=tenant,
        user=user,
        message=payload.content,
        conversation_id=str(conversation.id),
        context=context_data,
    )

    ai_message = None
    with schema_context(tenant.schema_name):
        ai_message = AIMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_content,
        )

        conversation.updated_at = timezone.now()
        conversation.save()

    return {
        'conversation_id': conversation.id,
        'message_id': ai_message.id,
        'content': ai_content,
        'role': 'assistant',
    }


@ai_router.get('/conversations/')
def list_conversations(request):
    require_membership(request)
    tenant = get_request_tenant(request)

    with schema_context(tenant.schema_name):
        conversations = AIConversation.objects.filter(
            user=request.user,
        ).order_by('-updated_at')

    return [
        {
            'id': c.id,
            'title': c.title,
            'channel_id': c.channel_id,
            'deal_id': c.deal_id,
            'created_at': c.created_at.isoformat(),
            'updated_at': c.updated_at.isoformat(),
            'message_count': c.messages.count(),
        }
        for c in conversations
    ]


@ai_router.get('/conversations/{conversation_id}/messages/')
def get_messages(request, conversation_id: int):
    require_membership(request)
    tenant = get_request_tenant(request)

    with schema_context(tenant.schema_name):
        conversation = AIConversation.objects.filter(
            id=conversation_id,
            user=request.user,
        ).first()

        if not conversation:
            raise HttpError(404, 'Conversation not found')

        messages = conversation.messages.order_by('created_at')

    return [
        {
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
        }
        for m in messages
    ]


@ai_router.delete('/conversations/{conversation_id}/')
def delete_conversation(request, conversation_id: int):
    require_membership(request)
    tenant = get_request_tenant(request)

    with schema_context(tenant.schema_name):
        conversation = AIConversation.objects.filter(
            id=conversation_id,
            user=request.user,
        ).first()

        if not conversation:
            raise HttpError(404, 'Conversation not found')

        conversation.delete()

    return {'status': 'ok'}


@ai_router.post('/conversations/{conversation_id}/title/')
def update_title(request, conversation_id: int, payload: dict):
    require_membership(request)
    tenant = get_request_tenant(request)

    with schema_context(tenant.schema_name):
        conversation = AIConversation.objects.filter(
            id=conversation_id,
            user=request.user,
        ).first()

        if not conversation:
            raise HttpError(404, 'Conversation not found')

        conversation.title = payload.get('title', '')
        conversation.save()

    return {'status': 'ok'}