import client from '@/api/client'

export async function uploadDocumentApi(file, groupId, assigneeUserId, signal) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('group_id', String(groupId))

  if (assigneeUserId != null) {
    formData.append('assignee_user_id', String(assigneeUserId))
  }

  const { data } = await client.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal,
  })
  return data
}
