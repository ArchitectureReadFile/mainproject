import client from '@/shared/api/client'

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

export const deactivateAccount = async () => {
  const response = await client.delete('/auth/deactivate')
  return response.data
}

export const reactivateAccount = async (credentials) => {
  const response = await client.post("/auth/reactivate", credentials);
  return response.data;
};

export const updatePassword = async (data) => {
  await client.patch("/auth/password", data);
};

export const updateUsername = async (newUsername) => {
  const response = await client.patch("/auth/username", { new_username: newUsername });
  return response.data;
}

export const subscribePremium =  async () => {
  const response = await client.post('/auth/subscription/subscribe', { confirm: true })
  return response.data
}

export const cancelSubscription = async () => {
  const response = await client.post('/auth/subscription/cancel', { confirm: true })
  return response.data
}

export const unlinkSocialAccount = async (provider) => {
  const response = await client.delete(`/auth/social/${provider}/unlink`)
  return response.data
}
