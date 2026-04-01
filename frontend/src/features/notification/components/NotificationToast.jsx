import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { MessageSquare, Users, FileText, ShieldAlert, Trash2, Check, Loader2, UserMinus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { acceptInvite, declineInvite } from '@/api/groups'
import { useNotification } from '../context/NotificationContext'

export default function NotificationToast({ notification, onNavigate, onClose }) {
  const { notifications, updateInviteStatus, markAsRead } = useNotification()
  const [isLoading, setIsLoading] = useState(false)

  const currentNotification = notifications.find(n => n.id === notification.id) || notification
  const status = currentNotification.inviteStatus
  
  const type = notification.notification_type || notification.type
  const isInvite = type === 'WORKSPACE_INVITED'

  const handleAccept = async (e) => {
    e.stopPropagation()
    setIsLoading(true)
    try {
      if (notification.target_id) {
        await acceptInvite(notification.target_id)
      }
      updateInviteStatus(notification.id, 'accepted')
      await markAsRead(notification.id)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReject = async (e) => {
    e.stopPropagation()
    setIsLoading(true)
    try {
      if (notification.target_id) {
        await declineInvite(notification.target_id)
      }
      updateInviteStatus(notification.id, 'rejected')
      await markAsRead(notification.id)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClick = () => {
    if (isInvite && status !== 'accepted') return
    if (onNavigate) onNavigate()
  }

  const getTheme = () => {
    switch (type) {
      case 'AI_ANSWER_COMPLETE': return { color: 'blue', label: 'AI 답변 완료', icon: MessageSquare }
      case 'WORKSPACE_INVITED': return { color: 'green', label: '워크스페이스 초대', icon: Users }
      case 'DOCUMENT_UPLOAD_REQUESTED': return { color: 'orange', label: '문서 검토 요청', icon: FileText }
      case 'WORKSPACE_KICKED': return { color: 'red', label: '워크스페이스 추방', icon: UserMinus }
      case 'WORKSPACE_DELETE_NOTICE': return { color: 'red', label: '워크스페이스 삭제 알림', icon: ShieldAlert }
      case 'DOCUMENT_DELETED': return { color: 'zinc', label: '문서 삭제 알림', icon: Trash2 }
      default: return { color: 'zinc', label: '새로운 알림', icon: MessageSquare }
    }
  }

  const theme = getTheme()
  const Icon = theme.icon

  const colorStyles = {
    blue: { border: 'bg-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/30', text: 'text-blue-500' },
    green: { border: 'bg-green-500', bg: 'bg-green-50 dark:bg-green-900/30', text: 'text-green-500' },
    orange: { border: 'bg-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/30', text: 'text-orange-500' },
    red: { border: 'bg-red-500', bg: 'bg-red-50 dark:bg-red-900/30', text: 'text-red-500' },
    zinc: { border: 'bg-zinc-500', bg: 'bg-zinc-50 dark:bg-zinc-800/30', text: 'text-zinc-500' }
  }

  const style = colorStyles[theme.color] || colorStyles.zinc

  return (
    <div 
      className={cn(
        "flex w-[380px] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl overflow-hidden transition-all",
        (isInvite && status !== 'accepted') ? "cursor-default" : "cursor-pointer hover:scale-[1.01]"
      )}
      onClick={handleClick}
    >
      <div className={cn("w-1.5", style.border)} />
      <div className="flex-1 p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className={cn("flex items-center justify-center w-6 h-6 rounded-full", style.bg)}>
            <Icon size={12} className={style.text} />
          </div>
          <span className="text-xs font-black text-zinc-900 dark:text-zinc-100">
            {theme.label}
          </span>
          <button 
            className="ml-auto text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1"
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
          >
            <svg size={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        
        <div className="text-[13px] font-bold text-zinc-800 dark:text-zinc-200 mb-1 leading-tight">
          {notification.title}
        </div>
        
        <div className="text-[11px] text-zinc-500 dark:text-zinc-400 line-clamp-2 leading-relaxed opacity-80">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {notification.body}
          </ReactMarkdown>
        </div>

        {isInvite && !status && (
          <div className="flex gap-2 mt-3">
            <Button size="sm" className="h-7 text-[10px] bg-blue-600 hover:bg-blue-700 text-white font-black px-4 rounded-lg shadow-sm" onClick={handleAccept} disabled={isLoading}>
              {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : '승인'}
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-[10px] font-bold border-zinc-200 dark:border-zinc-700 px-4 rounded-lg" onClick={handleReject} disabled={isLoading}>거절</Button>
          </div>
        )}
        
        {status === 'accepted' && (
          <div className="flex items-center gap-1 mt-2">
            <Check size={10} className="text-blue-600" />
            <p className="text-[10px] text-blue-600 font-black">승인 완료</p>
          </div>
        )}
        
        {status === 'rejected' && (
          <p className="text-[10px] text-red-500 font-black mt-2">✕ 거절됨</p>
        )}

        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-2 font-medium">
          {notification.displayTime}
        </p>
      </div>
    </div>
  )
}