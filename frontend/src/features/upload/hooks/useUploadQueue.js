import { useCallback } from 'react'
import { toast } from 'sonner'
import {
  clearUploadSessionApi,
  createUploadSessionApi,
  uploadDocumentApi,
} from '../api/uploadSessionApi.js'
import {
  buildSummary,
  isSameFile,
  makeItem,
  MAX_FILES,
} from '../uploadState.js'
import { useUploadPolling } from './useUploadPolling.js'
import { useRecoveryPolling } from './useRecoveryPolling.js'

export function useUploadQueue({
  fileInputRef,
  items,
  setItems,
  isRunning,
  setIsRunning,
  started,
  setStarted,
  setIsDragOver,
  stopRequestedRef,
  pollingDocIdsRef,
  resetLocalState,
}) {
  const updateItem = useCallback((file, patch) => {
    setItems((prev) => prev.map((it) => (isSameFile(it, file) ? { ...it, ...patch } : it)))
  }, [setItems])

  const applyCompletedResult = useCallback((file, result, docId) => {
    updateItem(file, {
      ...(docId ? { docId } : {}),
      status: 'done',
      progress: 100,
      summary: buildSummary(result),
    })
  }, [updateItem])

  const applyFailedResult = useCallback((file, err) => {
    updateItem(file, {
      status: 'failed',
      progress: 0,
      error: err.message || '처리 중 오류가 발생했습니다.',
    })
  }, [updateItem])

  // 실시간 업로드 중 신규 파일 폴링
  const { startPolling } = useUploadPolling({
    pollingDocIdsRef,
    updateItem,
    applyCompletedResult,
  })

  // 페이지 재진입/새로고침 후 processing 중인 아이템 복구 폴링
  useRecoveryPolling({
    items,
    pollingDocIdsRef,
    applyCompletedResult,
    applyFailedResult,
    setIsRunning,
  })

  const processOne = useCallback(async (file) => {
    updateItem(file, { status: 'processing', progress: 0, error: null })

    const timer = setInterval(() => {
      setItems((prev) =>
        prev.map((it) => {
          if (!isSameFile(it, file) || it.status !== 'processing') return it
          return { ...it, progress: Math.min(it.progress + 7, 90) }
        })
      )
    }, 400)

    try {
      const uploadData = await uploadDocumentApi(file)
      const docId = uploadData.document_ids[0]
      clearInterval(timer)
      await startPolling(file, docId)
    } catch (err) {
      clearInterval(timer)
      applyFailedResult(file, err)
    }
  }, [applyFailedResult, setItems, startPolling, updateItem])

  const addFiles = useCallback((newFiles) => {
    if (isRunning) return

    const pdfs = newFiles.filter((f) => f.type === 'application/pdf')
    if (pdfs.length !== newFiles.length) toast.error('PDF 파일만 업로드 가능합니다.')

    setItems((prev) => {
      const existingNames = new Set(
        prev.filter((it) => it.status !== 'failed').map((it) => it.file.name)
      )
      const deduped = pdfs.filter((f) => !existingNames.has(f.name))
      if (deduped.length !== pdfs.length) toast.warning('이미 추가된 파일은 제외되었습니다.')

      const waiting = prev.filter((it) => it.status === 'waiting')
      const combined = [...waiting, ...deduped.map(makeItem)]
      if (combined.length > MAX_FILES) toast.warning(`최대 ${MAX_FILES}개까지 업로드 가능합니다.`)

      const doneOrFailed = prev.filter((it) => it.status === 'done' || it.status === 'failed')
      return [...doneOrFailed, ...combined.slice(0, MAX_FILES)]
    })

    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [fileInputRef, isRunning, setItems])

  const handleFileChange = useCallback((e) => {
    addFiles(Array.from(e.target.files || []))
  }, [addFiles])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
    if (!isRunning) addFiles(Array.from(e.dataTransfer.files || []))
  }, [addFiles, isRunning, setIsDragOver])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    if (!isRunning) setIsDragOver(true)
  }, [isRunning, setIsDragOver])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [setIsDragOver])

  const openFilePicker = useCallback(() => {
    if (!isRunning) fileInputRef.current?.click()
  }, [fileInputRef, isRunning])

  const removeItem = useCallback((fileObj) => {
    setItems((prev) => prev.filter((it) => !isSameFile(it, fileObj)))
  }, [setItems])

  const toggleExpand = useCallback((file) => {
    const current = items.find((it) => isSameFile(it, file))
    updateItem(file, { expanded: !current?.expanded })
  }, [items, updateItem])

  const handleUpload = useCallback(async () => {
    if (isRunning) return

    const waitingOnly = items.filter((it) => it.status === 'waiting')
    if (waitingOnly.length === 0) return

    stopRequestedRef.current = false

    try {
      await createUploadSessionApi(waitingOnly.map((item) => item.file.name))
    } catch (err) {
      toast.error(err.message || '업로드 세션 생성에 실패했습니다.')
      return
    }

    setItems(waitingOnly)
    setIsRunning(true)
    setStarted(true)

    for (const file of waitingOnly.map((it) => it.file)) {
      if (stopRequestedRef.current) break
      await processOne(file)
    }

    setIsRunning(false)
  }, [isRunning, items, processOne, setItems, setIsRunning, setStarted, stopRequestedRef])

  const clearSession = useCallback(() => {
    clearUploadSessionApi().catch(() => {})
    stopRequestedRef.current = true
    pollingDocIdsRef.current.clear()
    resetLocalState()
  }, [pollingDocIdsRef, resetLocalState, stopRequestedRef])

  return {
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    toggleExpand,
    handleUpload,
    clearSession,
    waitingItems: items.filter((it) => it.status === 'waiting'),
    processingItems: started
      ? items.filter((it) => it.status === 'processing' || it.status === 'done' || it.status === 'failed')
      : [],
  }
}
