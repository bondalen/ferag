import { apiClient } from './client'

export interface UploadResponse {
  cycle_id: number
  task_id: number
}

export interface UploadStatusResponse {
  cycle_in_review: { cycle_id: number; task_id: number } | null
}

export function getUploadStatus(ragId: number): Promise<UploadStatusResponse> {
  return apiClient.get<UploadStatusResponse>(`/rags/${ragId}/upload-status`).then((r) => r.data)
}

export function uploadFile(ragId: number, file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return apiClient
    .post<UploadResponse>(`/rags/${ragId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}
