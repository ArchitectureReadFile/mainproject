import Button from '@/components/ui/Button'
import { CheckCircle, ChevronDown, ChevronUp, FileText, Loader2, XCircle } from 'lucide-react'

function StatusIcon({ status }) {
  if (status === 'processing') return <Loader2 size={16} className="shrink-0 text-primary animate-spin" />
  if (status === 'done')       return <CheckCircle size={16} className="shrink-0 text-success" />
  if (status === 'failed')     return <XCircle size={16} className="shrink-0 text-destructive" />
  return <FileText size={16} className="shrink-0 text-muted-foreground" />
}

function StatusLabel({ status }) {
  if (status === 'processing') return <span className="text-xs font-semibold text-primary">처리 중...</span>
  if (status === 'done')       return <span className="text-xs font-semibold text-success">완료</span>
  if (status === 'failed')     return <span className="text-xs font-semibold text-destructive">실패</span>
  return <span className="text-xs font-semibold text-muted-foreground">대기 중</span>
}

export default function FileStatusItem({ it, file, onToggle }) {
  return (
    <li className="rounded-lg border overflow-hidden">
      <div className="flex items-center gap-2.5 px-3.5 py-3">
        <StatusIcon status={it.status} />
        <span className="flex-1 text-sm truncate">{it.file.name}</span>
        <StatusLabel status={it.status} />
        {it.status === 'done' && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground"
            onClick={() => onToggle(file)}
          >
            {it.expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </Button>
        )}
      </div>

      {it.status === 'processing' && (
        <div className="px-3.5 pb-3">
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${it.progress}%` }}
            />
          </div>
        </div>
      )}

      {it.status === 'failed' && (
        <div className="px-3.5 pb-3 text-xs text-destructive">
          {it.error}
        </div>
      )}

      {it.status === 'done' && it.expanded && it.summary && (
        <div className="border-t bg-muted/40 p-4">
          <div className="grid grid-cols-3 gap-3 mb-3">
            {[
              ['사건번호', it.summary.case_number],
              ['법원',     it.summary.court],
              ['판결일',   it.summary.date],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-muted-foreground font-semibold">{label}</p>
                <p className="text-sm font-bold mt-0.5">{value}</p>
              </div>
            ))}
          </div>
          <div>
            <p className="text-xs text-muted-foreground font-semibold">AI 요약</p>
            <p className="text-sm text-foreground/80 leading-relaxed mt-1">{it.summary.content}</p>
          </div>
        </div>
      )}
    </li>
  )
}