import axios from 'axios'
import { ERROR_CODE } from '@/shared/lib/errors'

const client = axios.create({
  baseURL: `/api`,
  withCredentials: true,
})

const extractErrorCode = (error) => {
  return error.response?.data?.code ?? null
}

const parseAxiosError = (error, fallback) => {
  const payload = error.response?.data
  if (!payload) return fallback
  if (typeof payload === 'string') return payload
  if (typeof payload.message === 'string') return payload.message
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail
      .map((item) => (typeof item === 'string' ? item : item?.msg))
      .filter(Boolean)
    if (messages.length > 0) return messages.join(' / ')
  }
  return fallback
}

const tryRefreshToken = async (originalRequest) => {
  originalRequest._retry = true
  try {
    await axios.post(`/api/auth/refresh`, {}, { withCredentials: true })
    return client(originalRequest)
  } catch {
    window.location.href = '/'
    return Promise.reject(new Error('세션이 만료되었습니다. 다시 로그인해주세요.'))
  }
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const code = extractErrorCode(error)
    const isAuthEndpoint =
      originalRequest.url.includes('/auth/login') ||
      originalRequest.url.includes('/auth/refresh') ||
      originalRequest.url.includes('/auth/me')

    if (
      !originalRequest._retry &&
      !isAuthEndpoint &&
      (code === ERROR_CODE.AUTH_TOKEN_MISSING || code === ERROR_CODE.AUTH_TOKEN_INVALID)
    ) {
      return tryRefreshToken(originalRequest)
    }

    if (
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_EXPIRED ||
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_INVALID ||
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_MISSING
    ) {
      window.location.href = '/'
      return Promise.reject(new Error('세션이 만료되었습니다. 다시 로그인해주세요.'))
    }

    const fallback = originalRequest.url.includes('/auth/login')
      ? '로그인에 실패했습니다.'
      : '요청에 실패했습니다.'

    const message = parseAxiosError(error, fallback)
    const err = new Error(message)
    err.code = code
    return Promise.reject(err)
  },
)

export default client
