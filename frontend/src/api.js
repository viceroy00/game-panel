import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
})

// 응답 인터셉터: 401 시 토큰 갱신 시도
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true

      const refreshToken = sessionStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const res = await axios.post('/api/auth/refresh', null, {
            params: { refresh_token: refreshToken },
          })
          const { access_token, refresh_token } = res.data
          sessionStorage.setItem('access_token', access_token)
          sessionStorage.setItem('refresh_token', refresh_token)
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
          error.config.headers['Authorization'] = `Bearer ${access_token}`
          return api(error.config)
        } catch {
          sessionStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
