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

export interface ChatSessionListItem {
  id: number
  title: string | null
  created_at: string
}

export function sendQuestion(
  ragId: number,
  question: string,
  sessionId?: number | null
): Promise<ChatResponse> {
  const body = sessionId != null ? { question, session_id: sessionId } : { question }
  return apiClient.post<ChatResponse>(`/rags/${ragId}/chat`, body).then((r) => r.data)
}

export function getChatMessages(
  ragId: number,
  sessionId?: number | null,
  limit?: number,
  offset?: number
): Promise<ChatMessageItem[]> {
  const params = new URLSearchParams()
  if (sessionId != null) params.set('session_id', String(sessionId))
  if (limit != null) params.set('limit', String(limit))
  if (offset != null) params.set('offset', String(offset))
  const query = params.toString()
  const url = `/rags/${ragId}/chat/messages${query ? `?${query}` : ''}`
  return apiClient.get<ChatMessageItem[]>(url).then((r) => r.data)
}

export function getSessions(ragId: number): Promise<ChatSessionListItem[]> {
  return apiClient.get<ChatSessionListItem[]>(`/rags/${ragId}/chat/sessions`).then((r) => r.data)
}

export function createSession(
  ragId: number,
  title?: string | null
): Promise<{ id: number; rag_id: number; user_id: number; title: string | null; created_at: string }> {
  const body = title != null && title !== '' ? { title } : {}
  return apiClient
    .post<{ id: number; rag_id: number; user_id: number; title: string | null; created_at: string }>(
      `/rags/${ragId}/chat/sessions`,
      body
    )
    .then((r) => r.data)
}

export function getSessionMessages(
  ragId: number,
  sessionId: number,
  limit?: number,
  offset?: number
): Promise<ChatMessageItem[]> {
  const params = new URLSearchParams()
  if (limit != null) params.set('limit', String(limit))
  if (offset != null) params.set('offset', String(offset))
  const query = params.toString()
  const url = `/rags/${ragId}/chat/sessions/${sessionId}/messages${query ? `?${query}` : ''}`
  return apiClient.get<ChatMessageItem[]>(url).then((r) => r.data)
}

export function updateSession(
  ragId: number,
  sessionId: number,
  title: string | null
): Promise<ChatSessionListItem> {
  return apiClient
    .patch<ChatSessionListItem>(`/rags/${ragId}/chat/sessions/${sessionId}`, { title })
    .then((r) => r.data)
}

export function deleteSession(ragId: number, sessionId: number): Promise<void> {
  return apiClient.delete(`/rags/${ragId}/chat/sessions/${sessionId}`).then(() => undefined)
}
