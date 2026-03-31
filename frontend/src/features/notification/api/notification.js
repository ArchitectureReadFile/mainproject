import client from '../../../api/client'

export const getNotifications = (skip = 0, limit = 20) => {
  return client.get(`/notifications`, { params: { skip, limit } })
}

export const markAsRead = (id) => {
  return client.patch(`/notifications/${id}/read`)
}

export const markAllAsRead = () => {
  return client.patch(`/notifications/read-all`)
}

export const deleteNotification = (id) => {
  return client.delete(`/notifications/${id}`)
}