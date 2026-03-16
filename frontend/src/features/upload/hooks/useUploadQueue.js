import { useCallback } from 'react'
import { toast } from 'sonner'
import {
  cancelUploadItemApi,
  clearUploadSessionApi,
  createUploadSessionApi,
  uploadDocumentApi,
} from '../api/uploadSessionApi.js'
import {
  isSameFile,
  makeItem,
  MAX_FILES,
} from '../uploadState.js'

export function useUploadQueue({
  fileInputRef,
  items,
  setItems,
  isRunning,
  setIsRunning,
  setIsDragOver,
  stopRequestedRef,
  pollingDocIdsRef,
  resetLocalState,
}) {
  const updateItem = useCallback((file, patch) => {
    setItems((prev) => prev.map((it) => (isSameFile(it, file) ? { ...it, ...patch } : it)))
  }, [setItems])

  const updateItemByDocId = useCallback((docId, patch) => {
    setItems((prev) => prev.map((it) => (it.docId === docId ? { ...it, ...patch } : it)))
  }, [setItems])

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

  const cancelItem = useCallback(async (docId) => {
    try {
      await cancelUploadItemApi(docId)
      updateItemByDocId(docId, { status: 'failed', error: '사용자가 취소했습니다.' })

      setItems((prev) => {
        const stillRunning = prev.some(
          (it) => it.docId !== docId && (it.status === 'processing' || it.status === 'queued')
        )
        if (!stillRunning) setIsRunning(false)
        return prev
      })
    } catch {
      toast.error('취소에 실패했습니다.')
    }
  }, [updateItemByDocId, setItems, setIsRunning])

  const toggleExpand = useCallback((file) => {
    const current = items.find((it) => isSameFile(it, file))
    updateItem(file, { expanded: !current?.expanded })
  }, [items, updateItem])

  const handleWsMessage = useCallback((message) => {
    const { type, doc_id, summary, error } = message

    if (type === 'upload_processing') {
      updateItemByDocId(doc_id, { status: 'processing', progress: 0 })
    } else if (type === 'upload_done') {
      updateItemByDocId(doc_id, {
        status: 'done',
        progress: 100,
        summary: summary || null,
      })
      setItems((prev) => {
        const stillRunning = prev.some(
          (it) => it.docId !== doc_id && (it.status === 'processing' || it.status === 'queued')
        )
        if (!stillRunning) setIsRunning(false)
        return prev
      })
    } else if (type === 'upload_failed') {
      updateItemByDocId(doc_id, {
        status: 'failed',
        error: error || '처리 중 오류가 발생했습니다.',
      })
      setItems((prev) => {
        const stillRunning = prev.some(
          (it) => it.docId !== doc_id && (it.status === 'processing' || it.status === 'queued')
        )
        if (!stillRunning) setIsRunning(false)
        return prev
      })
    } else if (type === 'upload_cancelled') {
      updateItemByDocId(doc_id, { status: 'failed', error: '사용자가 취소했습니다.' })
    }
  }, [updateItemByDocId, setItems, setIsRunning])

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

    // 버튼 클릭 시 이전 done/failed 초기화, 대기 파일만 queued로 전환
    setItems(waitingOnly.map((it) => ({ ...it, status: 'queued' })))
    setIsRunning(true)

    for (const it of waitingOnly) {
      if (stopRequestedRef.current) break
      try {
        const uploadData = await uploadDocumentApi(it.file)
        const docId = uploadData.document_ids[0]
        updateItem(it.file, { docId })
      } catch (err) {
        updateItem(it.file, {
          status: 'failed',
          error: err.message || '업로드 실패',
        })
      }
    }
  }, [isRunning, items, setItems, setIsRunning, stopRequestedRef, updateItem])

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
    cancelItem,
    toggleExpand,
    handleUpload,
    handleWsMessage,
    clearSession,
    waitingItems: items.filter((it) => it.status === 'waiting'),
    processingItems: items.filter((it) =>
      it.status === 'queued' ||
      it.status === 'processing' ||
      it.status === 'done' ||
      it.status === 'failed'
    ),
  }
}