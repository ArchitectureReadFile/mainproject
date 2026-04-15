import {
    Download,
    FileArchive,
    Loader2,
    X,
    CheckCircle2,
    AlertCircle,
} from 'lucide-react'

import { Button } from '@/shared/ui/Button'
import { cn } from '@/shared/lib/utils'

const EXPORT_STATUS_LABEL = {
    PENDING: '다운로드 준비 중입니다.',
    PROCESSING: '압축 파일을 생성하고 있습니다.',
    READY: '다운로드 준비가 완료되었습니다.',
    FAILED: '백업 생성에 실패했습니다.',
    EXPIRED: '백업 파일 보관 기간이 만료되었습니다.',
    CANCELLED: '백업 생성이 취소되었습니다.',
}

/**
 * export 상태 패널을 표시한다.
 */
export default function ExportStatusToast({
    exportJob,
    onDownload,
    onClose,
}) {
    if (!exportJob) return null

    const isRunning = ['PENDING', 'PROCESSING'].includes(exportJob.status)
    const isReady = exportJob.status === 'READY'
    const isError = ['FAILED', 'EXPIRED', 'CANCELLED'].includes(exportJob.status)

    return (
        <div className="fixed bottom-6 right-6 z-[10010] w-[380px] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl">
            <div className="overflow-hidden rounded-t-2xl">
                {isRunning ? (
                    <div className="h-1.5 w-full bg-blue-100">
                        <div className="h-full w-1/3 animate-[export-progress_1.2s_ease-in-out_infinite] rounded-r-full bg-blue-500" />
                    </div>
                ) : (
                    <div
                        className={cn(
                            'h-1.5 w-full',
                            isReady && 'bg-blue-500',
                            isError && 'bg-red-500',
                        )}
                    />
                )}
            </div>
            <div className="p-4">
                <div className="mb-3 flex items-center gap-2">
                    <div
                        className={cn(
                            'flex h-7 w-7 items-center justify-center rounded-full',
                            isReady && 'bg-blue-50 text-blue-600',
                            isRunning && 'bg-blue-50 text-blue-600',
                            isError && 'bg-red-50 text-red-600',
                        )}
                    >
                        {isReady ? (
                            <CheckCircle2 className="h-4 w-4" />
                        ) : isRunning ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <AlertCircle className="h-4 w-4" />
                        )}
                    </div>

                    <p className="text-sm font-black text-zinc-900">
                        {isRunning
                            ? '압축 파일을 준비하고 있습니다.'
                            : EXPORT_STATUS_LABEL[exportJob.status] ?? exportJob.status}
                    </p>

                    <button
                        className="ml-auto p-1 text-zinc-400 hover:text-zinc-600"
                        onClick={onClose}
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="rounded-xl bg-zinc-50 px-3 py-3 text-sm text-zinc-600">
                    <div className="flex items-center gap-2">
                        <FileArchive className="h-4 w-4 text-zinc-500" />
                        <p>
                            {isRunning
                                ? '워크스페이스 문서를 ZIP 파일로 압축 중입니다. 완료되면 자동으로 다운로드됩니다.'
                                : `총 ${exportJob.total_file_count}건 중 ${exportJob.exported_file_count}건이 포함되었습니다.`}
                        </p>
                    </div>

                    {exportJob.missing_file_count > 0 && (
                        <p className="mt-2 text-xs text-zinc-500">
                            누락 파일 {exportJob.missing_file_count}건은 `missing_files.txt`에서 확인할 수 있습니다.
                        </p>
                    )}

                    {exportJob.status === 'FAILED' && exportJob.error_message && (
                        <p className="mt-2 text-xs text-red-600">{exportJob.error_message}</p>
                    )}

                    {exportJob.status === 'EXPIRED' && (
                        <p className="mt-2 text-xs text-zinc-500">
                            전체 다운로드 버튼을 눌러 백업을 다시 생성해주세요.
                        </p>
                    )}
                </div>

                {isReady && (
                    <div className="mt-3 flex justify-end">
                        <Button
                            variant="outline"
                            onClick={onDownload}
                            className="gap-2 border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                        >
                            <Download className="h-4 w-4" />
                            다시 다운로드
                        </Button>
                    </div>
                )}
            </div>
        </div>
    )
}
