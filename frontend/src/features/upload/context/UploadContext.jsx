import { useAuth } from '@/features/auth/index.js'
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  abandonUploadSessionApi,
  abandonUploadSessionKeepaliveApi,
} from '../api/uploadSessionApi.js'
import { useUploadQueue } from '../hooks/useUploadQueue.js'
import { useUploadSessionSync } from '../hooks/useUploadSessionSync.js'
import { useUploadWebSocket } from '../hooks/useUploadWebSocket.js'
import { makeRestoredItem } from '../uploadState.js'

const UploadContext = createContext(null)

export function UploadProvider({ children }) {
  const location = useLocation()
  const { user } = useAuth()
  const fileInputRef = useRef(null)
  const isRunningRef = useRef(false)
  const stopRequestedRef = useRef(false)
  const pollingDocIdsRef = useRef(new Set())

  const [items, setItems] = useState([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [isRunning, setIsRunning] = useState(false)

  const syncSessionState = useCallback((session) => {
    const restoredItems = (session?.items ?? []).map(makeRestoredItem)
    setItems(restoredItems)
    setIsRunning(restoredItems.some((item) => item.status === 'processing'))
  }, [])

  const requestAbandonSession = useCallback(({ keepalive = false } = {}) => {
    return keepalive ? abandonUploadSessionKeepaliveApi() : abandonUploadSessionApi()
  }, [])

  const resetLocalState = useCallback(() => {
    setItems([])
    setIsRunning(false)
  }, [])

  const abandonActiveUpload = useCallback(async () => {
    stopRequestedRef.current = true
    try {
      const session = await requestAbandonSession()
      syncSessionState(session)
    } catch {
      setIsRunning(false)
    }
  }, [requestAbandonSession, syncSessionState])

  isRunningRef.current = isRunning

  useUploadSessionSync({
    locationPath: location.pathname,
    isRunningRef,
    syncSessionState,
    abandonActiveUpload,
    requestAbandonSession,
    resetUploadState: resetLocalState,
  })

  const {
    waitingItems,
    processingItems,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    cancelItem,
    toggleExpand,
    handleUpload,
    handleWsMessage,
    clearSession,
  } = useUploadQueue({
    fileInputRef,
    items,
    setItems,
    isRunning,
    setIsRunning,
    setIsDragOver,
    stopRequestedRef,
    pollingDocIdsRef,
    resetLocalState,
  })

  // WebSocket 연결 — 업로드 진행 중에만 연결
  useUploadWebSocket({
    userId: user?.id,
    onMessage: handleWsMessage,
    isRunning,
  })

  const confirmLogout = useCallback(() => {
    if (isRunningRef.current) {
      return window.confirm('업로드 처리 중입니다. 로그아웃하면 대기 중 파일은 실패 처리됩니다. 계속하시겠습니까?')
    }
    return true
  }, [])

  const value = useMemo(() => ({
    fileInputRef,
    items,
    isDragOver,
    isRunning,
    waitingItems,
    processingItems,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    cancelItem,
    toggleExpand,
    handleUpload,
    confirmLogout,
    clearSession,
  }), [
    items,
    isDragOver,
    isRunning,
    waitingItems,
    processingItems,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    cancelItem,
    toggleExpand,
    handleUpload,
    clearSession,
    confirmLogout,
  ])

  return (
    <UploadContext.Provider value={value}>
      {children}
    </UploadContext.Provider>
  )
}

export function useUpload() {
  return useContext(UploadContext)
}