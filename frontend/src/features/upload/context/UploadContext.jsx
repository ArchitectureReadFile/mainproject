import { createContext, useContext, useMemo, useRef, useState } from 'react'
import { useUploadQueue } from '../hooks/useUploadQueue.js'

const UploadContext = createContext(null)

export function UploadProvider({ children, groupId }) {
  const fileInputRef = useRef(null)

  const [items, setItems] = useState([])
  const [isDragOver, setIsDragOver] = useState(false)

  const {
    waitingItems,
    uploadItems,
    isUploadingFiles,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    handleUpload,
    cancelUploadsAndReset,
    resetUploadState,
  } = useUploadQueue({
    fileInputRef,
    groupId,
    items,
    setItems,
    setIsDragOver,
  })

  const value = useMemo(() => ({
    groupId,
    fileInputRef,
    items,
    isDragOver,
    waitingItems,
    uploadItems,
    isUploadingFiles,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    handleUpload,
    cancelUploadsAndReset,
    resetUploadState,
  }), [
    groupId,
    items,
    isDragOver,
    waitingItems,
    uploadItems,
    isUploadingFiles,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    handleUpload,
    cancelUploadsAndReset,
    resetUploadState,
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
