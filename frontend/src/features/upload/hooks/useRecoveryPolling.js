import { useEffect } from 'react'
import { getDocumentDetailApi } from '../api/uploadSessionApi.js'
import { POLL_INTERVAL, POLL_TIMEOUT } from '../uploadState.js'

/**
 * 세션 복구 시 이미 processing 상태인 아이템을 감지해 폴링을 재연결합니다.
 * 페이지 재진입 또는 새로고침 후 진행 중인 업로드를 자동으로 추적합니다.
 */
export function useRecoveryPolling({
  items,
  pollingDocIdsRef,
  applyCompletedResult,
  applyFailedResult,
  setIsRunning,
}) {
  useEffect(() => {
    const processingItems = items.filter((item) => item.status === 'processing' && item.docId)

    processingItems.forEach((item) => {
      if (pollingDocIdsRef.current.has(item.docId)) return

      pollingDocIdsRef.current.add(item.docId)

      const startedAt = Date.now()
      const tick = setInterval(async () => {
        if (Date.now() - startedAt > POLL_TIMEOUT) {
          clearInterval(tick)
          pollingDocIdsRef.current.delete(item.docId)
          applyFailedResult(item.file, new Error('처리 시간이 초과되었습니다.'))
          setIsRunning(false)
          return
        }

        try {
          const data = await getDocumentDetailApi(item.docId)
          if (data.status === 'DONE') {
            clearInterval(tick)
            pollingDocIdsRef.current.delete(item.docId)
            applyCompletedResult(item.file, data)
            setIsRunning(false)
          } else if (data.status === 'FAILED') {
            clearInterval(tick)
            pollingDocIdsRef.current.delete(item.docId)
            applyFailedResult(item.file, new Error('서버에서 처리에 실패했습니다.'))
            setIsRunning(false)
          }
        } catch (err) {
          clearInterval(tick)
          pollingDocIdsRef.current.delete(item.docId)
          applyFailedResult(item.file, err)
          setIsRunning(false)
        }
      }, POLL_INTERVAL)
    })
  }, [applyCompletedResult, applyFailedResult, items, pollingDocIdsRef, setIsRunning])
}
