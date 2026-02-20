import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as authApi from '@/api/auth'
import { getStoredToken, setStoredToken } from '@/api/client'
import type { User } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getStoredToken())
  const user = ref<User | null>(null)

  async function fetchUser(): Promise<User | null> {
    if (!token.value) return null
    try {
      const u = await authApi.me()
      user.value = u
      return u
    } catch {
      token.value = null
      setStoredToken(null)
      user.value = null
      return null
    }
  }

  async function login(email: string, password: string): Promise<void> {
    await authApi.login({ email, password })
    token.value = getStoredToken()
    await fetchUser()
  }

  function logout(): void {
    token.value = null
    user.value = null
    setStoredToken(null)
  }

  return { token, user, fetchUser, login, logout }
})
