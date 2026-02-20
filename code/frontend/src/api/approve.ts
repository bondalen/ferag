import { apiClient } from './client'

export interface ApproveResponse {
  message: string
}

export function approveCycle(ragId: number, cycleId: number): Promise<ApproveResponse> {
  return apiClient.post<ApproveResponse>(`/rags/${ragId}/cycles/${cycleId}/approve`).then((r) => r.data)
}
