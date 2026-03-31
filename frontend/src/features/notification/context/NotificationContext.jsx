import { createContext, useContext } from 'react'
import { useNotification as useNotificationSource } from '../hooks/useNotification'

const NotificationContext = createContext()

export const NotificationProvider = ({ children }) => {
  const notificationValues = useNotificationSource()

  return (
    <NotificationContext.Provider value={notificationValues}>
      {children}
    </NotificationContext.Provider>
  )
}

export const useNotification = () => {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider')
  }
  return context
}
