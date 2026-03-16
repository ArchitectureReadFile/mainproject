import { useEffect, useRef } from 'react'
import { getUploadSessionApi } from '../api/uploadSessionApi.js'

export function useUploadSessionSync({
  locationPath,
  isRunningRef,
  syncSessionState,
  abandonActiveUpload,
  requestAbandonSession,
  resetUploadState,
}) {
  const previousPathRef = useRef(locationPath)

  useEffect(() => {
    let mounted = true

    getUploadSessionApi()
      .then((session) => {
        if (mounted) syncSessionState(session)
      })
      .catch(() => {
        if (mounted) resetUploadState()
      })

    return () => {
      mounted = false
    }
  }, [resetUploadState, syncSessionState])

  useEffect(() => {
    const handler = (e) => {
      if (isRunningRef.current) {
        e.preventDefault()
        e.returnValue = ''
      }
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isRunningRef])

  useEffect(() => {
    const handler = () => {
      if (!isRunningRef.current) return
      requestAbandonSession({ keepalive: true }).catch(() => {})
    }

    window.addEventListener('pagehide', handler)
    return () => window.removeEventListener('pagehide', handler)
  }, [isRunningRef, requestAbandonSession])

  useEffect(() => {
    const previousPath = previousPathRef.current
    const leftUploadPage =
      previousPath.includes('/upload') &&
      !locationPath.includes('/upload')

    if (leftUploadPage && isRunningRef.current) {
      abandonActiveUpload()
    }

    previousPathRef.current = locationPath
  }, [abandonActiveUpload, isRunningRef, locationPath])
}
