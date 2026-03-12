import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with null state', () => {
    const store = useAuthStore()
    expect(store.accessToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('can set token and user', () => {
    const store = useAuthStore()
    store.accessToken = 'fake-token'
    store.user = {
      id: 1,
      username: 'testuser',
      full_name: 'Test User',
      email: 'test@example.com',
      role: 'admin',
      is_active: true
    }
    
    expect(store.isAuthenticated).toBe(true)
    expect(store.user.role).toBe('admin')
    expect(store.isAdmin).toBe(true)
  })

  it('logout clears state', async () => {
    const store = useAuthStore()
    store.accessToken = 'fake-token'
    store.user = {
      id: 1,
      username: 'test',
      full_name: 'Test',
      email: 'test@example.com',
      role: 'operator',
      is_active: true
    }

    // Mock API client since logout calls api
    vi.mock('@/api/client', () => ({
      default: {
        post: vi.fn().mockResolvedValue({})
      }
    }))

    await store.logout()

    expect(store.accessToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })
})
