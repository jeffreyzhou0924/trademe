export interface User {
  id: string
  username: string
  email: string
  phone?: string
  avatar_url?: string
  membership_level: 'basic' | 'premium' | 'professional'
  membership_expires_at?: string
  email_verified: boolean
  is_active: boolean
  last_login_at?: string
  created_at: string
  updated_at: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData {
  username: string
  email: string
  password: string
  confirmPassword: string
}

export interface LoginResponse {
  user: User
  token: string
  refresh_token?: string
}

export interface TokenPayload {
  user_id: string
  email: string
  username: string
  membership_level: string
  exp: number
}