import { apiClient } from './client'

export interface ChatResponse {
  answer: string
  context_used: number
}

export interface ChatMessageItem {
  id: number
  role: string
  content: string
  context_used?: number | null
  created_at?: string
}

export function sendQuestion(ragId: number, question: string): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/rags/${ragId}/chat`, { question }).then((r) => r.data)
}

export function getChatMessages(
  ragId: number,
  limit?: number,
  offset?: number
): Promise<ChatMessageItem[]> {
  const params = new URLSearchParams()
  if (limit != null) params.set('limit', String(limit))
  if (offset != null) params.set('offset', String(offset))
  const query = params.toString()
  const url = `/rags/${ragId}/chat/messages${query ? `?${query}` : ''}`
  return apiClient.get<ChatMessageItem[]>(url).then((r) => r.data)
}
