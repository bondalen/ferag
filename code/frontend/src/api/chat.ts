import { apiClient } from './client'

export interface ChatResponse {
  answer: string
  context_used: number
}

export function sendQuestion(ragId: number, question: string): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/rags/${ragId}/chat`, { question }).then((r) => r.data)
}
