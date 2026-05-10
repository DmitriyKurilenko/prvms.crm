import { getAccessToken, getTenantSlug } from './http'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'

interface ConversationSummary {
  id: number
  title: string
  channel_id: number | null
  deal_id: number | null
  created_at: string
  updated_at: string
  message_count: number
}

interface AIMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

interface SendMessagePayload {
  content: string
  conversation_id?: number
  channel_id?: number
  deal_id?: number
}

interface SendMessageResponse {
  conversation_id: number
  message_id: number
  content: string
  role: string
}

async function fetchApi(
  path: string,
  options: RequestInit = {}
): Promise<any> {
  const token = getAccessToken()
  const slug = getTenantSlug()

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (slug) {
    headers['X-Tenant-Slug'] = slug
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

export async function listConversations(): Promise<ConversationSummary[]> {
  return fetchApi('/ai/conversations/')
}

export async function getMessages(conversationId: number): Promise<AIMessage[]> {
  return fetchApi(`/ai/conversations/${conversationId}/messages/`)
}

export async function sendMessage(payload: SendMessagePayload): Promise<SendMessageResponse> {
  return fetchApi('/ai/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await fetchApi(`/ai/conversations/${conversationId}/`, { method: 'DELETE' })
}

export async function updateTitle(conversationId: number, title: string): Promise<void> {
  await fetchApi(`/ai/conversations/${conversationId}/title/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}