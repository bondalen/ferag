import { apiClient } from './client'

export interface Task {
  id: number
  rag_id: number
  cycle_id: number | null
  type: string
  status: string
  error: string | null
  created_at: string
  updated_at: string
}

export function getTask(taskId: number): Promise<Task> {
  return apiClient.get<Task>(`/tasks/${taskId}`).then((r) => r.data)
}
