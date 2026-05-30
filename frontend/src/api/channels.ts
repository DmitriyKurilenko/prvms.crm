import { api } from './http'

export async function startVkOauth(): Promise<{ authorize_url: string; state: string }> {
  return api('/channels/oauth/vk/start/', { method: 'POST' })
}

export async function completeVkOauth(payload: {
  state: string
  tokens: Array<{ group_id: number; access_token: string }>
}): Promise<{ created: any[]; failed: any[] }> {
  return api('/channels/oauth/vk/complete/', { method: 'POST', body: payload })
}
