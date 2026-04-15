import client from '@/shared/api/client'

export const sendVerificationCode = async (email) => {
  const response = await client.post('/email/send-verification-code', { email })
  return response.data
}

export const verifyCode = async (email, code) => {
  const response = await client.post('/email/verify-code', { email, code })
  return response.data
}
