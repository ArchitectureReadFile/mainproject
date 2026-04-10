import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Inbox, Loader2, Search, RotateCcw } from 'lucide-react'

import { formatKoreanDate } from '@/lib/datetime'
import { getGroupDocuments } from '@/api/groups'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'

const STATUS_LABEL = {
    DONE: { text: '완료', color: 'text-green-600' },
    PROCESSING: { text: '처리 중', color: 'text-yellow-500' },
    PENDING: { text: '대기', color: 'text-muted-foreground' },
    FAILED: { text: '실패', color: 'text-destructive' },
}

const APPROVAL_STATUS_LABEL = {
    PENDING_REVIEW: {
        text: '승인 대기',
        className: 'bg-amber-50 text-amber-700 border border-amber-200',
    },
    REJECTED: {
        text: '반려',
        className: 'bg-red-50 text-red-700 border border-red-200',
    },
}

const STATUS_FILTER_OPTIONS = [
    { value: 'all', label: '전체 상태' },
    { value: 'DONE', label: '완료' },
    { value: 'PROCESSING', label: '처리 중' },
    { value: 'PENDING', label: '대기' },
    { value: 'FAILED', label: '실패' },
]

const CATEGORY_FILTER_OPTIONS = [
    { value: '전체', label: '전체 카테고리' },
    { value: '민사', label: '민사' },
    { value: '계약', label: '계약' },
    { value: '회사', label: '회사' },
    { value: '행정', label: '행정' },
    { value: '형사', label: '형사' },
    { value: '노동', label: '노동' },
    { value: '기타', label: '기타' },
    { value: '미분류', label: '미분류' },
]

const LIMIT = 5
const POLLING_INTERVAL = 5000

export default function DocumentsTab({ group }) {
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()

    const page = Number(searchParams.get('page') || '1')
    const viewType = searchParams.get('view_type') || 'all'
    const query = searchParams.get('keyword') || ''
    const statusFilter = searchParams.get('status') || 'all'
    const categoryFilter = searchParams.get('category') || '전체'

    const [keyword, setKeyword] = useState(query)
    const [items, setItems] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const skip = (page - 1) * LIMIT


        /**
         * URL 쿼리 변경 시 검색어 입력값을 동기화한다.
         */
        useEffect(() => {
            setKeyword(query)
        }, [query])
    
        const load = useCallback(async (
            nextPage = page,
            kw = query,
            vt = viewType,
            st = statusFilter,
            ct = categoryFilter,
            showLoading = true
        ) => {
            if (showLoading) {
                setLoading(true)
            }
        setError(null)

        try {
            const documentsRes = await getGroupDocuments(group.id, {
                skip: (nextPage - 1) * LIMIT,
                limit: LIMIT,
                keyword: kw,
                viewType: vt,
                status: st === 'all' ? '' : st,
                category: ct,
            })

            setItems(documentsRes.items)
            setTotal(documentsRes.total)
        } catch (e) {
            setError(e.message || '문서를 불러오지 못했습니다.')
        } finally {
            if (showLoading) {
                setLoading(false)
            }
        }
    }, [group.id, page, query, viewType, statusFilter, categoryFilter])


    useEffect(() => {
        load()
    }, [load])


    useEffect(() => {
        const hasProcessingItems = items.some(
            (doc) => doc.status === 'PENDING' || doc.status === 'PROCESSING'
        )

        if (!hasProcessingItems) return

        const timerId = window.setInterval(() => {
            load(page, query, viewType, statusFilter, categoryFilter, false)
        }, POLLING_INTERVAL)

        return () => window.clearInterval(timerId)
    }, [items, load, page, query, viewType, statusFilter, categoryFilter])

    /**
     * 현재 필터 조건으로 문서 검색을 실행한다.
     */
    const handleSearch = () => {
        setSearchParams({
            tab: 'documents',
            page: '1',
            keyword,
            view_type: viewType,
            status: statusFilter,
            category: categoryFilter,
        })
    }

    /**
     * 문서 보기 범위를 변경한다.
     */
    const handleViewTypeChange = (nextViewType) => {
        setSearchParams({
            tab: 'documents',
            page: '1',
            keyword: query,
            view_type: nextViewType,
            status: statusFilter,
            category: categoryFilter,
        })
    }

    /**
     * 처리 상태 필터를 변경한다.
     */
    const handleStatusFilterChange = (nextStatus) => {
        setSearchParams({
            tab: 'documents',
            page: '1',
            keyword: query,
            view_type: viewType,
            status: nextStatus,
            category: categoryFilter,
        })
    }

    /**
     * 문서 카테고리 필터를 변경한다.
     */
    const handleCategoryFilterChange = (nextCategory) => {
        setSearchParams({
            tab: 'documents',
            page: '1',
            keyword: query,
            view_type: viewType,
            status: statusFilter,
            category: nextCategory,
        })
    }

    /**
     * 문서 목록 필터를 기본값으로 초기화한다.
     */
    const handleResetFilters = () => {
        setKeyword('')
        setSearchParams({
            tab: 'documents',
            page: '1',
            keyword: '',
            view_type: 'all',
            status: 'all',
            category: '전체',
        })
    }

    /**
     * 문서 목록 페이지를 이동한다.
     */
    const movePage = (nextPage) => {
        setSearchParams({
            tab: 'documents',
            page: String(nextPage),
            keyword: query,
            view_type: viewType,
            status: statusFilter,
            category: categoryFilter,
        })
    }

    const startItem = total === 0 ? 0 : skip + 1
    const endItem = Math.min(skip + items.length, total)

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


    return (
        <div className="space-y-4 max-w-3xl mx-auto">
            <div className="space-y-3">
                <div className="flex min-w-0 gap-2">
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

                <div className="flex flex-wrap items-center gap-2">
                    <div className="flex rounded-md border overflow-hidden text-sm">
                        <Button
                            type="button"
                            variant={viewType === 'all' ? 'default' : 'ghost'}
                            onClick={() => handleViewTypeChange('all')}
                            className={`h-auto rounded-none px-3 py-1.5 ${
                                viewType === 'all'
                                    ? ''
                                    : 'text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            승인된 문서
                        </Button>
                        <Button
                            type="button"
                            variant={viewType === 'my' ? 'default' : 'ghost'}
                            onClick={() => handleViewTypeChange('my')}
                            className={`h-auto rounded-none border-l px-3 py-1.5 ${
                                viewType === 'my'
                                    ? ''
                                    : 'text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            내 문서
                        </Button>
                    </div>

                    <div className="flex rounded-md border overflow-hidden text-sm w-fit">
                        {STATUS_FILTER_OPTIONS.map((option) => (
                            <Button
                                key={option.value}
                                type="button"
                                variant={statusFilter === option.value ? 'default' : 'ghost'}
                                onClick={() => handleStatusFilterChange(option.value)}
                                className={`h-auto rounded-none border-l px-3 py-1.5 first:border-l-0 ${
                                    statusFilter === option.value
                                        ? ''
                                        : 'text-muted-foreground hover:bg-muted'
                                }`}
                            >
                                {option.label}
                            </Button>
                        ))}
                    </div>

                    <Select value={categoryFilter} onValueChange={handleCategoryFilterChange}>
                        <SelectTrigger className="w-full sm:w-50.5">
                            <SelectValue placeholder="전체 카테고리" />
                        </SelectTrigger>
                        <SelectContent>
                            {CATEGORY_FILTER_OPTIONS.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Button
                        variant="outline"
                        onClick={handleResetFilters}
                        className="gap-2"
                    >
                        <RotateCcw className="h-4 w-4" />
                        초기화
                    </Button>
                </div>
            </div>

            {group.my_role === 'EDITOR' && (
                <div className="text-sm text-muted-foreground">
                    {viewType === 'all'
                        ? '전체 문서에는 승인 완료된 문서만 표시됩니다.'
                        : '내 문서에서는 내가 업로드한 문서를 모두 확인할 수 있습니다. 승인 대기 및 반려 문서도 포함됩니다.'}
                </div>
            )}

            {!loading && !error && total > 0 && (
                <div className="flex justify-end text-sm text-muted-foreground mb-2">
                    <span>문서 {total}개 중 {startItem}-{endItem}</span>
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
                    <Inbox className="h-10 w-10" />
                    <p className="text-sm">문서가 없습니다.</p>
                </div>
            ) : (
                <div className="rounded-lg border divide-y">
                    {items.map((doc) => {
                        const status =
                            STATUS_LABEL[doc.status] ?? {
                                text: doc.status,
                                color: 'text-muted-foreground',
                            }

                        return (
                            <div
                                key={doc.id}
                                onClick={() => navigate(
                                    `/workspace/${group.id}/documents/${doc.id}?tab=documents&page=${page}&keyword=${encodeURIComponent(query)}&view_type=${viewType}&status=${statusFilter}&category=${encodeURIComponent(categoryFilter)}`
                                )}
                                className="flex items-start justify-between px-5 py-4 cursor-pointer hover:bg-muted/50 transition-colors"
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
                                            카테고리 {doc.category || '미분류'}
                                        </span>                                           
                                        <span className="rounded-sm bg-muted px-2 py-0.5 text-foreground">
                                            유형 {doc.document_type || '미분류'}
                                        </span>

                                        {APPROVAL_STATUS_LABEL[doc.approval_status] && (
                                            <span
                                                className={`rounded-sm px-2 py-0.5 ${
                                                    APPROVAL_STATUS_LABEL[doc.approval_status].className
                                                }`}
                                            >
                                                {APPROVAL_STATUS_LABEL[doc.approval_status].text}
                                            </span>
                                        )}

                                        <span>업로더 {doc.uploader}</span>
                                        <span>댓글 {doc.comment_count ?? 0}개</span>
                                        <span>업로드 {formatKoreanDate(doc.created_at)}</span>
                                    </div>
                                </div>
                                <span className={`text-xs font-medium shrink-0 ${status.color}`}>
                                    {status.text}
                                </span>
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
