/** Axios HTTP client with JWT auth interceptor. */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach Bearer token from localStorage on every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('pbam_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401, clear token and redirect to login
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pbam_access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)
