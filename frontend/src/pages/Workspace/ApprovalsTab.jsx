import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, Search, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'

import {
    approveDocument,
    getApprovedDocuments,
    getApprovedUploaders,
    getPendingDocuments,
    getPendingUploaders,
    getRejectedDocuments,
    getRejectedUploaders,
    rejectDocument,
} from '@/shared/api/groups'
import { formatKoreanDateTime } from '@/shared/lib/datetime'
import { Button } from '@/shared/ui/Button'
import { ConfirmModal } from '@/shared/ui/confirm-modal'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/shared/ui/Dialog'
import { Input } from '@/shared/ui/Input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

const APPROVAL_SUB_TABS = [
    { key: 'pending', label: '처리 대기' },
    { key: 'approved', label: '승인 완료' },
    { key: 'rejected', label: '반려' },
]

const PROCESSING_STATUS_META = {
    DONE: { label: '완료', className: 'text-green-600' },
    PROCESSING: { label: '처리중', className: 'text-yellow-600' },
    PENDING: { label: '대기', className: 'text-muted-foreground' },
    FAILED: { label: '실패', className: 'text-destructive' },
}

const LIMIT = 10

/**
 * UTC naive 시간을 한국 시간 문자열로 변환한다.
 */
function formatDateTime(value) {
    return formatKoreanDateTime(value)
}


function getProcessingStatusMeta(status) {
    return PROCESSING_STATUS_META[status] ?? {
        label: status,
        className: 'text-muted-foreground',
    }
}


export default function ApprovalsTab({ group }) {
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()

    const isWritable = group.status === 'ACTIVE'
    const isWriteRestricted = group.status !== 'ACTIVE'
    const isSubscriptionExpiredPending =
        group.status === 'DELETE_PENDING' &&
        group.pending_reason === 'SUBSCRIPTION_EXPIRED'

    const activeSubTab = searchParams.get('approval_tab') || 'pending'
    const page = Number(searchParams.get('approval_page') || '1')
    const query = searchParams.get('approval_keyword') || ''
    const authorFilter = searchParams.get('approval_author') || 'all'
    const assigneeFilter = searchParams.get('approval_assignee') || 'all'

    const [keyword, setKeyword] = useState(query)

    const [items, setItems] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const [approveTarget, setApproveTarget] = useState(null)
    const [rejectTarget, setRejectTarget] = useState(null)
    const [rejectReason, setRejectReason] = useState('')
    const [actionLoadingId, setActionLoadingId] = useState(null)
    const [authorOptions, setAuthorOptions] = useState([])

    useEffect(() => {
        setKeyword(query)
    }, [query])

    const updateApprovalParams = useCallback((updates) => {
        const nextParams = new URLSearchParams(searchParams)
        nextParams.set('tab', 'approvals')

        Object.entries(updates).forEach(([key, value]) => {
            if (value === '' || value == null) {
                nextParams.delete(key)
            } else {
                nextParams.set(key, String(value))
            }
        })

        setSearchParams(nextParams)
    }, [searchParams, setSearchParams])

    const handleSubTabChange = (nextTab) => {
        updateApprovalParams({
            approval_tab: nextTab,
            approval_page: 1,
            approval_author: 'all',
            approval_assignee: 'all',
        })
    }

    const handleSearch = () => {
        updateApprovalParams({
            approval_tab: activeSubTab,
            approval_page: 1,
            approval_keyword: keyword.trim(),
        })
    }

    const handleAuthorFilterChange = (nextAuthor) => {
        updateApprovalParams({
            approval_tab: activeSubTab,
            approval_page: 1,
            approval_author: nextAuthor,
        })
    }

    const handleAssigneeFilterChange = (nextAssignee) => {
        updateApprovalParams({
            approval_tab: activeSubTab,
            approval_page: 1,
            approval_assignee: nextAssignee,
        })
    }

    const handleResetFilters = () => {
        setKeyword('')
        updateApprovalParams({
            approval_tab: activeSubTab,
            approval_page: 1,
            approval_keyword: '',
            approval_author: 'all',
            approval_assignee: 'all',
        })
    }

    const movePage = (nextPage) => {
        updateApprovalParams({
            approval_tab: activeSubTab,
            approval_page: nextPage,
        })
    }

    const loadDocuments = useCallback(async (tab, nextPage = page, nextQuery = query) => {
        setLoading(true)
        setError('')

        try {
            const commonParams = {
                skip: (nextPage - 1) * LIMIT,
                limit: LIMIT,
                keyword: nextQuery,
                uploader: authorFilter === 'all' ? '' : authorFilter,
            }

            const response =
                tab === 'pending'
                    ? await getPendingDocuments(group.id, {
                        ...commonParams,
                        assigneeType: assigneeFilter,
                    })
                    : tab === 'approved'
                        ? await getApprovedDocuments(group.id, commonParams)
                        : await getRejectedDocuments(group.id, commonParams)

            setItems(response.items ?? [])
            setTotal(response.total ?? 0)
        } catch (e) {
            const fallback =
                tab === 'pending'
                    ? '승인 대기 문서를 불러오지 못했습니다.'
                    : tab === 'approved'
                        ? '승인 완료 문서를 불러오지 못했습니다.'
                        : '반려 문서를 불러오지 못했습니다.'
            setError(e.message || fallback)
        } finally {
            setLoading(false)
        }
    }, [group.id, page, query, authorFilter, assigneeFilter])

    useEffect(() => {
        loadDocuments(activeSubTab, page, query)
    }, [activeSubTab, page, query, authorFilter, assigneeFilter, loadDocuments])

    useEffect(() => {
        const loadAuthorOptions = async () => {
            try {
                const response =
                    activeSubTab === 'pending'
                        ? await getPendingUploaders(group.id)
                        : activeSubTab === 'approved'
                            ? await getApprovedUploaders(group.id)
                            : await getRejectedUploaders(group.id)

                setAuthorOptions(response.items ?? [])
            } catch {
                setAuthorOptions([])
            }
        }

        loadAuthorOptions()
    }, [group.id, activeSubTab])

    const totalPages = Math.ceil(total / LIMIT)
    const currentPage = page
    const maxVisiblePages = 5

    /**
     * 현재 페이지에 표시 중인 승인 문서 범위를 계산한다.
     */
    const startItem = total === 0 ? 0 : (page - 1) * LIMIT + 1
    const endItem = Math.min((page - 1) * LIMIT + items.length, total)

    /**
     * 현재 서브탭 라벨을 반환한다.
     */
    const currentTabLabel = {
        pending: '처리 대기',
        approved: '승인 완료',
        rejected: '반려',
    }[activeSubTab] ?? '문서'

    let startPage = Math.max(1, currentPage - 2)
    let endPage = Math.min(totalPages, currentPage + 2)

    if (endPage - startPage + 1 < maxVisiblePages) {
        if (startPage === 1) {
            endPage = Math.min(totalPages, startPage + maxVisiblePages - 1)
        } else if (endPage === totalPages) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1)
        }
    }

    const handleApprove = async () => {
        if (!approveTarget) return

        setActionLoadingId(approveTarget.id)
        try {
            await approveDocument(group.id, approveTarget.id)
            toast.success('문서를 승인했습니다.')
            setApproveTarget(null)

            const nextTotal = total - 1
            const nextTotalPages = Math.max(1, Math.ceil(nextTotal / LIMIT))
            const nextPage = Math.min(page, nextTotalPages)

            if (nextPage !== page) {
                updateApprovalParams({
                    approval_tab: 'pending',
                    approval_page: nextPage,
                })
            } else {
                await loadDocuments('pending', nextPage, query)
            }
        } catch (e) {
            toast.error(e.message || '문서 승인에 실패했습니다.')
        } finally {
            setActionLoadingId(null)
        }
    }

    const handleReject = async () => {
        if (!rejectTarget || !rejectReason.trim()) return

        setActionLoadingId(rejectTarget.id)
        try {
            await rejectDocument(group.id, rejectTarget.id, rejectReason.trim())
            toast.success('문서를 반려했습니다.')
            setRejectTarget(null)
            setRejectReason('')

            const nextTotal = total - 1
            const nextTotalPages = Math.max(1, Math.ceil(nextTotal / LIMIT))
            const nextPage = Math.min(page, nextTotalPages)

            if (nextPage !== page) {
                updateApprovalParams({
                    approval_tab: 'pending',
                    approval_page: nextPage,
                })
            } else {
                await loadDocuments('pending', nextPage, query)
            }
        } catch (e) {
            toast.error(e.message || '문서 반려에 실패했습니다.')
        } finally {
            setActionLoadingId(null)
        }
    }

    const buildApprovalDetailSearch = useCallback(() => {
        const nextParams = new URLSearchParams(searchParams)
        nextParams.set('comment_scope', 'review')
        return nextParams.toString()
    }, [searchParams])

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {isWriteRestricted && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <div className="text-amber-800">
                        <div>
                            <p className="text-amber-800">
                                {isSubscriptionExpiredPending
                                    ? '구독 만료 상태에서는 승인/반려 처리는 사용할 수 없고, 목록 조회와 다운로드만 가능합니다.'
                                    : '삭제 예정 상태에서는 승인/반려 처리가 제한되며, 목록 조회와 다운로드만 가능합니다.'}
                            </p>
                        </div>
                    </div>
                </div>
            )}
            <div className="space-y-1">
                <h2 className="text-base font-semibold">문서 승인 관리</h2>
                <p className="text-sm text-muted-foreground">
                    처리 가능한 승인 요청을 확인하고 승인 또는 반려할 수 있습니다.
                </p>
            </div>

            <div className="flex gap-2 border-b">
                {APPROVAL_SUB_TABS.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => handleSubTabChange(tab.key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            activeSubTab === tab.key
                                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                                : 'border-transparent text-muted-foreground hover:text-foreground'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            <div className="space-y-1">
                {activeSubTab === 'pending' && (
                    <>
                        <h3 className="font-semibold">처리 대기</h3>
                        <p className="text-sm text-muted-foreground">
                            내가 처리 가능한 전체 승인 대기 문서입니다. 담당자가 지정되어 있어도 OWNER/ADMIN은 대신 처리할 수 있습니다.
                        </p>
                    </>
                )}

                {activeSubTab === 'approved' && (
                    <>
                        <h3 className="font-semibold">승인 완료</h3>
                        <p className="text-sm text-muted-foreground">
                            내가 승인한 문서 이력을 확인할 수 있습니다.
                        </p>
                    </>
                )}

                {activeSubTab === 'rejected' && (
                    <>
                        <h3 className="font-semibold">반려</h3>
                        <p className="text-sm text-muted-foreground">
                            내가 반려한 문서와 반려 사유를 확인할 수 있습니다.
                        </p>
                    </>
                )}
            </div>

            <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4">
                <div className="flex min-w-0 flex-1 gap-2">
                    <Input
                        placeholder="문서명 검색"
                        value={keyword}
                        onChange={(e) => setKeyword(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        className="min-w-0 flex-1"
                    />
                    <Button variant="outline" onClick={handleSearch}>
                        <Search className="h-4 w-4" />
                    </Button>
                </div>

                <Select value={authorFilter} onValueChange={handleAuthorFilterChange}>
                    <SelectTrigger className="w-full sm:w-44">
                        <SelectValue placeholder="업로더 전체" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">업로더 전체</SelectItem>
                        {authorOptions.map((author) => (
                            <SelectItem key={author} value={author}>
                                {author}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {activeSubTab === 'pending' && (
                    <Select value={assigneeFilter} onValueChange={handleAssigneeFilterChange}>
                        <SelectTrigger className="w-full sm:w-48">
                            <SelectValue placeholder="담당자 전체" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">담당자 전체</SelectItem>
                            <SelectItem value="mine">내게 지정됨</SelectItem>
                            <SelectItem value="unassigned">미지정</SelectItem>
                            <SelectItem value="others">다른 담당자 지정</SelectItem>
                        </SelectContent>
                    </Select>
                )}

                <Button
                    variant="outline"
                    onClick={handleResetFilters}
                    className="gap-2"
                >
                    <RotateCcw className="h-4 w-4" />
                    초기화
                </Button>
            </div>

            {!loading && !error && total > 0 && (
                <div className="flex justify-end text-sm text-muted-foreground mb-2">
                    <span>{currentTabLabel} 문서 {total}개 중 {startItem}-{endItem}</span>
                </div>
            )}

            {loading ? (
                <div className="flex justify-center py-16">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : error ? (
                <div className="py-16 text-center text-sm text-destructive">{error}</div>
            ) : items.length === 0 ? (
                <div className="rounded-lg border py-16 text-center text-sm text-muted-foreground">
                    {activeSubTab === 'pending' && '처리할 승인 대기 문서가 없습니다.'}
                    {activeSubTab === 'approved' && '승인 완료 문서가 없습니다.'}
                    {activeSubTab === 'rejected' && '반려 문서가 없습니다.'}
                </div>
            ) : (
                <>
                    {activeSubTab === 'pending' && (
                        <div className="rounded-lg border divide-y">
                            {items.map((item) => {
                                const processingMeta = getProcessingStatusMeta(item.status)
                                const isBusy = actionLoadingId === item.id

                                return (
                                    <div
                                        key={item.id}
                                        className="flex items-start justify-between gap-4 px-5 py-4 transition-colors hover:bg-muted/50"
                                    >
                                        <div
                                            className="min-w-0 flex-1 cursor-pointer"
                                            onClick={() =>
                                                navigate(`/workspace/${group.id}/documents/${item.id}?${buildApprovalDetailSearch()}`)
                                            }
                                        >
                                            <p className="text-sm font-medium truncate">{item.title}</p>

                                            {item.preview && (
                                                <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                                                    {item.preview}
                                                </p>
                                            )}

                                            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                                <span className="rounded-sm bg-muted px-2 py-0.5 text-foreground">
                                                    {item.document_type || '유형 없음'}
                                                </span>
                                                <span>업로더 {item.uploader || '-'}</span>
                                                <span>검토 댓글 {item.comment_count ?? 0}개</span>
                                                <span>업로드 {formatDateTime(item.created_at)}</span>
                                                <span>담당자 {item.assignee_username || '미지정'}</span>
                                                <span className={processingMeta.className}>
                                                    요약 {processingMeta.label}
                                                </span>
                                            </div>
                                        </div>

                                        {activeSubTab === 'pending' && isWritable && (
                                            <div className="flex shrink-0 items-center gap-2">
                                                <Button
                                                    size="sm"
                                                    disabled={isBusy}
                                                    onClick={() => setApproveTarget(item)}
                                                >
                                                    {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : '승인'}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    disabled={isBusy}
                                                    onClick={() => {
                                                        setRejectTarget(item)
                                                        setRejectReason('')
                                                    }}
                                                >
                                                    반려
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {activeSubTab === 'approved' && (
                        <div className="rounded-lg border divide-y">
                            {items.map((item) => {
                                const processingMeta = getProcessingStatusMeta(item.status)

                                return (
                                    <div
                                        key={item.id}
                                        className="px-5 py-4 cursor-pointer transition-colors hover:bg-muted/50"
                                        onClick={() =>
                                            navigate(`/workspace/${group.id}/documents/${item.id}?${buildApprovalDetailSearch()}`)
                                        }
                                    >
                                        <p className="text-sm font-medium truncate">{item.title}</p>

                                        {item.preview && (
                                            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                                                {item.preview}
                                            </p>
                                        )}

                                        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                            <span className="rounded-sm bg-muted px-2 py-0.5 text-foreground">
                                                {item.document_type || '유형 없음'}
                                            </span>
                                            <span>업로더 {item.uploader || '-'}</span>
                                            <span>검토 댓글 {item.comment_count ?? 0}개</span>
                                            <span>승인일 {formatDateTime(item.reviewed_at)}</span>
                                            <span>담당자 {item.assignee_username || '미지정'}</span>
                                            <span className={processingMeta.className}>
                                                요약 {processingMeta.label}
                                            </span>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {activeSubTab === 'rejected' && (
                        <div className="rounded-lg border divide-y">
                            {items.map((item) => {
                                const processingMeta = getProcessingStatusMeta(item.status)

                                return (
                                    <div
                                        key={item.id}
                                        className="px-5 py-4 cursor-pointer transition-colors hover:bg-muted/50"
                                        onClick={() =>
                                            navigate(`/workspace/${group.id}/documents/${item.id}?${buildApprovalDetailSearch()}`)
                                        }
                                    >
                                        <p className="text-sm font-medium truncate">{item.title}</p>

                                        {item.preview && (
                                            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                                                {item.preview}
                                            </p>
                                        )}

                                        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                            <span className="rounded-sm bg-muted px-2 py-0.5 text-foreground">
                                                {item.document_type || '유형 없음'}
                                            </span>
                                            <span>업로더 {item.uploader || '-'}</span>
                                            <span>검토 댓글 {item.comment_count ?? 0}개</span>
                                            <span>반려일 {formatDateTime(item.reviewed_at)}</span>
                                            <span className={processingMeta.className}>
                                                요약 {processingMeta.label}
                                            </span>
                                        </div>

                                        {item.feedback && (
                                            <div className="mt-3 border-l-2 border-blue-500 bg-blue-50/60 px-3 py-2">
                                                <p className="text-[11px] font-semibold text-blue-700">반려 사유</p>
                                                <p className="mt-1 text-sm text-slate-700 line-clamp-2">
                                                    {item.feedback}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                )
                            })}
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
                                {Array.from(
                                    { length: endPage - startPage + 1 },
                                    (_, i) => startPage + i
                                ).map((p) => (
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
                </>
            )}

            <ConfirmModal
                open={approveTarget !== null}
                message={
                    approveTarget
                        ? `"${approveTarget.title}" 문서를 승인하시겠습니까?`
                        : ''
                }
                confirmLabel="승인"
                onConfirm={handleApprove}
                onCancel={() => setApproveTarget(null)}
            />

            <Dialog
                open={rejectTarget !== null}
                onOpenChange={(open) => {
                    if (!open) {
                        setRejectTarget(null)
                        setRejectReason('')
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>문서 반려</DialogTitle>
                    </DialogHeader>

                    <div className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            {rejectTarget
                                ? `"${rejectTarget.title}" 문서의 반려 사유를 입력해주세요.`
                                : '반려 사유를 입력해주세요.'}
                        </p>
                        <Textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="반려 사유를 입력하세요"
                            rows={5}
                            maxLength={1000}
                        />
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                setRejectTarget(null)
                                setRejectReason('')
                            }}
                        >
                            취소
                        </Button>
                        <Button
                            onClick={handleReject}
                            disabled={actionLoadingId === rejectTarget?.id}
                        >
                            {actionLoadingId === rejectTarget?.id ? '처리 중...' : '반려'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
