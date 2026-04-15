import { Button } from '@/shared/ui/Button'
import { CheckCircle, Clock3, FileText, Loader2, X, XCircle } from 'lucide-react'

function getDisplayState(it) {
  if (it.uploadStatus === 'uploading') {
    return {
      icon: <Loader2 size={16} className="shrink-0 text-primary animate-spin" />,
      label: '업로드 중',
      labelClass: 'text-primary',
      progress: Math.max(it.progress ?? 5, 5),
      error: null,
      description: '파일 업로드 중입니다.',
      removable: false,
    }
  }

  if (it.uploadStatus === 'upload_failed') {
    return {
      icon: <XCircle size={16} className="shrink-0 text-destructive" />,
      label: '업로드 실패',
      labelClass: 'text-destructive',
      progress: 100,
      error: it.error,
      description: '업로드에 실패했습니다.',
      removable: false,
    }
  }

  if (!it.serverDoc) {
    return {
      icon: <Clock3 size={16} className="shrink-0 text-muted-foreground" />,
      label: '상태 확인 중',
      labelClass: 'text-muted-foreground',
      progress: 10,
      error: null,
      description: '서버 상태 확인 중입니다.',
      removable: false,
    }
  }

  if (it.serverDoc.status === 'PENDING') {
    return {
      icon: <Clock3 size={16} className="shrink-0 text-muted-foreground" />,
      label: '대기',
      labelClass: 'text-muted-foreground',
      progress: 20,
      error: null,
      description: '아직 요약 시작 전이라 삭제할 수 있습니다.',
      removable: true,
    }
  }

  if (it.serverDoc.status === 'PROCESSING') {
    return {
      icon: <Loader2 size={16} className="shrink-0 text-yellow-500 animate-spin" />,
      label: '처리 중',
      labelClass: 'text-yellow-500',
      progress: 70,
      error: null,
      description: '이미 요약이 시작되어 삭제할 수 없습니다.',
      removable: false,
    }
  }

  if (it.serverDoc.status === 'DONE') {
    return {
      icon: <CheckCircle size={16} className="shrink-0 text-green-600" />,
      label: '완료',
      labelClass: 'text-green-600',
      progress: 100,
      error: null,
      description: '요약 완료',
      removable: false,
    }
  }

  if (it.serverDoc.status === 'FAILED') {
    return {
      icon: <XCircle size={16} className="shrink-0 text-destructive" />,
      label: '실패',
      labelClass: 'text-destructive',
      progress: 100,
      error: it.error ?? '요약 생성에 실패했습니다.',
      description: '요약 실패',
      removable: false,
    }
  }

  return {
    icon: <FileText size={16} className="shrink-0 text-muted-foreground" />,
    label: '상태 확인 중',
    labelClass: 'text-muted-foreground',
    progress: 10,
    error: null,
    description: '상태 확인 중입니다.',
    removable: false,
  }
}

export default function FileStatusItem({ it, onRemove }) {
  const state = getDisplayState(it)

  return (
    <li className="overflow-hidden rounded-lg border">
      <div className="flex items-center gap-2.5 px-3.5 py-3">
        {state.icon}
        <span className="flex-1 truncate text-sm">{it.file.name}</span>
        <span className={`text-xs font-semibold ${state.labelClass}`}>
          {state.label}
        </span>
        {state.removable && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-foreground"
            onClick={() => onRemove(it)}
            aria-label={`${it.file.name} 삭제`}
          >
            <X size={13} />
          </Button>
        )}
      </div>

      <div className="px-3.5 pb-3">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${state.progress}%` }}
          />
        </div>
      </div>

      <div className="px-3.5 pb-3 text-xs text-muted-foreground">
        {state.description}
      </div>

      {state.error && (
        <div className="px-3.5 pb-3 text-xs text-destructive">
          {state.error}
        </div>
      )}
    </li>
  )
}
