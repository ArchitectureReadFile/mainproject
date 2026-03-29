import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'

import {
    approveDocument,
    getPendingDocuments,
    rejectDocument,
} from '@/api/groups'
import { Button } from '@/components/ui/Button'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/Textarea'
import { useAuth } from '@/features/auth'

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

function formatDate(value) {
    return new Date(value).toLocaleDateString('ko-KR')
}

function getProcessingStatusMeta(status) {
    return PROCESSING_STATUS_META[status] ?? {
        label: status,
        className: 'text-muted-foreground',
    }
}

export default function ApprovalsTab({ group }) {
    const navigate = useNavigate()
    const { user } = useAuth()

    const [activeSubTab, setActiveSubTab] = useState('pending')
    const [keyword, setKeyword] = useState('')
    const [query, setQuery] = useState('')
    const [authorFilter, setAuthorFilter] = useState('all')
    const [assigneeFilter, setAssigneeFilter] = useState('all')

    const [items, setItems] = useState([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const [approveTarget, setApproveTarget] = useState(null)
    const [rejectTarget, setRejectTarget] = useState(null)
    const [rejectReason, setRejectReason] = useState('')
    const [actionLoadingId, setActionLoadingId] = useState(null)

    const loadPendingDocuments = useCallback(async (nextPage = page, nextQuery = query) => {
        setLoading(true)
        setError('')

        try {
            const response = await getPendingDocuments(group.id, {
                skip: (nextPage - 1) * LIMIT,
                limit: LIMIT,
                keyword: nextQuery,
            })
            setItems(response.items ?? [])
            setTotal(response.total ?? 0)
        } catch (e) {
            setError(e.message || '승인 대기 문서를 불러오지 못했습니다.')
        } finally {
            setLoading(false)
        }
    }, [group.id, page, query])


    useEffect(() => {
        if (activeSubTab !== 'pending') return
        loadPendingDocuments(page, query)
    }, [activeSubTab, page, query, loadPendingDocuments])


    const authorOptions = useMemo(() => {
        const authors = Array.from(
            new Set(items.map((item) => item.uploader).filter(Boolean))
        )
        return authors
    }, [items])

    const filteredItems = useMemo(() => {
        return items.filter((item) => {
            const matchesAuthor =
                authorFilter === 'all' || item.uploader === authorFilter

            const assigneeUsername = item.assignee_username ?? null
            const isMine =
                assigneeUsername === null ? false : assigneeUsername === user?.username

            const matchesAssignee =
                assigneeFilter === 'all' ||
                (assigneeFilter === 'unassigned' && !assigneeUsername) ||
                (assigneeFilter === 'mine' && isMine) ||
                (assigneeFilter === 'others' && assigneeUsername && !isMine)

            return matchesAuthor && matchesAssignee
        })
    }, [items, authorFilter, assigneeFilter, user?.username])

    const totalPages = Math.ceil(total / LIMIT)
    const currentPage = page
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

    const movePage = (nextPage) => {
        setPage(nextPage)
    }

    const handleSearch = () => {
        const nextQuery = keyword.trim()
        setPage(1)
        setQuery(nextQuery)
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

            setPage(nextPage)
            await loadPendingDocuments(nextPage, query)
        } catch (e) {
            toast.error(e.message || '승인에 실패했습니다.')
        } finally {
            setActionLoadingId(null)
        }
    }

    const handleReject = async () => {
        if (!rejectTarget) return

        const trimmedReason = rejectReason.trim()
        if (!trimmedReason) {
            toast.error('반려 사유를 입력해주세요.')
            return
        }

        setActionLoadingId(rejectTarget.id)
        try {
            await rejectDocument(group.id, rejectTarget.id, trimmedReason)
            toast.success('문서를 반려했습니다.')
            setRejectTarget(null)
            setRejectReason('')

            const nextTotal = total - 1
            const nextTotalPages = Math.max(1, Math.ceil(nextTotal / LIMIT))
            const nextPage = Math.min(page, nextTotalPages)

            setPage(nextPage)
            await loadPendingDocuments(nextPage, query)
        } catch (e) {
            toast.error(e.message || '반려에 실패했습니다.')
        } finally {
            setActionLoadingId(null)
        }
    }

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="space-y-1">
                <h2 className="text-base font-semibold">승인 관리</h2>
                <p className="text-sm text-muted-foreground">
                    처리 가능한 승인 요청을 확인하고 승인 또는 반려할 수 있습니다.
                </p>
            </div>

            <div className="flex gap-2 border-b">
                {APPROVAL_SUB_TABS.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveSubTab(tab.key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            activeSubTab === tab.key
                                ? 'border-blue-600 text-blue-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {activeSubTab === 'pending' && (
                <>
                    <div className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center">
                        <div className="flex gap-2 md:flex-1">
                            <Input
                                placeholder="문서명 검색"
                                value={keyword}
                                onChange={(e) => setKeyword(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                className="md:flex-1"
                            />
                            <Button variant="outline" onClick={handleSearch}>
                                <Search className="h-4 w-4" />
                            </Button>
                        </div>

                        <Select value={authorFilter} onValueChange={setAuthorFilter}>
                            <SelectTrigger className="w-full md:w-44">
                                <SelectValue placeholder="작성자 전체" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">작성자 전체</SelectItem>
                                {authorOptions.map((author) => (
                                    <SelectItem key={author} value={author}>
                                        {author}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Select value={assigneeFilter} onValueChange={setAssigneeFilter}>
                            <SelectTrigger className="w-full md:w-48">
                                <SelectValue placeholder="담당자 전체" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">담당자 전체</SelectItem>
                                <SelectItem value="mine">내게 지정됨</SelectItem>
                                <SelectItem value="unassigned">미지정</SelectItem>
                                <SelectItem value="others">다른 담당자 지정</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {loading ? (
                        <div className="flex justify-center py-16">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : error ? (
                        <div className="py-16 text-center text-sm text-destructive">{error}</div>
                    ) : filteredItems.length === 0 ? (
                        <div className="rounded-lg border py-16 text-center text-sm text-muted-foreground">
                            처리할 승인 대기 문서가 없습니다.
                        </div>
                    ) : (
                        <>
                            <div className="rounded-lg border divide-y">
                                <div className="px-5 py-4">
                                    <h3 className="font-semibold">처리 대기</h3>
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        내가 처리 가능한 전체 승인 대기 문서입니다. 담당자가 지정되어 있어도 OWNER/ADMIN은 대신 처리할 수 있습니다.
                                    </p>
                                </div>

                                {filteredItems.map((item) => {
                                    const processingMeta = getProcessingStatusMeta(item.status)
                                    const isBusy = actionLoadingId === item.id

                                    return (
                                        <div
                                            key={item.id}
                                            className="flex items-start justify-between gap-4 px-5 py-4"
                                        >
                                            <div
                                                className="min-w-0 flex-1 cursor-pointer"
                                                onClick={() =>
                                                    navigate(
                                                        `/workspace/${group.id}/documents/${item.id}?tab=approvals`
                                                    )
                                                }
                                            >
                                                <p className="text-sm font-medium truncate">{item.title}</p>

                                                {item.preview && (
                                                    <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                                                        {item.preview}
                                                    </p>
                                                )}

                                                <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                                    <span>작성자 {item.uploader || '-'}</span>
                                                    <span>업로드 {formatDate(item.created_at)}</span>
                                                    <span>담당자 {item.assignee_username || '미지정'}</span>
                                                    <span className={processingMeta.className}>
                                                        요약 {processingMeta.label}
                                                    </span>
                                                </div>
                                            </div>

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
                                        </div>
                                    )
                                })}
                            </div>

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
                </>
            )}

            {activeSubTab === 'approved' && (
                <div className="rounded-lg border py-16 text-center text-sm text-muted-foreground">
                    테스트
                </div>
            )}

            {activeSubTab === 'rejected' && (
                <div className="rounded-lg border py-16 text-center text-sm text-muted-foreground">
                    테스트
                </div>
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
                        <Button onClick={handleReject} disabled={actionLoadingId === rejectTarget?.id}>
                            {actionLoadingId === rejectTarget?.id ? '처리 중...' : '반려'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
