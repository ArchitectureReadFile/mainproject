import { useCallback, useEffect, useRef } from 'react'
import { getDocumentDetailApi } from '../api/uploadSessionApi.js'
import { POLL_INTERVAL, POLL_TIMEOUT } from '../uploadState.js'

/**
 * 단일 docId에 대한 폴링 로직 (Promise 기반).
 * 실시간 업로드 중 신규 파일 처리에 사용됩니다.
 */
export function useUploadPolling({
  pollingDocIdsRef,
  updateItem,
  applyCompletedResult,
}) {
  const intervalRefs = useRef(new Map())

  const clearTrackedInterval = useCallback((docId) => {
    const intervalId = intervalRefs.current.get(docId)
    if (intervalId) {
      clearInterval(intervalId)
      intervalRefs.current.delete(docId)
    }
  }, [])

  const pollStatus = useCallback((docId) =>
    new Promise((resolve, reject) => {
      const startedAt = Date.now()
      const tick = setInterval(async () => {
        if (Date.now() - startedAt > POLL_TIMEOUT) {
          clearTrackedInterval(docId)
          pollingDocIdsRef.current.delete(docId)
          return reject(new Error('처리 시간이 초과되었습니다.'))
        }

        try {
          const data = await getDocumentDetailApi(docId)
          if (data.status === 'DONE') {
            clearTrackedInterval(docId)
            pollingDocIdsRef.current.delete(docId)
            return resolve(data)
          }
          if (data.status === 'FAILED') {
            clearTrackedInterval(docId)
            pollingDocIdsRef.current.delete(docId)
            return reject(new Error('서버에서 처리에 실패했습니다.'))
          }
        } catch (err) {
          clearTrackedInterval(docId)
          pollingDocIdsRef.current.delete(docId)
          reject(err)
        }
      }, POLL_INTERVAL)

      intervalRefs.current.set(docId, tick)
    }), [clearTrackedInterval, pollingDocIdsRef])

  // 언마운트 시 모든 인터벌 정리
  useEffect(() => {
    const refs = intervalRefs.current
    return () => {
      refs.forEach((intervalId) => clearInterval(intervalId))
      refs.clear()
    }
  }, [])

  /**
   * 실시간 업로드 중 신규 파일을 폴링합니다.
   * processOne → uploadDocumentApi 완료 후 docId를 받아 직접 호출합니다.
   */
  const startPolling = useCallback(async (file, docId) => {
    pollingDocIdsRef.current.add(docId)
    updateItem(file, { docId })

    const result = await pollStatus(docId)
    applyCompletedResult(file, result, docId)
  }, [applyCompletedResult, pollStatus, pollingDocIdsRef, updateItem])

  return { startPolling }
}
