import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function NotificationToast({ notification, onNavigate, onClose }) {
  return (
    <div 
      className="flex w-[380px] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl overflow-hidden cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
      onClick={onNavigate}
    >
      <div className="w-1.5 bg-blue-500" />
      <div className="flex-1 p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="flex items-center justify-center w-6 h-6 bg-blue-50 dark:bg-blue-900/30 rounded-full">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          </div>
          <span className="text-xs font-black text-zinc-900 dark:text-zinc-100">
            AI 답변 완료
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
      </div>
    </div>
  )
}
