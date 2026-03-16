import client from '@/api/client'

export async function loginApi(email, password) {
  const response = await client.post('/auth/login', { email, password })
  return response.data
}

export async function signupApi(username, email, password) {
  return client.post('/auth/signup', { username, email, password }).then((res) => res.data)
}

export async function logoutApi() {
  await client.post('/auth/logout')
}

export function meApi() {
  return client.get('/auth/me').then((res) => res.data)
}

export const confirmAccount = async (email) => {
  const response = await client.post('/auth/confirm-account', { email })
  return response.data
}

export const resetPassword = async (email, newPassword) => {
  const response = await client.post('/auth/reset-password', { email, new_password: newPassword })
  return response.data
}

export async function updateAccountApi({ username, currentPassword, newPassword, avatarFile }) {
  const formData = new FormData()
  if (username) formData.append('username', username)
  if (currentPassword && newPassword) {
    formData.append('currentPassword', currentPassword)
    formData.append('newPassword', newPassword)
  }
  if (avatarFile) formData.append('avatar', avatarFile)

  const headers = avatarFile
    ? { 'Content-Type': 'multipart/form-data' }
    : { 'Content-Type': 'application/json' }

  const response = await client.patch(
    '/auth/account-settings',
    avatarFile ? formData : { username, currentPassword, newPassword },
    { headers }
  )
  return response.data
}