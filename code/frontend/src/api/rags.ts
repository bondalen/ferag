import { apiClient } from './client'

export interface Rag {
  id: number
  owner_id: number
  name: string
  description: string | null
  fuseki_dataset: string
  cycle_count: number
  created_at: string
}

export function listRags(): Promise<Rag[]> {
  return apiClient.get<Rag[]>('/rags').then((r) => r.data)
}

export function createRag(data: { name: string; description?: string }): Promise<Rag> {
  return apiClient.post<Rag>('/rags', data).then((r) => r.data)
}

export function getRag(id: number): Promise<Rag> {
  return apiClient.get<Rag>(`/rags/${id}`).then((r) => r.data)
}

export function deleteRag(id: number): Promise<void> {
  return apiClient.delete(`/rags/${id}`).then(() => undefined)
}
