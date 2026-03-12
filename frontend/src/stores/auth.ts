import { defineStore } from 'pinia'
import apiClient from '@/api/client'

interface UserMe {
  id: number
  username: string
  full_name: string | null
  email: string | null
  role: 'admin' | 'operator'
  is_active: boolean
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserMe | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: localStorage.getItem('access_token'),
    refreshToken: localStorage.getItem('refresh_token'),
    user: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    isAdmin: (state) => state.user?.role === 'admin',
  },

  actions: {
    async login(username: string, password: string) {
      const { data } = await apiClient.post('/auth/login', { username, password })
      this.accessToken = data.access_token
      this.refreshToken = data.refresh_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      await this.fetchMe()
    },

    async fetchMe() {
      const { data } = await apiClient.get('/auth/me')
      this.user = data
    },

    async logout() {
      try {
        await apiClient.post('/auth/logout')
      } catch {
        // ignore errors on logout
      } finally {
        this.accessToken = null
        this.refreshToken = null
        this.user = null
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    },
  },
})
