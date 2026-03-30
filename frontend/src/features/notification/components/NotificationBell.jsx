import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Bell, Check, X, Loader2 } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNotification } from '../context/NotificationContext'
import { cn } from '@/lib/utils'

export default function NotificationBell() {
  const { 
    notifications, unreadCount, markAllAsRead, handleNavigate, 
    deleteNotification, loadMoreNotifications, hasMore, isLoadingMore 
  } = useNotification()
  
  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
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

  const MarkdownComponents = {
    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="list-disc pl-4 mb-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-4 mb-1">{children}</ol>,
    li: ({ children }) => <li className="mb-0">{children}</li>,
  }

  const workspaceCount = notifications.filter(n => n.target_type === 'group').length;
  const chatCount = notifications.filter(n => n.target_type === 'chat').length;
  const allCount = notifications.length;

  const filteredNotifications = notifications.filter(n => {
    if (activeTab === 'workspace') return n.target_type === 'group'
    if (activeTab === 'chat') return n.target_type === 'chat'
    return true
  })

  const TABS = [
    { id: 'all', label: `전체 (${allCount})` },
    { id: 'workspace', label: `워크스페이스 (${workspaceCount})` },
    { id: 'chat', label: `채팅 (${chatCount})` }
  ]

  return (
    <div className="relative" ref={menuRef}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className="relative"
        aria-label="알림 열기"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <Badge 
            className="absolute -top-1 -right-1 h-4 min-w-4 p-0 flex items-center justify-center text-[10px] bg-red-500 hover:bg-red-600 text-white rounded-full border-2 border-background"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </Badge>
        )}
      </Button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 max-h-[500px] bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-lg shadow-xl z-50 overflow-hidden flex flex-col">        
            {unreadCount > 0 && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={(e) => {
                  e.stopPropagation()
                  markAllAsRead()
                }}
                className="text-[10px] h-6 px-1.5 gap-1 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <Check size={10} />
                모두 읽음
              </Button>
            )}
    

          <div className="flex px-1 border-b border-zinc-100 dark:border-zinc-800">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex-1 py-2.5 text-[11px] font-medium transition-all relative",
                  activeTab === tab.id 
                    ? "text-zinc-900 dark:text-zinc-100 font-bold" 
                    : "text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300"
                )}
              >
                {tab.label}
                {activeTab === tab.id && (
                  <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-zinc-900 dark:bg-zinc-100 rounded-full" />
                )}
              </button>
            ))}
          </div>
          
          <div 
            className="overflow-y-auto flex-1 custom-scrollbar min-h-[100px]"
            onScroll={handleScroll}
          >
            {filteredNotifications.length === 0 ? (
              <div className="py-12 px-4 text-center text-zinc-400 dark:text-zinc-500 text-xs">
                {activeTab === 'all' ? '새로운 알림이 없습니다.' : '해당 카테고리의 알림이 없습니다.'}
              </div>
            ) : (
              <>
                {filteredNotifications.map((n) => (
                  <div 
                    key={n.id}
                    className={cn(
                      "p-4 border-b border-zinc-50 dark:border-zinc-900 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors cursor-pointer relative group",
                      !n.is_read && "bg-blue-50/30 dark:bg-blue-900/10"
                    )}
                    onClick={() => {
                      handleNavigate(n)
                      setIsOpen(false)
                    }}
                  >
                    {!n.is_read && (
                      <div className="absolute top-5 left-2 w-1.5 h-1.5 bg-blue-500 rounded-full" />
                    )}
                    <div className="ml-1 pr-6">
                      <p className="text-[11px] font-bold text-zinc-900 dark:text-zinc-100 mb-1 leading-tight">{n.title}</p>
                      <div className="text-[10px] text-zinc-500 dark:text-zinc-400 line-clamp-3 leading-normal overflow-hidden">
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={MarkdownComponents}
                        >
                          {n.body}
                        </ReactMarkdown>
                      </div>
                      <p className="text-[9px] text-zinc-400 dark:text-zinc-600 mt-2">
                        {n.displayTime}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteNotification(n.id)
                      }}
                      className="absolute top-4 right-2 p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label="알림 삭제"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
                
                {isLoadingMore && (
                  <div className="py-4 flex justify-center items-center">
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}