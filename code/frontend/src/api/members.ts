import { apiClient } from './client'

export interface MemberListItem {
  user_id: number
  email: string
  display_name: string | null
  role: string
}

export interface MemberResponse {
  user_id: number
  email: string
  role: string
}

export function listMembers(ragId: number): Promise<MemberListItem[]> {
  return apiClient.get<MemberListItem[]>(`/rags/${ragId}/members`).then((r) => r.data)
}

export function addMember(
  ragId: number,
  data: { email: string; role: 'viewer' | 'editor' }
): Promise<MemberResponse> {
  return apiClient.post<MemberResponse>(`/rags/${ragId}/members`, data).then((r) => r.data)
}

export function removeMember(ragId: number, userId: number): Promise<void> {
  return apiClient.delete(`/rags/${ragId}/members/${userId}`).then(() => undefined)
}
