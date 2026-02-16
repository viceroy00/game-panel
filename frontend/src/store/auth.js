import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(sessionStorage.getItem('access_token') || '')
  const refreshToken = ref(sessionStorage.getItem('refresh_token') || '')
  const user = ref(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  function setTokens(access, refresh) {
    accessToken.value = access
    refreshToken.value = refresh
    sessionStorage.setItem('access_token', access)
    sessionStorage.setItem('refresh_token', refresh)
    api.defaults.headers.common['Authorization'] = `Bearer ${access}`
  }

  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('refresh_token')
    delete api.defaults.headers.common['Authorization']
  }

  async function fetchUser() {
    try {
      const res = await api.get('/api/auth/me')
      user.value = res.data
    } catch {
      logout()
    }
  }

  // 초기화 시 토큰이 있으면 헤더 설정
  if (accessToken.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken.value}`
  }

  return { accessToken, refreshToken, user, isAuthenticated, setTokens, logout, fetchUser }
})
