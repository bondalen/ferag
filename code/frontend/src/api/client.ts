/**
 * Axios instance: baseURL /ferag/api/, JWT interceptor.
 */
import axios from 'axios'

const TOKEN_KEY = 'ferag_token'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export const apiClient = axios.create({
  baseURL: '/ferag/api',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      setStoredToken(null)
    }
    return Promise.reject(err)
  }
)
