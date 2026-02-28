import { apiClient } from './client'
import type { TokenResponse, User } from '@/domain/identity'

export const authApi = {
  register: (email: string, username: string, password: string) =>
    apiClient.post<TokenResponse>('/auth/register', { email, username, password }),

  login: (username_or_email: string, password: string) =>
    apiClient.post<TokenResponse>('/auth/login', { username_or_email, password }),

  logout: () => apiClient.post('/auth/logout'),

  me: () => apiClient.get<User>('/auth/me'),
}
