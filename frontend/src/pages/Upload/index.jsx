import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { getGroupDocuments } from '@/api/groups.js'
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import FileDropzone from '../../features/upload/components/FileDropzone.jsx'
import UploadProgressDialog from '../../features/upload/components/UploadProgressDialog.jsx'
import UploadSummaryCards from '../../features/upload/components/UploadSummaryCards.jsx'
import UploadWaitingList from '../../features/upload/components/UploadWaitingList.jsx'
import { UploadProvider, useUpload } from '../../features/upload/context/UploadContext.jsx'
import { MAX_FILES } from '../../features/upload/uploadState.js'

function UploadPageInner() {
  const {
    groupId,
    fileInputRef,
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
  } = useUpload()
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [statusCounts, setStatusCounts] = useState({
    inProgress: 0,
    done: 0,
    failed: 0,
  })

  const activeCount = statusCounts.inProgress
  const isUploadLocked = activeCount >= MAX_FILES
  const hasWaitingItems = waitingItems.length > 0
  const showDropzone = !isUploadLocked
  const loadStatusCounts = useCallback(async () => {
    if (!groupId) return

    const [pendingRes, processingRes, doneRes, failedRes] = await Promise.all([
      getGroupDocuments(groupId, { skip: 0, limit: 1, status: 'PENDING', viewType: 'my' }),
      getGroupDocuments(groupId, { skip: 0, limit: 1, status: 'PROCESSING', viewType: 'my' }),
      getGroupDocuments(groupId, { skip: 0, limit: 1, status: 'DONE', viewType: 'my' }),
      getGroupDocuments(groupId, { skip: 0, limit: 1, status: 'FAILED', viewType: 'my' }),
    ])

    setStatusCounts({
      inProgress: pendingRes.total + processingRes.total,
      done: doneRes.total,
      failed: failedRes.total,
    })
  }, [groupId])


  useEffect(() => {
    loadStatusCounts()
  }, [loadStatusCounts])

  const handleStartUpload = async () => {
    setUploadModalOpen(true)
    await handleUpload()
    await loadStatusCounts()
  }

  const handleCloseUploadModal = () => {
    setUploadModalOpen(false)
    if (isUploadingFiles || waitingItems.length > 0) {
      cancelUploadsAndReset()
      return
    }
    resetUploadState()
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-6">

      <section className="text-center flex flex-col gap-2">
        <h1 className="text-2xl font-bold">그룹 문서 업로드</h1>
        <p className="text-sm text-muted-foreground">
          그룹 문서 PDF를 먼저 업로드하고, AI 요약은 서버에서 순차적으로 처리합니다.
        </p>
        <p className="text-xs text-muted-foreground">
          아래 상태는 이 그룹에 내가 업로드한 문서 기준으로 집계됩니다.
        </p>
      </section>

      <Card className="p-6 flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold">문서 업로드</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            파일 업로드는 즉시 처리되고, AI 요약 대기/처리 문서는 최대 {MAX_FILES}개까지 유지됩니다.
          </p>
        </div>

        {showDropzone && (
          <FileDropzone
            fileInputRef={fileInputRef}
            isUploading={isUploadLocked}
            isDragOver={isDragOver}
            onOpenPicker={openFilePicker}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          />
        )}

        {!showDropzone && (
          <div className="rounded-xl border border-dashed px-6 py-6 text-center text-sm text-muted-foreground">
            AI 요약 대기/처리 중인 문서가 {MAX_FILES}개입니다. 완료 또는 실패 후 다시 업로드할 수 있습니다.
          </div>
        )}

        <UploadWaitingList items={waitingItems} onRemove={removeItem} />

        <Button
          onClick={handleStartUpload}
          disabled={waitingItems.length === 0}
          className="w-full"
        >
          {hasWaitingItems ? '파일 업로드 시작' : '업로드할 파일을 선택하세요'}
        </Button>
      </Card>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-base font-semibold">AI 요약 현황</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            업로드가 끝난 문서의 요약 처리 상태를 확인할 수 있습니다.
          </p>
        </div>

        <UploadSummaryCards counts={statusCounts} />
      </section>

      <UploadProgressDialog
        open={uploadModalOpen}
        items={uploadItems}
        canCancel={isUploadingFiles || waitingItems.length > 0}
        onClose={handleCloseUploadModal}
      />
    </div>
  )
}

export default function UploadPage() {
  const { group_id } = useParams()

  return (
    <UploadProvider groupId={group_id}>
      <UploadPageInner />
    </UploadProvider>
  )
}
