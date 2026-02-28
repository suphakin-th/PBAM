/** TypeScript interfaces for the identity domain. */

export interface User {
  id: string
  email: string
  username: string
  is_active: boolean
  is_verified: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_at: string
}
