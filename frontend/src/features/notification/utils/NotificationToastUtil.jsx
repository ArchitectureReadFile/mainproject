import { toast } from 'sonner'
import NotificationToast from '../components/NotificationToast'

export const showNotificationToast = (notification, onNavigate, onUpdateStatus, markAsRead, user = null) => {
  if (user && user.is_notification_enabled === false) {
    return
  }

  toast.custom((t) => (
    <NotificationToast
      notification={notification}
      onNavigate={() => {
        if (onNavigate) onNavigate(notification)
        toast.dismiss(t)
      }}
      onUpdateStatus={(id, status) => {
        if (onUpdateStatus) onUpdateStatus(id, status)
      }}
      onMarkAsRead={async (id) => {
        if (markAsRead) await markAsRead(id)
      }}
      onClose={() => toast.dismiss(t)}
    />
  ), {
    position: 'bottom-right',
    duration: 30000,
  })
}