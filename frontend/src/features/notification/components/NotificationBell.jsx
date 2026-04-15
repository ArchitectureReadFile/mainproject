import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Bell, Check, X, Loader2, MessageSquare, Users, FileText, FileCheck, ShieldAlert, Trash2, AtSign, UserCheck, ShieldCheck } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNotification } from '../context/NotificationContext'
import { cn } from '@/lib/utils'
import { acceptInvite, declineInvite } from '@/api/groups'

export default function NotificationBell() {
  const {
    notifications, unreadCount, markAllAsRead, handleNavigate,
    deleteNotification, loadMoreNotifications, hasMore, isLoadingMore,
    markAsRead, updateInviteStatus
  } = useNotification()

  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const [isActionLoading, setIsActionLoading] = useState({})
  const menuRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop <= clientHeight + 10) {
      if (hasMore && !isLoadingMore) {
        loadMoreNotifications();
      }
    }
  };

  const handleAccept = async (e, n) => {
    e.stopPropagation()
    setIsActionLoading(prev => ({ ...prev, [n.id]: true }))
    try {
      if (n.target_id) {
        await acceptInvite(n.target_id)
      }
      updateInviteStatus(n.id, 'accepted')
      await markAsRead(n.id)
    } catch (error) {
      console.error(error)
    } finally {
      setIsActionLoading(prev => ({ ...prev, [n.id]: false }))
    }
  }

  const handleReject = async (e, n) => {
    e.stopPropagation()
    setIsActionLoading(prev => ({ ...prev, [n.id]: true }))
    try {
      if (n.target_id) {
        await declineInvite(n.target_id)
      }
      updateInviteStatus(n.id, 'rejected')
      await markAsRead(n.id)
    } catch (error) {
      console.error(error)
    } finally {
      setIsActionLoading(prev => ({ ...prev, [n.id]: false }))
    }
  }

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'AI_ANSWER_COMPLETE':
        return <MessageSquare size={14} className="text-blue-500" />
      case 'WORKSPACE_INVITED':
        return <Users size={14} className="text-green-500" />
      case 'WORKSPACE_MEMBER_UPDATE':
        return <UserCheck size={14} className="text-green-500" />
      case 'DOCUMENT_UPLOAD_REQUESTED':
        return <FileText size={14} className="text-orange-500" />
      case 'WORKSPACE_DELETE_NOTICE':
        return <ShieldAlert size={14} className="text-red-500" />
      case 'DOCUMENT_DELETED':
        return <Trash2 size={14} className="text-zinc-500" />
      case 'COMMENT_MENTIONED':
        return <AtSign size={14} className="text-purple-500" />
      case 'WORKSPACE_STATUS_UPDATE':
        return <ShieldCheck size={14} className="text-blue-500" />
      case 'DOCUMENT_REVIEW_RESULT':
        return <FileCheck size={14} className="text-blue-500" />
      default:
        return <Bell size={14} className="text-zinc-400" />
    }
  }

  const MarkdownComponents = {
    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="list-disc pl-4 mb-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-4 mb-1">{children}</ol>,
    li: ({ children }) => <li className="mb-0">{children}</li>,
  }

  const isWorkspaceNotification = (n) =>
    n.target_type === 'group' ||
    n.target_type === 'group_document' ||
    (n.target_type && n.target_type.startsWith('doc_comment:'))

  const workspaceCount = notifications.filter(isWorkspaceNotification).length
  const chatCount = notifications.filter(n => n.target_type === 'chat').length

  const filteredNotifications = notifications.filter(n => {
    if (activeTab === 'workspace') {
      return isWorkspaceNotification(n)
    }
    if (activeTab === 'chat') return n.target_type === 'chat'
    return true
  })

  return (
    <div className="relative" ref={menuRef}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className="relative"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <Badge className="absolute -top-1 -right-1 h-4 min-w-4 p-0 flex items-center justify-center text-[10px] bg-red-500 text-white rounded-full border-2 border-background shadow-sm">
            {unreadCount > 99 ? '99+' : unreadCount}
          </Badge>
        )}
      </Button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 max-h-[500px] bg-white dark:bg-slate-950 border border-zinc-200 dark:border-slate-800 rounded-xl shadow-2xl z-50 overflow-hidden flex flex-col">
          <div className="p-3 border-b flex justify-between items-center bg-zinc-50/80 dark:bg-slate-900/80 backdrop-blur-md">
            <span className="text-xs font-black px-1 tracking-tight">최근 알림</span>
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" onClick={markAllAsRead} className="text-[10px] h-7 font-bold hover:bg-zinc-200 dark:hover:bg-slate-800">모두 읽음</Button>
            )}
          </div>

          <div className="flex px-1 border-b border-zinc-100 dark:border-slate-800 bg-white dark:bg-slate-950">
            <button onClick={() => setActiveTab('all')} className={cn("flex-1 py-2.5 text-[11px] transition-all", activeTab === 'all' ? "font-black text-zinc-900 dark:text-slate-100 border-b-2 border-zinc-900 dark:border-slate-100" : "text-zinc-400 hover:text-zinc-600")}>전체 ({notifications.length})</button>
            <button onClick={() => setActiveTab('workspace')} className={cn("flex-1 py-2.5 text-[11px] transition-all", activeTab === 'workspace' ? "font-black text-zinc-900 dark:text-slate-100 border-b-2 border-zinc-900 dark:border-slate-100" : "text-zinc-400 hover:text-zinc-600")}>워크스페이스 ({workspaceCount})</button>
            <button onClick={() => setActiveTab('chat')} className={cn("flex-1 py-2.5 text-[11px] transition-all", activeTab === 'chat' ? "font-black text-zinc-900 dark:text-slate-100 border-b-2 border-zinc-900 dark:border-slate-100" : "text-zinc-400 hover:text-zinc-600")}>채팅 ({chatCount})</button>
          </div>

          <div className="overflow-y-auto flex-1 custom-scrollbar" onScroll={handleScroll}>
            {filteredNotifications.length === 0 ? (
              <div className="py-16 text-center text-zinc-400 dark:text-slate-500 text-xs font-medium">새로운 알림이 없습니다.</div>
            ) : (
              filteredNotifications.map((n) => {
                const type = n.notification_type || n.type
                const isInvite = type === 'WORKSPACE_INVITED'
                const status = n.inviteStatus

                const showButtons = isInvite && !status && !n.is_read
                const isClickable = !isInvite || status === 'accepted' || (n.is_read && status !== 'rejected')

                return (
                  <div
                    key={n.id}
                    className={cn(
                      "p-4 border-b last:border-0 relative group transition-all",
                      !n.is_read ? "bg-blue-50/40 dark:bg-blue-900/15" : "hover:bg-zinc-50 dark:hover:bg-slate-900/50",
                      isClickable ? "cursor-pointer" : "cursor-default"
                    )}
                    onClick={() => {
                      if (!isClickable) return
                      handleNavigate(n)
                      setIsOpen(false)
                    }}
                  >
                    {!n.is_read && <div className="absolute top-0 left-0 w-1 h-full bg-blue-500" />}

                    <div className="flex gap-2.5 items-start">
                      <div className="mt-0.5 p-1.5 rounded-lg bg-white dark:bg-slate-800 shadow-sm border border-zinc-100 dark:border-slate-800 shrink-0">
                        {getNotificationIcon(type)}
                      </div>
                      <div className="flex-1 pr-4">
                        <p className={cn("text-[11px] mb-1 leading-tight", !n.is_read ? "font-black text-zinc-900 dark:text-slate-100" : "font-bold text-zinc-600 dark:text-slate-400")}>{n.title}</p>
                        <div className="text-[10px] text-zinc-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MarkdownComponents}>{n.body}</ReactMarkdown>
                        </div>

                        {showButtons && (
                          <div className="flex gap-2 mt-3">
                            <Button size="sm" className="h-7 text-[10px] bg-blue-600 hover:bg-blue-700 text-white font-black px-4 rounded-lg shadow-sm" onClick={(e) => handleAccept(e, n)} disabled={isActionLoading[n.id]}>
                              {isActionLoading[n.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : '승인'}
                            </Button>
                            <Button size="sm" variant="outline" className="h-7 text-[10px] font-bold border-zinc-200 dark:border-slate-700 px-4 rounded-lg" onClick={(e) => handleReject(e, n)} disabled={isActionLoading[n.id]}>거절</Button>
                          </div>
                        )}

                        {(status === 'accepted' || (n.is_read && isInvite && status !== 'rejected')) && (
                          <div className="flex items-center gap-1 mt-2">
                            <Check size={10} className="text-blue-600" />
                            <p className="text-[10px] text-blue-600 font-black">승인 완료</p>
                          </div>
                        )}
                        {status === 'rejected' && (
                          <p className="text-[10px] text-red-500 font-black mt-2">✕ 거절됨</p>
                        )}

                        <p className="text-[9px] text-zinc-400 dark:text-slate-600 mt-2 font-medium">{n.displayTime}</p>
                      </div>
                    </div>

                    <button onClick={(e) => { e.stopPropagation(); deleteNotification(n.id); }} className="absolute top-4 right-2 p-1.5 text-zinc-300 hover:text-zinc-500 dark:hover:text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" aria-label="삭제">
                      <X size={12} />
                    </button>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}