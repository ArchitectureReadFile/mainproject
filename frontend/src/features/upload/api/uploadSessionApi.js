import client from '@/api/client'

export async function createUploadSessionApi(fileNames) {
  const { data } = await client.post('/documents/upload-session', {
    file_names: fileNames,
  })
  return data
}

export async function getUploadSessionApi() {
  const { data } = await client.get('/documents/upload-session')
  return data
}

export async function abandonUploadSessionApi() {
  const { data } = await client.post('/documents/upload-session/abandon')
  return data
}

export async function abandonUploadSessionKeepaliveApi() {
  return fetch('/api/documents/upload-session/abandon', {
    method: 'POST',
    credentials: 'include',
    keepalive: true,
  })
}

export async function clearUploadSessionApi() {
  await client.delete('/documents/upload-session')
}

export async function uploadDocumentApi(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getDocumentDetailApi(docId) {
  const { data } = await client.get('/documents/' + docId)
  return data
}