import { apiClient, setStoredToken } from './client'

export interface User {
  id: number
  email: string
  display_name: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export function register(data: { email: string; password: string; display_name?: string }): Promise<User> {
  return apiClient.post<User>('/auth/register', data).then((r) => r.data)
}

export function login(data: { email: string; password: string }): Promise<TokenResponse> {
  return apiClient.post<TokenResponse>('/auth/login', data).then((r) => {
    setStoredToken(r.data.access_token)
    return r.data
  })
}

export function me(): Promise<User> {
  return apiClient.get<User>('/auth/me').then((r) => r.data)
}
