import { getGroupDocuments, getMembers } from '@/api/groups'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Label } from '@/components/ui/Label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FileText, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import FileDropzone from '../../features/upload/components/FileDropzone.jsx'
import FileStatusItem from '../../features/upload/components/FileStatusItem.jsx'
import UploadSummaryCards from '../../features/upload/components/UploadSummaryCards.jsx'
import { useUpload } from '../../features/upload/context/UploadContext.jsx'
import { MAX_FILES } from '../../features/upload/uploadState.js'

const STATUS_POLLING_INTERVAL = 5000

function UploadPageInner() {
  const {
    groupId,
    fileInputRef,
    isDragOver,
    waitingItems = [],
    uploadItems = [],
    isUploadingFiles,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    handleUpload,
  } = useUpload()

  const [statusCounts, setStatusCounts] = useState({
    inProgress: 0,
    done: 0,
    failed: 0,
  })
  const [reviewerOptions, setReviewerOptions] = useState([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [assigneeValue, setAssigneeValue] = useState('unassigned')
  const [serverDocuments, setServerDocuments] = useState([])

  const hasUploadingItems = uploadItems.some(
    (it) => it.uploadStatus === 'uploading'
  )

  const hasWaitingItems = waitingItems.length > 0
  const showDropzone = !hasUploadingItems

  const loadServerDocuments = useCallback(async () => {
    if (!groupId) return

    try {
      const [pendingRes, processingRes, doneRes, failedRes] = await Promise.all([
        getGroupDocuments(groupId, { skip: 0, limit: 50, status: 'PENDING', viewType: 'my' }),
        getGroupDocuments(groupId, { skip: 0, limit: 50, status: 'PROCESSING', viewType: 'my' }),
        getGroupDocuments(groupId, { skip: 0, limit: 50, status: 'DONE', viewType: 'my' }),
        getGroupDocuments(groupId, { skip: 0, limit: 50, status: 'FAILED', viewType: 'my' }),
      ])

      setStatusCounts({
        inProgress: pendingRes.total + processingRes.total,
        done: doneRes.total,
        failed: failedRes.total,
      })

      setServerDocuments([
        ...pendingRes.items,
        ...processingRes.items,
        ...doneRes.items,
        ...failedRes.items,
      ])
    } catch {
      setStatusCounts({
        inProgress: 0,
        done: 0,
        failed: 0,
      })
      setServerDocuments([])
    }
  }, [groupId])

  const loadReviewerOptions = useCallback(async () => {
    if (!groupId) return

    setMembersLoading(true)
    try {
      const data = await getMembers(groupId)
      const members = data?.members ?? []

      const reviewers = members.filter(
        (member) =>
          member.status === 'ACTIVE' &&
          (member.role === 'OWNER' || member.role === 'ADMIN')
      )

      setReviewerOptions(reviewers)
    } catch {
      setReviewerOptions([])
    } finally {
      setMembersLoading(false)
    }
  }, [groupId])

  useEffect(() => {
    loadServerDocuments()
    loadReviewerOptions()
  }, [loadServerDocuments, loadReviewerOptions])

  useEffect(() => {
    const hasTrackableItems =
      uploadItems.length > 0 ||
      statusCounts.inProgress > 0

    if (!hasTrackableItems) return

    const timerId = window.setInterval(() => {
      loadServerDocuments()
    }, STATUS_POLLING_INTERVAL)

    return () => window.clearInterval(timerId)
  }, [uploadItems.length, statusCounts.inProgress, loadServerDocuments])

  const recentItems = useMemo(() => {
    return [...uploadItems]
      .map((item) => {
        const serverDoc = item.docId
          ? serverDocuments.find((doc) => doc.id === item.docId)
          : null

        return {
          ...item,
          serverDoc,
        }
      })
      .reverse()
  }, [uploadItems, serverDocuments])

  const handleStartUpload = async () => {
    await handleUpload()
    await loadServerDocuments()
  }

  return (
    <div className="max-w-4xl mx-auto px-4 flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">AI 요약 현황</h2>
          <p className="text-sm text-muted-foreground">
            업로드가 끝난 문서의 요약 처리 상태를 확인할 수 있습니다.
          </p>
        </div>

        <UploadSummaryCards counts={statusCounts} />
      </section>

      <Card className="p-5 sm:p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-base font-semibold">문서 업로드</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            파일을 드래그 앤 드롭하거나 클릭하여 선택하세요. 최대 {MAX_FILES}개까지 가능합니다.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="assignee">승인 담당자 (선택)</Label>
          <Select
            value={assigneeValue}
            onValueChange={setAssigneeValue}
            disabled={membersLoading || hasUploadingItems}
          >
            <SelectTrigger id="assignee" className="w-full">
              <SelectValue placeholder="담당자 미지정" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="unassigned">담당자 미지정</SelectItem>
              {reviewerOptions.map((member) => (
                <SelectItem key={member.user_id} value={String(member.user_id)}>
                  {member.username} ({member.role})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            담당자를 지정하지 않으면 개별 알림은 발송되지 않습니다.
          </p>
        </div>

        {showDropzone && (
          <FileDropzone
            fileInputRef={fileInputRef}
            isUploading={false}
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
            현재 업로드가 진행 중입니다.
          </div>
        )}

        {hasWaitingItems && (
          <ul className="flex flex-col gap-2">
            {waitingItems.map((it) => (
              <li
                key={it.file.name}
                className="flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm"
              >
                <FileText size={15} className="text-muted-foreground shrink-0" />
                <span className="flex-1 truncate">{it.file.name}</span>
                <span className="text-xs text-muted-foreground">대기 중</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground hover:text-foreground"
                  onClick={() => removeItem(it)}
                >
                  <X size={13} />
                </Button>
              </li>
            ))}
          </ul>
        )}


        <Button
          onClick={handleStartUpload}
          disabled={waitingItems.length === 0 || isUploadingFiles}
          className="w-full"
        >
          {isUploadingFiles ? '처리 중...' : '업로드 및 요약 생성'}
        </Button>
      </Card>

      {recentItems.length > 0 && (
        <Card className="p-5 sm:p-6 flex flex-col gap-4">
          <div>
            <h3 className="text-base font-semibold">처리 현황</h3>
            <p className="text-sm text-muted-foreground mt-0.5">
              업로드한 파일의 진행 상태를 바로 확인할 수 있습니다.
            </p>
          </div>

          <ul className="flex flex-col gap-2">
            {recentItems.map((it) => (
              <FileStatusItem
                key={`${it.file.name}-${it.uploadStatus}-${it.serverDoc?.status ?? 'NONE'}`}
                it={it}
                onRemove={removeItem}
              />
            ))}
          </ul>

        </Card>
      )}
    </div>
  )
}

export default function UploadPage() {
  return <UploadPageInner />
}
