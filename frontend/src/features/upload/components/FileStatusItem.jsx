import { CheckCircle, FileText, Loader2, XCircle } from 'lucide-react'

function StatusIcon({ uploadStatus }) {
  if (uploadStatus === 'uploading') return <Loader2 size={16} className="shrink-0 text-primary animate-spin" />
  if (uploadStatus === 'uploaded') return <CheckCircle size={16} className="shrink-0 text-success" />
  if (uploadStatus === 'upload_failed') return <XCircle size={16} className="shrink-0 text-destructive" />
  return <FileText size={16} className="shrink-0 text-muted-foreground" />
}

function StatusLabel({ uploadStatus }) {
  if (uploadStatus === 'uploading') return <span className="text-xs font-semibold text-primary">업로드 중...</span>
  if (uploadStatus === 'uploaded') return <span className="text-xs font-semibold text-success">업로드 완료</span>
  if (uploadStatus === 'upload_failed') return <span className="text-xs font-semibold text-destructive">업로드 실패</span>
  return <span className="text-xs font-semibold text-muted-foreground">대기 중</span>
}

export default function FileStatusItem({ it }) {
  return (
    <li className="rounded-lg border overflow-hidden">
      <div className="flex items-center gap-2.5 px-3.5 py-3">
        <StatusIcon uploadStatus={it.uploadStatus} />
        <span className="flex-1 text-sm truncate">{it.file.name}</span>
        <StatusLabel uploadStatus={it.uploadStatus} />
      </div>

      {it.uploadStatus === 'uploading' && (
        <div className="px-3.5 pb-3">
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${it.progress}%` }}
            />
          </div>
        </div>
      )}

      {it.uploadStatus === 'upload_failed' && (
        <div className="px-3.5 pb-3 text-xs text-destructive">
          {it.error}
        </div>
      )}
    </li>
  )
}
