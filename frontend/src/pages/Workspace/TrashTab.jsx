import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArchiveRestore, Loader2, Trash2 } from 'lucide-react'
import { getDeletedGroupDocuments, restoreGroupDocument } from '@/api/groups'
import { Button } from '@/components/ui/Button'
import { toast } from 'sonner'

const LIMIT = 5

function calcDday(isoDate) {
  if (!isoDate) return '-'
  const diff = Math.ceil((new Date(isoDate) - new Date()) / (1000 * 60 * 60 * 24))
  return diff <= 0 ? 'D-0' : `D-${diff}`
}

export default function TrashTab({ group }) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const page = Number(searchParams.get('page') || '1')
  const isWritable = group.status === 'ACTIVE'
  const isWriteRestricted = group.status !== 'ACTIVE'
  const isSubscriptionExpiredPending =
    group.status === 'DELETE_PENDING' &&
    group.pending_reason === 'SUBSCRIPTION_EXPIRED'

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [restoringId, setRestoringId] = useState(null)

  const skip = (page - 1) * LIMIT
  const totalPages = Math.ceil(total / LIMIT)
  const currentPage = Math.floor(skip / LIMIT) + 1
  const maxVisiblePages = 5

  let startPage = Math.max(1, currentPage - 2)
  let endPage = Math.min(totalPages, currentPage + 2)

  if (endPage - startPage + 1 < maxVisiblePages) {
    if (startPage === 1) {
      endPage = Math.min(totalPages, startPage + maxVisiblePages - 1)
    } else if (endPage === totalPages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1)
    }
  }

  const load = useCallback(async (nextPage = page, showLoading = true) => {
    if (showLoading) {
      setLoading(true)
    }
    setError(null)

    try {
      const res = await getDeletedGroupDocuments(group.id, {
        skip: (nextPage - 1) * LIMIT,
        limit: LIMIT,
      })

      setItems(res.items)
      setTotal(res.total)
    } catch (e) {
      setError(e.message || '휴지통 문서를 불러오지 못했습니다.')
    } finally {
      if (showLoading) {
        setLoading(false)
      }
    }
  }, [group.id, page])

  useEffect(() => {
    load()
  }, [load])

  const movePage = (nextPage) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('tab', 'trash')
    newParams.set('page', String(nextPage))
    setSearchParams(newParams)
  }

  const handleRestore = async (e, docId) => {
    e.stopPropagation()
    setRestoringId(docId)

    try {
      await restoreGroupDocument(group.id, docId)
      toast.success('문서를 복구했습니다.')

      const nextTotal = Math.max(0, total - 1)
      const nextTotalPages = Math.ceil(nextTotal / LIMIT)
      const nextPage =
        page > 1 && items.length === 1
          ? Math.min(page - 1, Math.max(nextTotalPages, 1))
          : page

      const newParams = new URLSearchParams(searchParams)
      newParams.set('tab', 'trash')
      newParams.set('page', String(nextPage))
      setSearchParams(newParams)

      await load(nextPage, false)
    } catch (e) {
      toast.error(e.message || '문서 복구에 실패했습니다.')
    } finally {
      setRestoringId(null)
    }
  }

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      {isWriteRestricted && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <div className="text-amber-800">
                  <div>
                      <p className="text-amber-800">
                          {isSubscriptionExpiredPending
                              ? '구독 만료 상태에서는 승인/반려 처리는 사용할 수 없고, 목록 조회와 다운로드만 가능합니다.'
                              : '삭제 예정 상태에서는 복구 처리가 제한되며, 목록 조회와 다운로드만 가능합니다.'}
                      </p>
                  </div>
              </div>
          </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="py-16 text-center text-sm text-destructive">{error}</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-20 text-center text-muted-foreground">
          <Trash2 className="h-10 w-10" />
          <p className="text-sm">휴지통에 문서가 없습니다.</p>
        </div>
      ) : (
        <div className="rounded-lg border divide-y">
          {items.map((doc) => (
            <div
              key={doc.id}
              onClick={() =>
                navigate(
                  `/workspace/${group.id}/documents/${doc.id}?tab=trash&page=${page}`
                )
              }
              className="flex items-start justify-between px-5 py-4 gap-4 cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex-1 min-w-0 pr-4">
                <p className="text-sm font-medium truncate">{doc.title}</p>
                {doc.preview && (
                  <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                    {doc.preview}
                  </p>
                )}
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span className="rounded-sm bg-muted px-2 py-0.5 text-foreground">
                    {doc.document_type || '유형 없음'}
                  </span>
                  <span>업로더 {doc.uploader}</span>
                  <span>
                    삭제 요청{' '}
                    {doc.delete_requested_at
                      ? new Date(doc.delete_requested_at).toLocaleDateString('ko-KR')
                      : '-'}
                  </span>
                  <span>
                    삭제 예정{' '}
                    {doc.delete_scheduled_at
                      ? new Date(doc.delete_scheduled_at).toLocaleDateString('ko-KR')
                      : '-'}
                  </span>
                  <span className="font-medium text-destructive">
                    {calcDday(doc.delete_scheduled_at)}
                  </span>
                </div>
              </div>

              {isWritable && (
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0 gap-1.5"
                  disabled={restoringId === doc.id}
                  onClick={(e) => handleRestore(e, doc.id)}
                >
                  {restoringId === doc.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArchiveRestore className="h-4 w-4" />
                  )}
                  복구
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(1)}
            disabled={currentPage === 1}
          >
            처음
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(currentPage - 1)}
            disabled={currentPage === 1}
          >
            이전
          </Button>

          <div className="flex items-center gap-1">
            {Array.from({ length: endPage - startPage + 1 }, (_, i) => startPage + i).map((p) => (
              <Button
                key={p}
                variant={p === currentPage ? 'default' : 'outline'}
                size="sm"
                onClick={() => movePage(p)}
              >
                {p}
              </Button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            다음
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(totalPages)}
            disabled={currentPage === totalPages}
          >
            마지막
          </Button>
        </div>
      )}
    </div>
  )
}
