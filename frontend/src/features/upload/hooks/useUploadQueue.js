/* global AbortController */

import { useCallback, useRef } from 'react'
import { fetchDocumentDetail } from '@/api/documents.js'
import { toast } from 'sonner'
import { uploadDocumentApi } from '../api/uploadApi.js'
import {
  isSameFile,
  makeItem,
  MAX_FILES,
} from '../uploadState.js'

const POLL_INTERVAL_MS = 2000

export function useUploadQueue({
  fileInputRef,
  groupId,
  items,
  setItems,
  setIsDragOver,
}) {
  const pollTimersRef = useRef(new Map())
  const uploadControllersRef = useRef(new Map())
  const abortRequestedRef = useRef(false)

  const updateItem = useCallback((file, patch) => {
    setItems((prev) => prev.map((it) => (isSameFile(it, file) ? { ...it, ...patch } : it)))
  }, [setItems])

  const updateItemByDocId = useCallback((docId, patch) => {
    setItems((prev) => prev.map((it) => (it.docId === docId ? { ...it, ...patch } : it)))
  }, [setItems])

  const addFiles = useCallback((newFiles) => {
    const pdfs = newFiles.filter((f) => f.type === 'application/pdf')
    if (pdfs.length !== newFiles.length) toast.error('PDF 파일만 업로드 가능합니다.')

    setItems((prev) => {
      const occupiedCount = prev.filter((it) =>
        it.uploadStatus === 'waiting' ||
        it.uploadStatus === 'uploading' ||
        it.summaryStatus === 'queued' ||
        it.summaryStatus === 'processing'
      ).length
      if (occupiedCount >= MAX_FILES) {
        toast.warning(`진행 중인 파일은 최대 ${MAX_FILES}개까지 유지할 수 있습니다.`)
        return prev
      }

      const existingNames = new Set(
        prev
          .filter((it) => it.uploadStatus !== 'upload_failed' && it.summaryStatus !== 'failed')
          .map((it) => it.file.name)
      )
      const deduped = pdfs.filter((f) => !existingNames.has(f.name))
      if (deduped.length !== pdfs.length) toast.warning('이미 추가된 파일은 제외되었습니다.')

      const availableSlots = MAX_FILES - occupiedCount
      const limited = deduped.slice(0, availableSlots)
      if (limited.length !== deduped.length) toast.warning(`진행 중인 파일은 최대 ${MAX_FILES}개까지 유지할 수 있습니다.`)

      return [...prev, ...limited.map(makeItem)]
    })

    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [fileInputRef, setItems])

  const handleFileChange = useCallback((e) => {
    addFiles(Array.from(e.target.files || []))
  }, [addFiles])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
    addFiles(Array.from(e.dataTransfer.files || []))
  }, [addFiles, setIsDragOver])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [setIsDragOver])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [setIsDragOver])

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click()
  }, [fileInputRef])

  const removeItem = useCallback((fileObj) => {
    setItems((prev) => prev.filter((it) => !isSameFile(it, fileObj)))
  }, [setItems])

  const stopPolling = useCallback((docId) => {
    const timer = pollTimersRef.current.get(docId)
    if (timer) {
      clearTimeout(timer)
      pollTimersRef.current.delete(docId)
    }
  }, [])

  const isAbortError = useCallback((err) => (
    err?.code === 'ERR_CANCELED' ||
    err?.name === 'CanceledError' ||
    err?.name === 'AbortError'
  ), [])

  const pollDocument = useCallback(async (docId) => {
    try {
      const detail = await fetchDocumentDetail(docId)
      const status = detail.status?.toLowerCase()

      if (status === 'pending') {
        updateItemByDocId(docId, { summaryStatus: 'queued' })
      } else if (status === 'processing') {
        updateItemByDocId(docId, { summaryStatus: 'processing' })
      } else if (status === 'done') {
        updateItemByDocId(docId, {
          summaryStatus: 'done',
          summary: {
            content: detail.summary_text,
            key_points: detail.key_points ?? [],
          },
        })
        stopPolling(docId)
        return
      } else if (status === 'failed') {
        updateItemByDocId(docId, {
          summaryStatus: 'failed',
          error: '처리 중 오류가 발생했습니다.',
        })
        stopPolling(docId)
        return
      }

      const timer = setTimeout(() => {
        pollDocument(docId)
      }, POLL_INTERVAL_MS)
      pollTimersRef.current.set(docId, timer)
    } catch {
      const timer = setTimeout(() => {
        pollDocument(docId)
      }, POLL_INTERVAL_MS)
      pollTimersRef.current.set(docId, timer)
    }
  }, [stopPolling, updateItemByDocId])

  const handleUpload = useCallback(async () => {
    if (!groupId) {
      toast.error('업로드할 워크스페이스 정보를 확인할 수 없습니다.')
      return
    }

    const waitingOnly = items.filter((it) => it.uploadStatus === 'waiting')
    if (waitingOnly.length === 0) return

    abortRequestedRef.current = false

    for (const it of waitingOnly) {
      if (abortRequestedRef.current) break

      const controller = new AbortController()
      uploadControllersRef.current.set(it.file, controller)

      try {
        updateItem(it.file, {
          uploadStatus: 'uploading',
          progress: 5,
          error: null,
        })
        const uploadData = await uploadDocumentApi(it.file, groupId, controller.signal)
        const docId = uploadData.document_ids[0]
        updateItem(it.file, {
          docId,
          uploadStatus: 'uploaded',
          summaryStatus: 'queued',
          progress: 100,
        })
        stopPolling(docId)
        pollDocument(docId)
      } catch (err) {
        if (!isAbortError(err)) {
          updateItem(it.file, {
            uploadStatus: 'upload_failed',
            error: err.message || '업로드 실패',
          })
        }
      } finally {
        uploadControllersRef.current.delete(it.file)
      }
    }
  }, [groupId, isAbortError, items, pollDocument, stopPolling, updateItem])

  const resetUploadState = useCallback(() => {
    for (const timer of pollTimersRef.current.values()) {
      clearTimeout(timer)
    }
    pollTimersRef.current.clear()
    setItems([])
  }, [setItems])

  const cancelUploadsAndReset = useCallback(() => {
    abortRequestedRef.current = true
    for (const controller of uploadControllersRef.current.values()) {
      controller.abort()
    }
    uploadControllersRef.current.clear()
    resetUploadState()
  }, [resetUploadState])

  return {
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    handleUpload,
    cancelUploadsAndReset,
    resetUploadState,
    waitingItems: items.filter((it) => it.uploadStatus === 'waiting'),
    uploadItems: items.filter((it) => it.uploadStatus !== 'waiting'),
    isUploadingFiles: items.some((it) => it.uploadStatus === 'uploading'),
  }
}
