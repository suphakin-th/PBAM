import { create } from 'zustand'
import type { User } from '@/domain/identity'
import { authApi } from '@/infrastructure/api/auth'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (usernameOrEmail: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('pbam_access_token'),
  isLoading: false,

  initialize: async () => {
    const token = localStorage.getItem('pbam_access_token')
    if (token) {
      set({ token })
      await get().fetchMe()
    }
  },

  login: async (usernameOrEmail, password) => {
    set({ isLoading: true })
    try {
      const { data } = await authApi.login(usernameOrEmail, password)
      localStorage.setItem('pbam_access_token', data.access_token)
      set({ token: data.access_token })
      await get().fetchMe()
    } finally {
      set({ isLoading: false })
    }
  },

  register: async (email, username, password) => {
    set({ isLoading: true })
    try {
      const { data } = await authApi.register(email, username, password)
      localStorage.setItem('pbam_access_token', data.access_token)
      set({ token: data.access_token })
      await get().fetchMe()
    } finally {
      set({ isLoading: false })
    }
  },

  logout: async () => {
    try {
      await authApi.logout()
    } finally {
      localStorage.removeItem('pbam_access_token')
      set({ user: null, token: null })
    }
  },

  fetchMe: async () => {
    try {
      const { data } = await authApi.me()
      set({ user: data })
    } catch {
      localStorage.removeItem('pbam_access_token')
      set({ user: null, token: null })
    }
  },
}))
