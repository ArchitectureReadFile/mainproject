import { useEffect, useRef, useState } from 'react'

import { getExportJob, getExportDownloadUrl } from '@/shared/api/exports'
import ExportStatusToast from './ExportStatusToast'
import {
    clearStoredExportIntent,
    EXPORT_INTENT_UPDATED_EVENT,
    getStoredExportIntent,
} from '../utils/exportIntent'

const EXPORT_MONITOR_INTERVAL = 3000

/**
 * export ZIP 다운로드를 시작한다.
 */
function triggerExportDownload(jobId, fileName) {
    const link = document.createElement('a')
    link.href = getExportDownloadUrl(jobId)
    link.download = fileName || 'workspace_documents.zip'
    document.body.appendChild(link)
    link.click()
    link.remove()
}

/**
 * 앱 전역에서 export job 상태를 감시한다.
 */
export default function ExportMonitor() {
    const [exportJob, setExportJob] = useState(null)
    const [isVisible, setIsVisible] = useState(false)
    const handledStatusRef = useRef({})

    useEffect(() => {
        /**
         * 현재 export intent 기준으로 job 상태를 즉시 조회한다.
         */
        const pollExportJob = async () => {
            const intent = getStoredExportIntent()
            if (!intent?.jobId) {
                return
            }

            setIsVisible(true)
            setExportJob((prev) => {
                if (prev?.id === intent.jobId) return prev

                return {
                    id: intent.jobId,
                    status: 'PENDING',
                    total_file_count: 0,
                    exported_file_count: 0,
                    missing_file_count: 0,
                    error_message: null,
                    export_file_name: null,
                }
            })

            try {
                const nextJob = await getExportJob(intent.jobId)
                setExportJob(nextJob)

                const key = `${nextJob.id}:${nextJob.status}`
                if (handledStatusRef.current[key]) return
                handledStatusRef.current[key] = true

                if (nextJob.status === 'READY') {
                    if (intent.autoDownload) {
                        triggerExportDownload(nextJob.id, nextJob.export_file_name)
                    }
                    clearStoredExportIntent()
                    return
                }

                if (
                    nextJob.status === 'FAILED' ||
                    nextJob.status === 'EXPIRED' ||
                    nextJob.status === 'CANCELLED'
                ) {
                    clearStoredExportIntent()
                }
            } catch (e) {
                console.error('export monitor polling 실패:', e)
            }
        }

        /**
         * export intent 갱신 시 즉시 패널을 띄우고 상태 조회를 시작한다.
         */
        const handleIntentUpdated = () => {
            pollExportJob()
        }

        pollExportJob()

        window.addEventListener(EXPORT_INTENT_UPDATED_EVENT, handleIntentUpdated)

        const timerId = window.setInterval(pollExportJob, EXPORT_MONITOR_INTERVAL)

        return () => {
            window.removeEventListener(EXPORT_INTENT_UPDATED_EVENT, handleIntentUpdated)
            window.clearInterval(timerId)
        }
    }, [])

    if (!isVisible || !exportJob) return null

    return (
        <ExportStatusToast
            exportJob={exportJob}
            onDownload={() =>
                triggerExportDownload(exportJob.id, exportJob.export_file_name)
            }
            onClose={() => {
                setIsVisible(false)
                setExportJob(null)
            }}
        />
    )
}
