import {
    createDocumentComment,
    deleteDocumentComment,
    deleteGroupDocument,
    getDocumentComments,
    getGroupDocumentDetail,
    getGroupDocumentOriginalUrl,
    getMembers,
} from '@/api/groups'
import { downloadSummaryPdf } from '@/api/documents'
import { Avatar, AvatarFallback } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/Sheet'
import { Textarea } from '@/components/ui/Textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/features/auth/context/AuthContext'
import { cn } from '@/lib/utils'
import {
    ArrowLeft,
    ChevronDown,
    ChevronUp,
    Download,
    ExternalLink,
    Loader2,
    MapPin,
    MessageSquareText,
    PanelRightClose,
    PanelRightOpen,
    Reply,
    SendHorizontal,
    Trash2,
    X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Document as PdfDocument, Page, pdfjs } from 'react-pdf'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url
).toString()

/**
 * 댓글 시간 표시 문자열을 만든다.
 */
function formatCommentDate(value) {
    if (!value) return '-'

    return new Date(value).toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    })
}

/**
 * 멘션 경계 문자 여부를 판별한다.
 */
function isMentionBoundary(char) {
    return !char || /[\s.,!?;:()[\]{}"'`~<>/\\|-]/.test(char)
}

/**
 * 현재 커서 위치 기준으로 활성 멘션 입력 상태를 계산한다.
 */
function findActiveMention(value, selectionStart) {
    if (selectionStart == null) return null

    const beforeCursor = value.slice(0, selectionStart)
    const atIndex = beforeCursor.lastIndexOf('@')

    if (atIndex === -1) return null

    const previousChar = atIndex === 0 ? '' : beforeCursor[atIndex - 1]
    if (previousChar && !isMentionBoundary(previousChar)) {
        return null
    }

    const query = beforeCursor.slice(atIndex + 1)
    if (/[\s.,!?;:()[\]{}"'`~<>/\\|-]/.test(query)) {
        return null
    }

    return {
        start: atIndex,
        query,
    }
}

/**
 * 최종 본문 문자열에서 백엔드 저장용 멘션 span 목록을 만든다.
 */
function buildMentionPayloads(content, members) {
    const sortedMembers = [...members].sort((a, b) => b.username.length - a.username.length)
    const mentions = []
    let cursor = 0

    while (cursor < content.length) {
        if (content[cursor] !== '@') {
            cursor += 1
            continue
        }

        const previousChar = cursor === 0 ? '' : content[cursor - 1]
        if (previousChar && !isMentionBoundary(previousChar)) {
            cursor += 1
            continue
        }

        const matchedMember = sortedMembers.find((member) => {
            const mentionText = `@${member.username}`
            const nextIndex = cursor + mentionText.length

            return content.startsWith(mentionText, cursor) && isMentionBoundary(content[nextIndex])
        })

        if (!matchedMember) {
            cursor += 1
            continue
        }

        mentions.push({
            user_id: matchedMember.user_id,
            snapshot_username: matchedMember.username,
            start: cursor,
            end: cursor + matchedMember.username.length + 1,
        })

        cursor += matchedMember.username.length + 1
    }

    return mentions
}

/**
 * 댓글 응답에서 위치 좌표를 정규화한다.
 * 백엔드 필드명이 다르면 이 함수만 맞춰서 수정하면 된다.
 */
function getCommentAnchor(comment) {
    const rawPage = comment.page ?? comment.page_number ?? comment.target_page ?? comment.position?.page
    const rawX = comment.x ?? comment.position_x ?? comment.position?.x
    const rawY = comment.y ?? comment.position_y ?? comment.position?.y

    const page = Number(rawPage)
    const x = Number(rawX)
    const y = Number(rawY)

    if (!Number.isFinite(page) || !Number.isFinite(x) || !Number.isFinite(y)) {
        return null
    }

    return {
        page,
        x: Math.min(1, Math.max(0, x)),
        y: Math.min(1, Math.max(0, y)),
    }
}

/**
 * 댓글 트리 전체 개수를 계산한다.
 */
function countAllComments(comments) {
    return comments.reduce((count, comment) => {
        return count + 1 + countAllComments(comment.replies ?? [])
    }, 0)
}

/**
 * 멘션 span을 반영해서 댓글 본문을 렌더링한다.
 */
function renderCommentContent(content, mentions) {
    if (!mentions?.length) {
        return content
    }

    const sortedMentions = [...mentions].sort((a, b) => a.start - b.start)
    const parts = []
    let cursor = 0

    sortedMentions.forEach((mention, index) => {
        if (cursor < mention.start) {
            parts.push(
                <span key={`text-${index}-${cursor}`}>
                    {content.slice(cursor, mention.start)}
                </span>
            )
        }

        parts.push(
            <span key={`mention-${index}`} className="font-semibold text-primary">
                {content.slice(mention.start, mention.end)}
            </span>
        )

        cursor = mention.end
    })

    if (cursor < content.length) {
        parts.push(<span key={`text-last-${cursor}`}>{content.slice(cursor)}</span>)
    }

    return parts
}

export default function DocumentPage() {
    const { user } = useAuth()
    const { group_id, doc_id } = useParams()
    const navigate = useNavigate()
    const location = useLocation()

    const [doc, setDoc] = useState(null)
    const [comments, setComments] = useState([])
    const [members, setMembers] = useState([])
    const [loading, setLoading] = useState(true)
    const [commentsLoading, setCommentsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [pdfError, setPdfError] = useState(null)

    const [showDeleteModal, setShowDeleteModal] = useState(false)
    const [isCommentPanelOpen, setIsCommentPanelOpen] = useState(false)
    const [isMobileCommentLayout, setIsMobileCommentLayout] = useState(false)

    const [draftContent, setDraftContent] = useState('')
    const [draftAnchor, setDraftAnchor] = useState(null)
    const [replyParentId, setReplyParentId] = useState(null)
    const [focusedCommentId, setFocusedCommentId] = useState(null)
    const [isSubmittingComment, setIsSubmittingComment] = useState(false)
    const [deletingCommentId, setDeletingCommentId] = useState(null)
    const [isComposerOpen, setIsComposerOpen] = useState(false)

    const [mentionState, setMentionState] = useState({
        open: false,
        query: '',
        start: -1,
    })

    const [numPages, setNumPages] = useState(0)
    const [pageWidth, setPageWidth] = useState(820)

    const viewerRef = useRef(null)
    const textareaRef = useRef(null)
    const pageRefs = useRef({})
    const commentRefs = useRef({})

    const pdfOptions = useMemo(() => {
        return { withCredentials: true }
    }, [])

    const backToListUrl = `/workspace/${group_id}${location.search || '?tab=documents'}`
    const originalPdfUrl = getGroupDocumentOriginalUrl(group_id, doc_id)

    const STATUS_MESSAGE = {
        PENDING: 'AI 요약 대기 중입니다. 잠시 후 다시 확인해주세요.',
        PROCESSING: 'AI가 문서를 분석하고 있습니다. 잠시 후 요약이 표시됩니다.',
        FAILED: '요약 생성에 실패했습니다. 다시 업로드하거나 관리자에게 문의해주세요.',
    }

    /**
     * 댓글 목록만 다시 불러온다.
     */
    const loadComments = useCallback(async () => {
        setCommentsLoading(true)

        try {
            const commentData = await getDocumentComments(group_id, doc_id)
            setComments(commentData.items ?? [])
        } catch (e) {
            toast.error(e.message || '댓글을 불러오지 못했습니다.')
        } finally {
            setCommentsLoading(false)
        }
    }, [group_id, doc_id])

    /**
     * 문서 상세, 댓글, 멤버 목록을 한 번에 로드한다.
     */
    const loadPageData = useCallback(async () => {
        setLoading(true)
        setCommentsLoading(true)

        try {
            const [docData, commentData, memberData] = await Promise.all([
                getGroupDocumentDetail(group_id, doc_id),
                getDocumentComments(group_id, doc_id),
                getMembers(group_id),
            ])

            setDoc(docData)
            setComments(commentData.items ?? [])
            setMembers(memberData.members ?? [])
            setError(null)
        } catch (e) {
            setError(e.message || '문서를 불러오지 못했습니다.')
        } finally {
            setLoading(false)
            setCommentsLoading(false)
        }
    }, [group_id, doc_id])

    /**
     * 멘션 팝오버 상태를 현재 커서 기준으로 동기화한다.
     */
    const syncMentionState = useCallback((value, selectionStart) => {
        const activeMention = findActiveMention(value, selectionStart)

        if (!activeMention) {
            setMentionState({
                open: false,
                query: '',
                start: -1,
            })
            return
        }

        setMentionState({
            open: true,
            query: activeMention.query,
            start: activeMention.start,
        })
    }, [])

    /**
     * 특정 댓글 스레드를 패널과 PDF 양쪽에서 동시에 포커싱한다.
     */
    const focusCommentThread = useCallback((comment) => {
        const anchor = getCommentAnchor(comment)

        setIsCommentPanelOpen(true)
        setFocusedCommentId(comment.id)

        if (anchor) {
            pageRefs.current[anchor.page]?.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
            })
        }

        window.setTimeout(() => {
            commentRefs.current[comment.id]?.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
            })
        }, 120)
    }, [])

    /**
     * 멘션 후보를 본문에 삽입한다.
     */
    const insertMention = useCallback((member) => {
        const textarea = textareaRef.current
        if (!textarea || mentionState.start < 0) return

        const selectionStart = textarea.selectionStart ?? draftContent.length
        const nextValue = [
            draftContent.slice(0, mentionState.start),
            `@${member.username} `,
            draftContent.slice(selectionStart),
        ].join('')

        setDraftContent(nextValue)
        setMentionState({
            open: false,
            query: '',
            start: -1,
        })

        window.requestAnimationFrame(() => {
            const nextCaret = mentionState.start + member.username.length + 2
            textarea.focus()
            textarea.setSelectionRange(nextCaret, nextCaret)
        })
    }, [draftContent, mentionState.start])

    useEffect(() => {
        loadPageData()
    }, [loadPageData])

    useEffect(() => {
        const mediaQuery = window.matchMedia('(max-width: 1023px)')

        const syncCommentLayout = (matches) => {
            setIsMobileCommentLayout(matches)
        }

        const handleChange = (event) => {
            syncCommentLayout(event.matches)
        }

        syncCommentLayout(mediaQuery.matches)
        mediaQuery.addEventListener('change', handleChange)

        return () => {
            mediaQuery.removeEventListener('change', handleChange)
        }
    }, [])

    useEffect(() => {
        if (!viewerRef.current) return

        const observer = new window.ResizeObserver(([entry]) => {
            const nextWidth = Math.max(280, Math.min(920, entry.contentRect.width - 40))
            setPageWidth(Math.floor(nextWidth))
        })

        observer.observe(viewerRef.current)

        return () => {
            observer.disconnect()
        }
    }, [])


    /**
     * 답글 작성 또는 PDF 위치 선택 시 작성 영역을 자동으로 연다.
     */
    useEffect(() => {
        if (replyParentId || draftAnchor || draftContent.trim() || mentionState.open) {
            setIsComposerOpen(true)
        }
    }, [replyParentId, draftAnchor, draftContent, mentionState.open])


    const s = doc
    const statusMessage = STATUS_MESSAGE[s?.status] ?? null
    const hasSummary = Boolean(s?.summary_text)

    const isDeletedDocument = Boolean(doc?.delete_scheduled_at)
    const canDelete = Boolean(doc?.can_delete) && !isDeletedDocument

    const isPendingReview = doc?.approval_status === 'PENDING_REVIEW'
    const isRejected = doc?.approval_status === 'REJECTED'

    const mentionableMembers = useMemo(() => {
        return members.filter((member) => member.user_id !== user?.id)
    }, [members, user?.id])

    const mentionCandidates = useMemo(() => {
        if (!mentionState.open) return []

        const keyword = mentionState.query.trim().toLowerCase()

        return mentionableMembers
            .filter((member) => {
                if (!keyword) return true
                return member.username.toLowerCase().includes(keyword)
            })
            .slice(0, 6)
    }, [mentionState.open, mentionState.query, mentionableMembers])

    const anchoredThreads = useMemo(() => {
        return comments.filter((comment) => Boolean(getCommentAnchor(comment)))
    }, [comments])

    const markerNumberMap = useMemo(() => {
        return new Map(anchoredThreads.map((comment, index) => [comment.id, index + 1]))
    }, [anchoredThreads])

    const totalCommentCount = useMemo(() => {
        return countAllComments(comments)
    }, [comments])

    const replyTarget = useMemo(() => {
        return comments.find((comment) => comment.id === replyParentId) ?? null
    }, [comments, replyParentId])

    const calcDday = (isoDate) => {
        if (!isoDate) return null
        const diff = Math.ceil((new Date(isoDate) - new Date()) / (1000 * 60 * 60 * 24))
        return diff <= 0 ? 'D-0' : `D-${diff}`
    }

    const deletedDday = calcDday(doc?.delete_scheduled_at)

    if (loading) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-12 text-center text-muted-foreground">
                불러오는 중...
            </div>
        )
    }

    if (error || !doc) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-12 text-center text-destructive">
                {error || '문서를 찾을 수 없습니다.'}
            </div>
        )
    }

    const handleDownload = async () => {
        if (!s.summary_id) return
        try {
            await downloadSummaryPdf(s.summary_id, s.case_number, s.case_name)
        } catch {
            toast.error('다운로드에 실패했습니다.')
        }
    }

    const handleDeleteConfirm = async () => {
        try {
            await deleteGroupDocument(group_id, doc_id)
            navigate(backToListUrl, { state: { deleted: true } })
        } catch (e) {
            toast.error(e.message || '삭제에 실패했습니다.')
            setShowDeleteModal(false)
        }
    }

    const handleDraftChange = (event) => {
        const nextValue = event.target.value
        setDraftContent(nextValue)
        syncMentionState(nextValue, event.target.selectionStart)
    }

    const handleDraftSelection = (event) => {
        syncMentionState(event.target.value, event.target.selectionStart)
    }

    const handleDraftKeyDown = (event) => {
        if (mentionState.open && mentionCandidates.length > 0 && event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            insertMention(mentionCandidates[0])
            return
        }

        if (event.key === 'Escape') {
            setMentionState({
                open: false,
                query: '',
                start: -1,
            })
        }
    }

    const handlePdfPageClick = (pageNumber, event) => {
        const rect = event.currentTarget.getBoundingClientRect()
        const x = Number(((event.clientX - rect.left) / rect.width).toFixed(4))
        const y = Number(((event.clientY - rect.top) / rect.height).toFixed(4))

        setDraftAnchor({ page: pageNumber, x, y })
        setReplyParentId(null)
        setIsCommentPanelOpen(true)

        window.requestAnimationFrame(() => {
            textareaRef.current?.focus()
        })
    }

    const handleStartReply = (comment) => {
        setReplyParentId(comment.id)
        setDraftAnchor(getCommentAnchor(comment))
        setIsCommentPanelOpen(true)

        window.requestAnimationFrame(() => {
            textareaRef.current?.focus()
        })
    }

    const handleCancelDraftMeta = () => {
        setReplyParentId(null)
        setDraftAnchor(null)
    }

    const handleSubmitComment = async () => {
        const content = draftContent.trim()
        if (!content) {
            toast.error('댓글 내용을 입력해주세요.')
            return
        }

        if (!replyParentId && !draftAnchor) {
            toast.error('PDF 페이지를 클릭해서 댓글 위치를 먼저 선택해주세요.')
            return
        }

        setIsSubmittingComment(true)

        try {
            const payload = {
                content,
                parent_id: replyParentId,
                mentions: buildMentionPayloads(content, mentionableMembers),
            }

            if (!replyParentId && draftAnchor) {
                payload.page = draftAnchor.page
                payload.x = draftAnchor.x
                payload.y = draftAnchor.y
            }

            const createdComment = await createDocumentComment(group_id, doc_id, payload)

            setDraftContent('')
            setDraftAnchor(null)
            setReplyParentId(null)
            setMentionState({
                open: false,
                query: '',
                start: -1,
            })

            await loadComments()
            setIsCommentPanelOpen(true)
            setFocusedCommentId(createdComment.parent_id ?? createdComment.id)

            window.setTimeout(() => {
                commentRefs.current[createdComment.parent_id ?? createdComment.id]?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest',
                })
            }, 120)

            toast.success('댓글이 등록되었습니다.')
        } catch (e) {
            toast.error(e.message || '댓글 등록에 실패했습니다.')
        } finally {
            setIsSubmittingComment(false)
        }
    }

    const handleDeleteComment = async (commentId) => {
        const confirmed = window.confirm('댓글을 삭제하시겠습니까?')
        if (!confirmed) return

        setDeletingCommentId(commentId)

        try {
            await deleteDocumentComment(group_id, commentId)
            await loadComments()
            toast.success('댓글을 삭제했습니다.')
        } catch (e) {
            toast.error(e.message || '댓글 삭제에 실패했습니다.')
        } finally {
            setDeletingCommentId(null)
        }
    }

    const renderThread = (comment) => {
        const anchor = getCommentAnchor(comment)
        const isFocused = focusedCommentId === comment.id

        return (
            <div
                key={comment.id}
                ref={(node) => {
                    if (node) {
                        commentRefs.current[comment.id] = node
                    }
                }}
                className={cn(
                    'rounded-xl border bg-background p-4 transition-colors',
                    isFocused && 'border-primary bg-primary/5'
                )}
            >
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                        <Avatar className="size-9">
                            <AvatarFallback className="text-xs font-semibold">
                                {comment.author?.username?.slice(0, 2)?.toUpperCase() || '??'}
                            </AvatarFallback>
                        </Avatar>

                        <div>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-semibold text-foreground">
                                    {comment.author?.username || '알 수 없음'}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                    {formatCommentDate(comment.created_at)}
                                </span>
                                {comment.is_deleted && (
                                    <Badge variant="outline">삭제됨</Badge>
                                )}
                            </div>

                            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
                                {renderCommentContent(comment.content, comment.mentions)}
                            </p>
                        </div>
                    </div>

                    {anchor && (
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 gap-1.5 px-2 text-xs"
                            onClick={() => focusCommentThread(comment)}
                        >
                            <MapPin size={13} />
                            페이지 {anchor.page}
                        </Button>
                    )}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                    {!comment.is_deleted && (
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 gap-1.5 px-2 text-xs"
                            onClick={() => handleStartReply(comment)}
                        >
                            <Reply size={13} />
                            답글
                        </Button>
                    )}

                    {comment.can_delete && (
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 gap-1.5 px-2 text-xs text-destructive"
                            disabled={deletingCommentId === comment.id}
                            onClick={() => handleDeleteComment(comment.id)}
                        >
                            <Trash2 size={13} />
                            삭제
                        </Button>
                    )}
                </div>

                {comment.replies?.length > 0 && (
                    <div className="mt-4 space-y-3 border-l pl-4">
                        {comment.replies.map((reply) => (
                            <div key={reply.id} className="rounded-lg bg-muted/30 p-3">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-foreground">
                                            {reply.author?.username || '알 수 없음'}
                                        </span>
                                        <span className="text-xs text-muted-foreground">
                                            {formatCommentDate(reply.created_at)}
                                        </span>
                                        {reply.is_deleted && (
                                            <Badge variant="outline">삭제됨</Badge>
                                        )}
                                    </div>

                                    {reply.can_delete && (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 px-2 text-xs text-destructive"
                                            disabled={deletingCommentId === reply.id}
                                            onClick={() => handleDeleteComment(reply.id)}
                                        >
                                            삭제
                                        </Button>
                                    )}
                                </div>

                                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
                                    {renderCommentContent(reply.content, reply.mentions)}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        )
    }

    const commentPanelBody = (
        <div className="flex min-h-0 flex-1 flex-col">
            <div className="border-b px-5 py-4">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <div className="flex items-center gap-2">
                            <div className="rounded-full bg-primary/10 p-2 text-primary">
                                <MessageSquareText size={16} />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-foreground">문서 댓글</p>
                                <p className="text-xs text-muted-foreground">
                                    댓글 목록을 보면서 필요할 때만 작성창을 열 수 있습니다.
                                </p>
                            </div>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-2">
                            <Badge variant="secondary">전체 {totalCommentCount}</Badge>
                            <Badge variant="outline">위치 댓글 {anchoredThreads.length}</Badge>
                            {draftAnchor && (
                                <Badge variant="outline">페이지 {draftAnchor.page}</Badge>
                            )}
                            {replyTarget && (
                                <Badge variant="outline">
                                    답글 대상 @{replyTarget.author?.username || '알 수 없음'}
                                </Badge>
                            )}
                        </div>
                    </div>

                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => setIsComposerOpen((prev) => !prev)}
                    >
                        {isComposerOpen ? (
                            <>
                                <ChevronUp size={16} />
                                접기
                            </>
                        ) : (
                            <>
                                <ChevronDown size={16} />
                                댓글 작성
                            </>
                        )}
                    </Button>
                </div>

                {isComposerOpen && (
                    <div className="mt-4 space-y-3">
                        <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">
                            {replyTarget
                                ? `현재 페이지 ${draftAnchor?.page ?? '-'} 위치 스레드에 답글을 작성합니다.`
                                : draftAnchor
                                ? `페이지 ${draftAnchor.page} · x ${Math.round(draftAnchor.x * 100)}% · y ${Math.round(draftAnchor.y * 100)}% 위치에 댓글을 작성합니다.`
                                : 'PDF 페이지를 클릭하면 해당 좌표에 루트 댓글이 생성됩니다.'}
                        </div>

                        <div className="relative">
                            <Textarea
                                ref={textareaRef}
                                value={draftContent}
                                onChange={handleDraftChange}
                                onClick={handleDraftSelection}
                                onKeyUp={handleDraftSelection}
                                onSelect={handleDraftSelection}
                                onKeyDown={handleDraftKeyDown}
                                placeholder="@사용자명 으로 멘션하거나 댓글을 입력하세요."
                                className="min-h-[88px] resize-none"
                            />

                            {mentionState.open && mentionCandidates.length > 0 && (
                                <div className="absolute inset-x-0 top-full z-20 mt-2 rounded-lg border bg-background p-2 shadow-lg">
                                    <div className="mb-1 px-2 text-xs font-medium text-muted-foreground">
                                        멘션 대상
                                    </div>

                                    <div className="space-y-1">
                                        {mentionCandidates.map((member) => (
                                            <button
                                                key={member.user_id}
                                                type="button"
                                                className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-muted"
                                                onMouseDown={(event) => {
                                                    event.preventDefault()
                                                    insertMention(member)
                                                }}
                                            >
                                                <span className="font-medium text-foreground">
                                                    @{member.username}
                                                </span>
                                                <span className="text-xs text-muted-foreground">
                                                    {member.role}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="flex flex-wrap items-center justify-end gap-2">
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={handleCancelDraftMeta}
                            >
                                선택 해제
                            </Button>

                            <Button
                                type="button"
                                size="sm"
                                className="gap-1.5"
                                disabled={isSubmittingComment}
                                onClick={handleSubmitComment}
                            >
                                {isSubmittingComment ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizontal size={14} />}
                                등록
                            </Button>
                        </div>
                    </div>
                )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {commentsLoading ? (
                    <div className="flex items-center justify-center py-16 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                ) : comments.length > 0 ? (
                    <div className="space-y-3">
                        {comments.map(renderThread)}
                    </div>
                ) : (
                    <div className="rounded-lg border border-dashed bg-background p-6 text-center text-sm text-muted-foreground">
                        아직 댓글이 없습니다. PDF를 클릭해서 첫 댓글을 남겨보세요.
                    </div>
                )}
            </div>
        </div>
    )

    return (
        <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-4 py-8 lg:px-6 xl:px-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button variant="ghost" size="sm" onClick={() => navigate(backToListUrl)}>
                    <ArrowLeft size={15} />
                    문서 목록으로
                </Button>

                <div className="flex gap-2">
                    {doc.summary_id && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="outline" size="sm" onClick={handleDownload} className="gap-1.5">
                                    <Download size={14} />
                                    PDF 다운로드
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>요약본 PDF를 다운로드합니다</TooltipContent>
                        </Tooltip>
                    )}

                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button asChild variant="outline" size="sm" className="gap-1.5">
                                <a href={originalPdfUrl} target="_blank" rel="noreferrer">
                                    <ExternalLink size={14} />
                                    새 탭으로 열기
                                </a>
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>원본 PDF를 새 탭에서 엽니다</TooltipContent>
                    </Tooltip>

                    {canDelete && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => setShowDeleteModal(true)}
                                    className="gap-1.5"
                                >
                                    <Trash2 size={14} />
                                    삭제
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>문서를 휴지통으로 이동합니다</TooltipContent>
                        </Tooltip>
                    )}
                </div>
            </div>

            <ConfirmModal
                open={showDeleteModal}
                message={'정말 삭제하시겠습니까?\n삭제된 문서는 휴지통에서 확인할 수 있습니다.'}
                confirmLabel="삭제"
                onConfirm={handleDeleteConfirm}
                onCancel={() => setShowDeleteModal(false)}
            />

            {isDeletedDocument && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <p className="font-medium">휴지통에 있는 문서입니다.</p>
                    <p className="mt-1 text-xs">
                        {doc.delete_scheduled_at
                            ? `${new Date(doc.delete_scheduled_at).toLocaleDateString('ko-KR')} 삭제 예정 (${deletedDday})`
                            : '삭제 예정 문서입니다.'}
                        {doc.deleted_by_username ? ` · 삭제자 ${doc.deleted_by_username}` : ''}
                    </p>
                </div>
            )}

            {!isDeletedDocument && isPendingReview && (
                <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                    <p className="font-medium">승인 대기 중인 문서입니다.</p>
                    <p className="mt-1 text-xs">
                        아직 검토가 완료되지 않았습니다.
                        {doc.assignee_username ? ` · 담당자 ${doc.assignee_username}` : ''}
                    </p>
                </div>
            )}

            {!isDeletedDocument && isRejected && (
                <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <p className="font-medium">반려된 문서입니다.</p>
                    <p className="mt-1 text-xs">
                        반려 사유: {doc.feedback || '반려 사유가 등록되지 않았습니다.'}
                    </p>
                </div>
            )}

            <div className="px-1">
                <h1 className="mb-3 text-2xl font-bold">{s.title || '문서 상세'}</h1>
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
                    <div className="flex gap-1.5">
                        <span className="font-medium text-foreground">문서 유형</span>
                        <span>{s.document_type || '-'}</span>
                    </div>
                    <div className="flex gap-1.5">
                        <span className="font-medium text-foreground">업로더</span>
                        <span>{s.uploader || '-'}</span>
                    </div>
                    <div className="flex gap-1.5">
                        <span className="font-medium text-foreground">업로드 일시</span>
                        <span>{formatCommentDate(s.created_at)}</span>
                    </div>
                </div>
            </div>

            <Card className="p-6">
                <h3 className="mb-2 text-sm font-semibold text-muted-foreground">AI 요약</h3>

                {hasSummary ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{s.summary_text}</p>
                ) : statusMessage ? (
                    <div className="rounded-md border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        {statusMessage}
                    </div>
                ) : (
                    <p className="text-sm leading-relaxed text-muted-foreground">요약 정보가 없습니다.</p>
                )}
            </Card>

            <Card className="p-6">
                <h3 className="mb-3 text-sm font-semibold text-muted-foreground">핵심 포인트</h3>
                {s.key_points?.length ? (
                    <ul className="list-disc space-y-2 pl-5 text-sm">
                        {s.key_points.map((point) => (
                            <li key={point}>{point}</li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm font-medium">-</p>
                )}
            </Card>

            <div
                className={cn(
                    'grid items-stretch gap-4',
                    isCommentPanelOpen ? 'lg:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]' : 'grid-cols-1'
                )}
            >
                <Card className="overflow-hidden lg:flex lg:h-[78vh] lg:flex-col">
                    <div className="flex items-center justify-between border-b px-6 py-4">
                        <div>
                            <h3 className="text-sm font-semibold text-muted-foreground">원문 PDF</h3>
                            <p className="mt-1 text-xs text-muted-foreground">
                                페이지를 클릭하면 해당 좌표에 댓글을 남길 수 있습니다.
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <Button
                                variant={isCommentPanelOpen ? 'secondary' : 'outline'}
                                size="sm"
                                onClick={() => setIsCommentPanelOpen((prev) => !prev)}
                                className="gap-1.5"
                            >
                                {isCommentPanelOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
                                댓글 패널
                            </Button>
                        </div>
                    </div>

                    <div ref={viewerRef} className="min-h-0 flex-1 overflow-auto bg-muted/20">
                        {pdfError ? (
                            <div className="flex h-full items-center justify-center p-8 text-sm text-destructive">
                                {pdfError}
                            </div>
                        ) : (
                            <div className="mx-auto flex max-w-[980px] flex-col gap-4 p-4">
                                <PdfDocument
                                    file={originalPdfUrl}
                                    options={pdfOptions}
                                    loading={
                                        <div className="flex items-center justify-center py-20 text-muted-foreground">
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                        </div>
                                    }
                                    onLoadSuccess={({ numPages: nextNumPages }) => {
                                        setNumPages(nextNumPages)
                                        setPdfError(null)
                                    }}
                                    onLoadError={(loadError) => {
                                        setPdfError(loadError?.message || 'PDF를 불러오지 못했습니다.')
                                    }}
                                >
                                    {Array.from({ length: numPages }, (_, index) => {
                                        const pageNumber = index + 1
                                        const pageMarkers = anchoredThreads.filter((comment) => {
                                            return getCommentAnchor(comment)?.page === pageNumber
                                        })

                                        return (
                                            <div
                                                key={pageNumber}
                                                ref={(node) => {
                                                    if (node) {
                                                        pageRefs.current[pageNumber] = node
                                                    }
                                                }}
                                                className="overflow-hidden rounded-xl border bg-white shadow-sm"
                                            >
                                                <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-muted-foreground">
                                                    <span>페이지 {pageNumber}</span>

                                                    {draftAnchor?.page === pageNumber && (
                                                        <Badge variant="secondary">선택한 위치</Badge>
                                                    )}
                                                </div>

                                                <div
                                                    className="relative cursor-crosshair"
                                                    onClick={(event) => handlePdfPageClick(pageNumber, event)}
                                                >
                                                    <Page
                                                        pageNumber={pageNumber}
                                                        width={pageWidth}
                                                        renderAnnotationLayer={false}
                                                        renderTextLayer={false}
                                                    />

                                                    {pageMarkers.map((comment) => {
                                                        const anchor = getCommentAnchor(comment)
                                                        if (!anchor) return null

                                                        return (
                                                            <button
                                                                key={comment.id}
                                                                type="button"
                                                                className={cn(
                                                                    'absolute flex size-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-primary text-xs font-semibold text-white shadow-lg transition',
                                                                    focusedCommentId === comment.id && 'bg-destructive'
                                                                )}
                                                                style={{
                                                                    left: `${anchor.x * 100}%`,
                                                                    top: `${anchor.y * 100}%`,
                                                                }}
                                                                onClick={(event) => {
                                                                    event.stopPropagation()
                                                                    focusCommentThread(comment)
                                                                }}
                                                                aria-label={`댓글 ${markerNumberMap.get(comment.id)} 위치`}
                                                            >
                                                                {markerNumberMap.get(comment.id)}
                                                            </button>
                                                        )
                                                    })}

                                                    {draftAnchor?.page === pageNumber && (
                                                        <div
                                                            className="pointer-events-none absolute flex size-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-amber-500 text-xs font-bold text-white shadow-lg"
                                                            style={{
                                                                left: `${draftAnchor.x * 100}%`,
                                                                top: `${draftAnchor.y * 100}%`,
                                                            }}
                                                        >
                                                            +
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </PdfDocument>
                            </div>
                        )}
                    </div>
                </Card>

                {isCommentPanelOpen && (
                    <Card className="hidden overflow-hidden lg:flex lg:h-[78vh] lg:flex-col">
                        <div className="flex items-center justify-between border-b px-5 py-4">
                            <div>
                                <h3 className="text-sm font-semibold text-foreground">댓글 패널</h3>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    위치 마커, 스레드, 멘션 입력이 연결된 상태입니다.
                                </p>
                            </div>

                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setIsCommentPanelOpen(false)}
                                aria-label="댓글 패널 닫기"
                            >
                                <X size={18} />
                            </Button>
                        </div>

                        {commentPanelBody}
                    </Card>
                )}
            </div>

            <Sheet open={isMobileCommentLayout && isCommentPanelOpen} onOpenChange={setIsCommentPanelOpen}>
                <SheetContent className="w-[min(92vw,380px)] lg:hidden">
                    <SheetHeader>
                        <SheetTitle>댓글 패널</SheetTitle>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setIsCommentPanelOpen(false)}
                            aria-label="댓글 패널 닫기"
                        >
                            <X size={18} />
                        </Button>
                    </SheetHeader>

                    {commentPanelBody}
                </SheetContent>
            </Sheet>
        </div>
    )
}
