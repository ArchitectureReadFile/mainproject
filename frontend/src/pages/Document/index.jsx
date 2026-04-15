import {
    approveDocument,
    createDocumentComment,
    deleteDocumentComment,
    deleteGroupDocument,
    getDocumentComments,
    getGroupDetail,
    getGroupDocumentDetail,
    getGroupDocumentDownloadUrl,
    getGroupDocumentPreviewUrl,
    getMembers,
    rejectDocument,
    updateDocumentClassification,
} from '@/shared/api/groups'
import {
    calcKoreanDday,
    formatKoreanDate,
    formatKoreanDateTime,
} from '@/shared/lib/datetime'
import { Avatar, AvatarFallback } from '@/shared/ui/avatar'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/card'
import { ConfirmModal } from '@/shared/ui/confirm-modal'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/shared/ui/Dialog'
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from '@/shared/ui/Sheet'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import { useAuth } from '@/features/auth/context/AuthContext'
import { cn } from '@/shared/lib/utils'
import {
    ArrowLeft,
    ChevronDown,
    ChevronUp,
    Download,
    ExternalLink,
    Loader2,
    MapPin,
    MessageSquareText,
    Minus,
    PanelRightClose,
    PanelRightOpen,
    Plus,
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

const PDF_OPTIONS = {
    withCredentials: true,
}

const DOCUMENT_TYPE_OPTIONS = [
    { value: '계약서', label: '계약서' },
    { value: '신청서', label: '신청서' },
    { value: '준비서면', label: '준비서면' },
    { value: '의견서', label: '의견서' },
    { value: '내용증명', label: '내용증명' },
    { value: '소장', label: '소장' },
    { value: '고소장', label: '고소장' },
    { value: '기타', label: '기타' },
    { value: '미분류', label: '미분류' },
]

const CATEGORY_OPTIONS = [
    { value: '민사', label: '민사' },
    { value: '계약', label: '계약' },
    { value: '회사', label: '회사' },
    { value: '행정', label: '행정' },
    { value: '형사', label: '형사' },
    { value: '노동', label: '노동' },
    { value: '기타', label: '기타' },
    { value: '미분류', label: '미분류' },
]

/**
 * 댓글 시간 표시 문자열을 만든다.
 */
function formatCommentDate(value) {
    return formatKoreanDateTime(value)
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
 * 멘션 span을 반영해서 댓글 본문을 렌더링한다.(멘션 강조)
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

/**
 * 삭제되지 않은 댓글 트리 전체 개수를 계산
 */
function countVisibleComments(comments) {
    return comments.reduce((count, comment) => {
        const selfCount = comment.is_deleted ? 0 : 1
        return count + selfCount + countVisibleComments(comment.replies ?? [])
    }, 0)
}

const MIN_ZOOM = 0.6
const MAX_ZOOM = 2
const ZOOM_STEP = 0.1
const PAN_THRESHOLD = 4

/**
 * PDF 줌 값을 허용 범위 안으로 보정한다.
 */
function clampZoom(value) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value))
}

/**
 * 현재 줌 값을 입력창용 퍼센트 문자열로 변환한다.
 */
function formatZoomInput(value) {
    return String(Math.round(value * 100))
}

/**
 * 퍼센트 입력값을 실제 PDF 배율로 변환한다.
 */
function parseZoomInput(value) {
    if (!value) return null

    const nextPercent = Number(value)
    if (!Number.isFinite(nextPercent)) {
        return null
    }

    const nextZoom = nextPercent / 100
    if (nextZoom < MIN_ZOOM || nextZoom > MAX_ZOOM) {
        return null
    }

    return Number(nextZoom.toFixed(2))
}

/**
 * 사용자 표시명을 반환한다.
 */
function formatUserDisplayName(user) {
    if (!user?.username) return '알 수 없음'
    return user.is_active === false
        ? `${user.username}(탈퇴)`
        : user.username
}

/**
 * 아바타용 사용자 이니셜을 반환한다.
 */
function formatUserInitials(user) {
    if (!user?.username) return '??'
    return user.username.slice(0, 2).toUpperCase()
}

export default function DocumentPage() {
    const { user } = useAuth()
    const { group_id, doc_id } = useParams()
    const navigate = useNavigate()
    const location = useLocation()

    const [doc, setDoc] = useState(null)
    const [groupMeta, setGroupMeta] = useState(null)
    const [comments, setComments] = useState([])
    const [members, setMembers] = useState([])
    const [loading, setLoading] = useState(true)
    const [commentsLoading, setCommentsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [pdfError, setPdfError] = useState(null)

    const [showDeleteModal, setShowDeleteModal] = useState(false)
    const [showApproveModal, setShowApproveModal] = useState(false)
    const [showRejectModal, setShowRejectModal] = useState(false)
    const [rejectReason, setRejectReason] = useState('')
    const [reviewActionLoading, setReviewActionLoading] = useState(false)

    const [isCommentPanelOpen, setIsCommentPanelOpen] = useState(false)
    const [isMobileCommentLayout, setIsMobileCommentLayout] = useState(false)

    const [draftContent, setDraftContent] = useState('')
    const [draftAnchor, setDraftAnchor] = useState(null)
    const [replyParentId, setReplyParentId] = useState(null)
    const [focusedCommentId, setFocusedCommentId] = useState(null)
    const [isSubmittingComment, setIsSubmittingComment] = useState(false)
    const [deletingCommentId, setDeletingCommentId] = useState(null)
    const [isComposerOpen, setIsComposerOpen] = useState(false)

    const [currentPage, setCurrentPage] = useState(1)
    const [pageInput, setPageInput] = useState('1')
    const [zoom, setZoom] = useState(1)
    const [zoomInput, setZoomInput] = useState('100')
    const [isPanning, setIsPanning] = useState(false)

    const [showClassificationConfirmModal, setShowClassificationConfirmModal] = useState(false)
    const [isClassificationEditMode, setIsClassificationEditMode] = useState(false)
    const [classificationDocumentType, setClassificationDocumentType] = useState('')
    const [classificationCategory, setClassificationCategory] = useState('')
    const [isClassificationSubmitting, setIsClassificationSubmitting] = useState(false)

    const explicitCommentScope = useMemo(() => {
        const params = new URLSearchParams(location.search)
        const rawScope = params.get('comment_scope')

        if (rawScope === 'review') {
            return 'REVIEW'
        }

        if (rawScope === 'general') {
            return 'GENERAL'
        }

        return null
    }, [location.search])

    /**
     * 문서 상태와 현재 사용자 권한을 기준으로 기본 댓글 scope를 계산한다.
     * 승인 대기/반려 문서에 접근 가능한 업로더, OWNER, ADMIN은 REVIEW를 기본값으로 사용한다.
     */
    const resolveCommentScope = useCallback((targetDoc) => {
        if (explicitCommentScope) {
            return explicitCommentScope
        }

        const isReviewDocument =
            targetDoc?.approval_status === 'PENDING_REVIEW' ||
            targetDoc?.approval_status === 'REJECTED'

        const canAccessReviewComments = Boolean(targetDoc?.can_delete)

        if (isReviewDocument && canAccessReviewComments) {
            return 'REVIEW'
        }

        return 'GENERAL'
    }, [explicitCommentScope])

    const commentScope = useMemo(() => {
        return resolveCommentScope(doc)
    }, [doc, resolveCommentScope])

    const commentPanelMeta = useMemo(() => {
        if (commentScope === 'REVIEW') {
            return {
                title: '검토 댓글',
                description: '검토 중 의견 공유용 댓글입니다. 최종 반려 사유는 별도로 입력해주세요.',
            }
        }

        return {
            title: '문서 댓글',
            description: '문서 협업용 댓글입니다.',
        }
    }, [commentScope])


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
    const panStateRef = useRef({
        active: false,
        startX: 0,
        startY: 0,
        scrollLeft: 0,
        scrollTop: 0,
        moved: false,
    })
    const suppressPdfClickRef = useRef(false)
    const pendingZoomCenterRef = useRef(null)

    const backToListUrl = `/workspace/${group_id}${location.search || '?tab=documents'}`
    const previewPdfUrl = getGroupDocumentPreviewUrl(group_id, doc_id)
    const downloadUrl = getGroupDocumentDownloadUrl(group_id, doc_id)

    const STATUS_MESSAGE = {
        PENDING: 'AI 요약 대기 중입니다. 잠시 후 다시 확인해주세요.',
        PROCESSING: 'AI가 문서를 분석하고 있습니다. 잠시 후 요약이 표시됩니다.',
        FAILED: '요약 생성에 실패했습니다. 다시 업로드하거나 관리자에게 문의해주세요.',
    }

    const PREVIEW_STATUS_MESSAGE = {
        PENDING: '미리보기 PDF를 준비 중입니다. 잠시 후 다시 확인해주세요.',
        PROCESSING: '문서 미리보기를 생성하고 있습니다. 잠시 후 다시 확인해주세요.',
        FAILED: '미리보기 변환에 실패했습니다. 원본 파일을 다운로드해 확인해주세요.',
    }

    /**
     * 현재 줌 배율을 반영한 PDF 렌더링 너비를 계산한다.
     */
    const renderedPageWidth = useMemo(() => {
        return Math.floor(pageWidth * zoom)
    }, [pageWidth, zoom])


    /**
     * 댓글 목록만 다시 불러온다.
     */
    const loadComments = useCallback(async () => {
        setCommentsLoading(true)

        try {
            const commentData = await getDocumentComments(group_id, doc_id, {
                scope: commentScope,
            })
            setComments(commentData.items ?? [])
        } catch (e) {
            toast.error(e.message || '댓글을 불러오지 못했습니다.')
        } finally {
            setCommentsLoading(false)
        }
    }, [group_id, doc_id, commentScope])

    /**
     * 문서 상세, 댓글, 멤버 목록을 로드하고 리뷰 버튼용 그룹 메타는 별도로 보강한다.
     */
    const loadPageData = useCallback(async () => {
        setLoading(true)
        setCommentsLoading(true)

        try {
            const [docData, memberData] = await Promise.all([
                getGroupDocumentDetail(group_id, doc_id),
                getMembers(group_id),
            ])

            const nextCommentScope = resolveCommentScope(docData)
            const commentData = await getDocumentComments(group_id, doc_id, {
                scope: nextCommentScope,
            })

            setDoc(docData)
            setComments(commentData.items ?? [])
            setMembers(memberData.members ?? [])
            setError(null)

            try {
                const groupData = await getGroupDetail(group_id)
                setGroupMeta(groupData)
            } catch (e) {
                console.error('그룹 메타 조회 실패:', e)
                setGroupMeta(null)
            }
        } catch (e) {
            setError(e.message || '문서를 불러오지 못했습니다.')
        } finally {
            setLoading(false)
            setCommentsLoading(false)
        }
    }, [group_id, doc_id, resolveCommentScope])

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
     * 댓글 좌표 기준으로 PDF 뷰어 내부 스크롤을 이동한다.
     * 확대 상태에서도 좌표가 보이도록 가로/세로를 함께 중앙 정렬한다.
     */
    const scrollToMarker = useCallback((anchor) => {
        const pageEl = pageRefs.current[anchor.page]
        const viewerEl = viewerRef.current

        if (!pageEl || !viewerEl) {
            return
        }

        const pageRect = pageEl.getBoundingClientRect()
        const viewerRect = viewerEl.getBoundingClientRect()

        const markerTopInViewer =
            pageRect.top - viewerRect.top + viewerEl.scrollTop + pageEl.clientHeight * anchor.y
        const markerLeftInViewer =
            pageRect.left - viewerRect.left + viewerEl.scrollLeft + pageEl.clientWidth * anchor.x

        viewerEl.scrollTo({
            top: Math.max(0, markerTopInViewer - viewerEl.clientHeight / 2),
            left: Math.max(0, markerLeftInViewer - viewerEl.clientWidth / 2),
            behavior: 'smooth',
        })
    }, [])


    /**
     * 특정 페이지로 PDF 뷰어 스크롤을 이동한다.
     */
    const scrollToPage = useCallback((pageNumber) => {
        const pageEl = pageRefs.current[pageNumber]
        const viewerEl = viewerRef.current

        if (!pageEl || !viewerEl) {
            return
        }

        const pageRect = pageEl.getBoundingClientRect()
        const viewerRect = viewerEl.getBoundingClientRect()

        const nextScrollTop =
            pageRect.top - viewerRect.top + viewerEl.scrollTop - 12

        viewerEl.scrollTo({
            top: Math.max(0, nextScrollTop),
            behavior: 'smooth',
        })

        setCurrentPage(pageNumber)
        setPageInput(String(pageNumber))
    }, [])


    /**
     * 특정 댓글 스레드를 패널과 PDF 양쪽에서 동시에 포커싱한다.
     */
    const focusCommentThread = useCallback((comment) => {
        const anchor = getCommentAnchor(comment)

        setIsCommentPanelOpen(true)
        setFocusedCommentId(comment.id)

        if (anchor) {
            setCurrentPage(anchor.page)
            setPageInput(String(anchor.page))

            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    scrollToMarker(anchor)
                })
            })
        }

        window.setTimeout(() => {
            commentRefs.current[comment.id]?.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
            })
        }, 180)
    }, [scrollToMarker])


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


    /**
     * 뷰어 스크롤 위치를 기준으로 현재 보고 있는 페이지를 추적한다.
     */
    useEffect(() => {
        const viewerEl = viewerRef.current
        if (!viewerEl) {
            return
        }

        const handleScroll = () => {
            if (!numPages) {
                return
            }

            const viewerRect = viewerEl.getBoundingClientRect()
            const viewerCenterY = viewerRect.top + viewerEl.clientHeight / 2

            let nearestPage = 1
            let nearestDistance = Number.POSITIVE_INFINITY

            for (let pageNumber = 1; pageNumber <= numPages; pageNumber += 1) {
                const pageEl = pageRefs.current[pageNumber]
                if (!pageEl) {
                    continue
                }

                const pageRect = pageEl.getBoundingClientRect()
                const pageCenterY = pageRect.top + pageRect.height / 2
                const distance = Math.abs(pageCenterY - viewerCenterY)

                if (distance < nearestDistance) {
                    nearestDistance = distance
                    nearestPage = pageNumber
                }
            }

            setCurrentPage(nearestPage)
            setPageInput(String(nearestPage))
        }

        viewerEl.addEventListener('scroll', handleScroll, { passive: true })
        handleScroll()

        return () => {
            viewerEl.removeEventListener('scroll', handleScroll)
        }
    }, [numPages])


    const s = doc
    const statusMessage = STATUS_MESSAGE[s?.status] ?? null
    const hasSummary = Boolean(s?.summary_text)

    const previewStatus = s?.preview_status ?? null
    const previewAvailable = Boolean(s?.preview_available)
    const previewStatusMessage = PREVIEW_STATUS_MESSAGE[previewStatus] ?? null
    const canRenderPreview = previewAvailable && previewStatus === 'READY'

    const isDeletedDocument = Boolean(doc?.delete_scheduled_at)
    const canDelete = Boolean(doc?.can_delete) && !isDeletedDocument

    const isPendingReview = doc?.approval_status === 'PENDING_REVIEW'
    const isRejected = doc?.approval_status === 'REJECTED'

    const isClassificationEditable =
        !isDeletedDocument &&
        s?.status === 'DONE' &&
        groupMeta?.status === 'ACTIVE' &&
        ['OWNER', 'ADMIN'].includes(groupMeta?.my_role)

    const hasClassificationChanged =
        classificationDocumentType !== (s?.document_type || '미분류') ||
        classificationCategory !== (s?.category || '미분류')

    /**
     * 상세 페이지에서 승인/반려 버튼 노출 여부를 계산한다.
     */
    const canReviewDocument =
        !isDeletedDocument &&
        isPendingReview &&
        groupMeta?.status === 'ACTIVE' &&
        ['OWNER', 'ADMIN'].includes(groupMeta?.my_role)

    const mentionableMembers = useMemo(() => {
        return members.filter(
            (member) => member.user_id !== user?.id && member.is_active !== false
        )
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
        return countVisibleComments(comments)
    }, [comments])

    const replyTarget = useMemo(() => {
        return comments.find((comment) => comment.id === replyParentId) ?? null
    }, [comments, replyParentId])

    const calcDday = (isoDate) => {
        return calcKoreanDday(isoDate)
    }

    const deletedDday = calcDday(doc?.delete_scheduled_at)


    /**
     * 줌 변경 전후에도 현재 보고 있는 중심 영역이 크게 튀지 않도록 배율을 갱신한다.
     */
    const applyZoom = useCallback((nextZoom) => {
        const normalizedZoom = clampZoom(Number(nextZoom.toFixed(2)))
        const viewerEl = viewerRef.current

        if (!viewerEl) {
            setZoom(normalizedZoom)
            setZoomInput(formatZoomInput(normalizedZoom))
            return
        }

        const prevCenterX = viewerEl.scrollLeft + viewerEl.clientWidth / 2
        const prevCenterY = viewerEl.scrollTop + viewerEl.clientHeight / 2
        const prevScrollWidth = Math.max(viewerEl.scrollWidth, viewerEl.clientWidth, 1)
        const prevScrollHeight = Math.max(viewerEl.scrollHeight, viewerEl.clientHeight, 1)

        pendingZoomCenterRef.current = {
            centerRatioX: prevCenterX / prevScrollWidth,
            centerRatioY: prevCenterY / prevScrollHeight,
        }

        setZoom(normalizedZoom)
        setZoomInput(formatZoomInput(normalizedZoom))
    }, [])

    /**
     * PDF 폭이 다시 계산된 뒤 뷰어 중심을 자연스럽게 복원한다.
     */
    useEffect(() => {
        const viewerEl = viewerRef.current
        const pendingCenter = pendingZoomCenterRef.current

        if (!viewerEl || !pendingCenter) {
            return
        }

        let frameA = 0
        let frameB = 0

        frameA = window.requestAnimationFrame(() => {
            frameB = window.requestAnimationFrame(() => {
                const nextScrollWidth = Math.max(viewerEl.scrollWidth, viewerEl.clientWidth, 1)
                const nextScrollHeight = Math.max(viewerEl.scrollHeight, viewerEl.clientHeight, 1)

                viewerEl.scrollTo({
                    left: Math.max(0, nextScrollWidth * pendingCenter.centerRatioX - viewerEl.clientWidth / 2),
                    top: Math.max(0, nextScrollHeight * pendingCenter.centerRatioY - viewerEl.clientHeight / 2),
                })

                pendingZoomCenterRef.current = null
            })
        })

        return () => {
            window.cancelAnimationFrame(frameA)
            window.cancelAnimationFrame(frameB)
        }
    }, [zoom, renderedPageWidth])


    /**
     * 드래그 팬 종료 시 상태를 정리한다.
     */
    const finishViewerPan = useCallback(() => {
        const didMove = panStateRef.current.moved

        panStateRef.current = {
            active: false,
            startX: 0,
            startY: 0,
            scrollLeft: 0,
            scrollTop: 0,
            moved: false,
        }
        setIsPanning(false)

        if (didMove) {
            window.setTimeout(() => {
                suppressPdfClickRef.current = false
            }, 0)
        }
    }, [])

    const handleStartClassificationEdit = () => {
        setClassificationDocumentType(s?.document_type || '미분류')
        setClassificationCategory(s?.category || '미분류')
        setIsClassificationEditMode(true)
    }

    const handleCancelClassificationEdit = () => {
        setClassificationDocumentType(s?.document_type || '미분류')
        setClassificationCategory(s?.category || '미분류')
        setIsClassificationEditMode(false)
        setShowClassificationConfirmModal(false)
    }

    const handleOpenClassificationConfirmModal = () => {
        if (!hasClassificationChanged || isClassificationSubmitting) {
            return
        }

        setShowClassificationConfirmModal(true)
    }

    const handleConfirmClassificationUpdate = async () => {
        if (!s || isClassificationSubmitting) return

        setIsClassificationSubmitting(true)

        try {
            await updateDocumentClassification(group_id, doc_id, {
                document_type: classificationDocumentType,
                category: classificationCategory,
            })

            const updatedDoc = await getGroupDocumentDetail(group_id, doc_id)
            setDoc(updatedDoc)
            setIsClassificationEditMode(false)
            setShowClassificationConfirmModal(false)
            toast.success('문서 분류를 수정했습니다.')
        } catch (e) {
            toast.error(e.message || '문서 분류를 수정하지 못했습니다.')
        } finally {
            setIsClassificationSubmitting(false)
        }
    }

    /**
     * 문서를 승인한다.
     */
    const handleApproveConfirm = async () => {
        setReviewActionLoading(true)

        try {
            await approveDocument(group_id, doc_id)
            setShowApproveModal(false)
            toast.success('문서를 승인했습니다.')

            try {
                await loadPageData()
            } catch (e) {
                console.error('문서 재조회 실패:', e)
            }
        } catch (e) {
            toast.error(e.message || '문서 승인에 실패했습니다.')
        } finally {
            setReviewActionLoading(false)
        }
    }

    /**
     * 문서를 반려한다.
     */
    const handleRejectConfirm = async () => {
        if (!rejectReason.trim()) {
            toast.error('반려 사유를 입력해주세요.')
            return
        }

        setReviewActionLoading(true)

        try {
            await rejectDocument(group_id, doc_id, rejectReason.trim())
            setShowRejectModal(false)
            setRejectReason('')
            toast.success('문서를 반려했습니다.')

            try {
                await loadPageData()
            } catch (e) {
                console.error('문서 재조회 실패:', e)
            }
        } catch (e) {
            toast.error(e.message || '문서 반려에 실패했습니다.')
        } finally {
            setReviewActionLoading(false)
        }
    }

    /**
     * 페이지 입력값을 기준으로 해당 페이지로 이동한다.
     */
    const handleMoveToPage = () => {
        const nextPage = Number(pageInput)

        if (!Number.isInteger(nextPage) || nextPage < 1 || nextPage > numPages) {
            toast.error(`1부터 ${numPages} 사이의 페이지를 입력해주세요.`)
            setPageInput(String(currentPage))
            return
        }

        scrollToPage(nextPage)
    }

    /**
     * 버튼 클릭 기준으로 PDF 줌 배율을 변경한다.
     */
    const handleZoomChange = (delta) => {
        applyZoom(zoom + delta)
    }

    /**
     * 줌 퍼센트 입력값을 숫자만 유지하면서 상태에 반영한다.
     */
    const handleZoomInputChange = (event) => {
        setZoomInput(event.target.value.replace(/\D/g, ''))
    }

    /**
     * 줌 퍼센트 입력값을 검증한 뒤 PDF 배율에 반영한다.
     */
    const handleApplyZoomInput = () => {
        const nextZoom = parseZoomInput(zoomInput)

        if (nextZoom == null) {
            toast.error(
                `${Math.round(MIN_ZOOM * 100)}부터 ${Math.round(MAX_ZOOM * 100)} 사이의 줌 값을 입력해주세요.`
            )
            setZoomInput(formatZoomInput(zoom))
            return
        }

        applyZoom(nextZoom)
    }

    /**
     * 확대 상태에서 마우스 드래그로 PDF 뷰어를 탐색할 수 있게 한다.
     */
    const handleViewerMouseDown = (event) => {
        const viewerEl = viewerRef.current
        const target = event.target
        const targetEl =
            target && typeof target.closest === 'function'
                ? target
                : null

        if (!viewerEl || zoom <= 1 || event.button !== 0) {
            return
        }

        if (targetEl?.closest('button')) {
            return
        }

        panStateRef.current = {
            active: true,
            startX: event.clientX,
            startY: event.clientY,
            scrollLeft: viewerEl.scrollLeft,
            scrollTop: viewerEl.scrollTop,
            moved: false,
        }
        suppressPdfClickRef.current = false
    }


    /**
     * 드래그 중인 거리만큼 스크롤 좌표를 갱신한다.
     */
    const handleViewerMouseMove = useCallback((event) => {
        const viewerEl = viewerRef.current
        const panState = panStateRef.current

        if (!viewerEl || !panState.active) {
            return
        }

        const deltaX = event.clientX - panState.startX
        const deltaY = event.clientY - panState.startY

        if (!panState.moved && (Math.abs(deltaX) > PAN_THRESHOLD || Math.abs(deltaY) > PAN_THRESHOLD)) {
            panState.moved = true
            suppressPdfClickRef.current = true
            setIsPanning(true)
        }

        if (!panState.moved) {
            return
        }

        event.preventDefault()
        viewerEl.scrollTo({
            left: panState.scrollLeft - deltaX,
            top: panState.scrollTop - deltaY,
        })
    }, [])

    /**
     * PDF 페이지 클릭 좌표를 댓글 앵커로 저장한다.
     * 드래그 팬 직후 발생한 클릭은 무시한다.
     */
    const handlePdfPageClick = (pageNumber, event) => {
        if (suppressPdfClickRef.current) {
            return
        }

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

    /**
     * 뷰어 바깥에서 마우스를 놓아도 드래그 팬이 정상 종료되도록 전역 이벤트를 연결한다.
     */
    useEffect(() => {
        const handleWindowMouseMove = (event) => {
            handleViewerMouseMove(event)
        }

        const handleWindowMouseUp = () => {
            finishViewerPan()
        }

        window.addEventListener('mousemove', handleWindowMouseMove)
        window.addEventListener('mouseup', handleWindowMouseUp)

        return () => {
            window.removeEventListener('mousemove', handleWindowMouseMove)
            window.removeEventListener('mouseup', handleWindowMouseUp)
        }
    }, [finishViewerPan, handleViewerMouseMove])


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

        const isRootComment = !replyParentId

        setIsSubmittingComment(true)

        try {
            const payload = {
                scope: commentScope,
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

            if (isRootComment) {
                setIsComposerOpen(false)
            }

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

    /**
     * 원본 문서 다운로드
     */
    const handleDownload = () => {
        const link = document.createElement('a')
        link.href = downloadUrl
        document.body.appendChild(link)
        link.click()
        link.remove()
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
                                {formatUserInitials(comment.author)}
                            </AvatarFallback>
                        </Avatar>

                        <div>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-semibold text-foreground">
                                    {formatUserDisplayName(comment.author)}
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
                                            {formatUserDisplayName(reply.author)}
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
                                <p className="text-sm font-semibold text-foreground">{commentPanelMeta.title}</p>
                                <p className="text-xs text-muted-foreground">
                                    {commentPanelMeta.description}
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
                                    답글 대상 @{formatUserDisplayName(replyTarget.author)}
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
                    {canReviewDocument && (
                        <>
                            <Button
                                size="sm"
                                onClick={() => setShowApproveModal(true)}
                                disabled={reviewActionLoading}
                                className="gap-1.5"
                            >
                                {reviewActionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : '승인'}
                            </Button>

                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setShowRejectModal(true)}
                                disabled={reviewActionLoading}
                                className="gap-1.5"
                            >
                                반려
                            </Button>
                        </>
                    )}
                    {isClassificationEditable && !isClassificationEditMode && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleStartClassificationEdit}
                                    className="gap-1.5"
                                >
                                    분류 수정
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                문서 유형과 카테고리를 수정합니다
                            </TooltipContent>
                        </Tooltip>
                    )}
                    {doc && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="outline" size="sm" onClick={handleDownload} className="gap-1.5">
                                    <Download size={14} />
                                    원본 다운로드
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>원본 파일을 다운로드합니다</TooltipContent>
                        </Tooltip>
                    )}

                    <Tooltip>
                        <TooltipTrigger asChild>
                            {canRenderPreview ? (
                                <Button asChild variant="outline" size="sm" className="gap-1.5">
                                    <a href={previewPdfUrl} target="_blank" rel="noreferrer">
                                        <ExternalLink size={14} />
                                        새 탭으로 열기
                                    </a>
                                </Button>
                            ) : (
                                <Button variant="outline" size="sm" className="gap-1.5" disabled>
                                    <ExternalLink size={14} />
                                    새 탭으로 열기
                                </Button>
                            )}
                        </TooltipTrigger>
                        <TooltipContent>
                            {canRenderPreview ? '미리보기 PDF를 새 탭에서 엽니다' : '미리보기가 아직 준비되지 않았습니다'}
                        </TooltipContent>
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

            <ConfirmModal
                open={showApproveModal}
                message="이 문서를 승인하시겠습니까?"
                confirmLabel={reviewActionLoading ? '처리 중...' : '승인'}
                onConfirm={handleApproveConfirm}
                onCancel={() => setShowApproveModal(false)}
            />

            <ConfirmModal
                open={showClassificationConfirmModal}
                message={'문서 분류를 수정하시겠습니까?\n분류를 변경하면 챗봇 답변에 활용되는 문서 검색 결과가 달라질 수 있습니다.'}
                confirmLabel={isClassificationSubmitting ? '처리 중...' : '수정'}
                onConfirm={handleConfirmClassificationUpdate}
                onCancel={() => {
                    if (isClassificationSubmitting) return
                    setShowClassificationConfirmModal(false)
                }}
            />

            <Dialog
                open={showRejectModal}
                onOpenChange={(open) => {
                    if (!open) {
                        setShowRejectModal(false)
                        setRejectReason('')
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>문서 반려</DialogTitle>
                        <DialogDescription>
                            문서 반려 사유를 입력하는 검토 모달입니다.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            반려 사유를 입력해주세요.
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
                                setShowRejectModal(false)
                                setRejectReason('')
                            }}
                        >
                            취소
                        </Button>
                        <Button
                            onClick={handleRejectConfirm}
                            disabled={reviewActionLoading}
                        >
                            {reviewActionLoading ? '처리 중...' : '반려'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {isDeletedDocument && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <p className="font-medium">휴지통에 있는 문서입니다.</p>
                    <p className="mt-1 text-xs">
                        {doc.delete_scheduled_at
                            ? `${formatKoreanDate(doc.delete_scheduled_at)} 삭제 예정 (${deletedDday})`
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
                <div className="mb-3 flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-bold">{s.title || '문서 상세'}</h1>

                    {isClassificationEditMode && (
                        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                            분류 수정 중
                        </span>
                    )}
                </div>

                {isClassificationEditMode ? (
                    <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
                        <div className="flex flex-col gap-3 md:flex-row">
                            <div className="flex-1 space-y-2">
                                <p className="text-xs font-medium text-muted-foreground">문서 유형</p>
                                <Select
                                    value={classificationDocumentType}
                                    onValueChange={setClassificationDocumentType}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="문서 유형 선택" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {DOCUMENT_TYPE_OPTIONS.map((option) => (
                                            <SelectItem key={option.value} value={option.value}>
                                                {option.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex-1 space-y-2">
                                <p className="text-xs font-medium text-muted-foreground">카테고리</p>
                                <Select
                                    value={classificationCategory}
                                    onValueChange={setClassificationCategory}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="카테고리 선택" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {CATEGORY_OPTIONS.map((option) => (
                                            <SelectItem key={option.value} value={option.value}>
                                                {option.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                            분류를 변경하면 챗봇 답변에 활용되는 문서 검색 결과가 달라질 수 있습니다.
                        </div>

                        <div className="flex flex-wrap justify-end gap-2 pr-3">
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={handleCancelClassificationEdit}
                                disabled={isClassificationSubmitting}
                            >
                                취소
                            </Button>

                            <Tooltip delayDuration={100}>
                                <TooltipTrigger asChild>
                                    <span>
                                        <Button
                                            type="button"
                                            onClick={handleOpenClassificationConfirmModal}
                                            disabled={!hasClassificationChanged || isClassificationSubmitting}
                                        >
                                            {isClassificationSubmitting ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                '저장'
                                            )}
                                        </Button>
                                    </span>
                                </TooltipTrigger>
                                {!hasClassificationChanged && !isClassificationSubmitting && (
                                    <TooltipContent>
                                        변경된 내용이 없습니다.
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
                        <div className="flex gap-1.5">
                            <span className="font-medium text-foreground">문서 유형</span>
                            <span>{s.document_type || '-'}</span>
                        </div>
                        <div className="flex gap-1.5">
                            <span className="font-medium text-foreground">카테고리</span>
                            <span>{s.category || '-'}</span>
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
                )}
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

                        <div className="flex flex-wrap items-center gap-2">
                            <div className="flex items-center gap-1 rounded-lg border bg-background px-2 py-1">
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="size-8"
                                    disabled={currentPage <= 1}
                                    onClick={() => scrollToPage(currentPage - 1)}
                                    aria-label="이전 페이지"
                                >
                                    <ArrowLeft size={14} />
                                </Button>

                                <input
                                    value={pageInput}
                                    onChange={(event) => setPageInput(event.target.value.replace(/\D/g, ''))}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter') {
                                            handleMoveToPage()
                                        }
                                    }}
                                    className="h-8 w-14 rounded-md border px-2 text-center text-sm outline-none"
                                    aria-label="페이지 번호 입력"
                                />

                                <span className="text-xs text-muted-foreground">/ {numPages || 1}</span>

                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 text-xs"
                                    onClick={handleMoveToPage}
                                >
                                    이동
                                </Button>

                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="size-8"
                                    disabled={!numPages || currentPage >= numPages}
                                    onClick={() => scrollToPage(currentPage + 1)}
                                    aria-label="다음 페이지"
                                >
                                    <ArrowLeft size={14} className="rotate-180" />
                                </Button>
                            </div>

                            <div className="flex items-center gap-1 rounded-lg border bg-background px-2 py-1">
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="size-8"
                                    onClick={() => handleZoomChange(-ZOOM_STEP)}
                                    aria-label="축소"
                                >
                                    <Minus size={14} />
                                </Button>

                                <input
                                    value={zoomInput}
                                    onChange={handleZoomInputChange}
                                    onBlur={handleApplyZoomInput}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter') {
                                            handleApplyZoomInput()
                                            event.currentTarget.blur()
                                        }

                                        if (event.key === 'Escape') {
                                            setZoomInput(formatZoomInput(zoom))
                                            event.currentTarget.blur()
                                        }
                                    }}
                                    className="h-8 w-16 rounded-md border px-2 text-center text-sm outline-none"
                                    aria-label="줌 비율 입력"
                                />

                                <span className="text-xs text-muted-foreground">%</span>

                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="size-8"
                                    onClick={() => handleZoomChange(ZOOM_STEP)}
                                    aria-label="확대"
                                >
                                    <Plus size={14} />
                                </Button>
                            </div>

                            <Button
                                variant={isCommentPanelOpen ? 'secondary' : 'default'}
                                size="sm"
                                onClick={() => setIsCommentPanelOpen((prev) => !prev)}
                                className={cn(
                                    'gap-1.5 shadow-sm',
                                    !isCommentPanelOpen && 'bg-primary text-primary-foreground hover:bg-primary/90'
                                )}
                            >
                                {isCommentPanelOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
                                {isCommentPanelOpen ? '댓글 닫기' : `댓글 열기 (${totalCommentCount})`}
                            </Button>
                        </div>
                    </div>

                    <div
                        ref={viewerRef}
                        className={cn(
                            'min-h-0 flex-1 overflow-auto bg-muted/20',
                            zoom > 1 && 'select-none'
                        )}
                        onMouseDown={handleViewerMouseDown}
                    >
                        {pdfError ? (
                            <div className="flex h-full items-center justify-center p-8 text-sm text-destructive">
                                {pdfError}
                            </div>
                        ) : !canRenderPreview ? (
                            <div className="flex h-full items-center justify-center p-8">
                                <div className="max-w-md rounded-xl border bg-background px-6 py-5 text-center">
                                    <p className="text-sm font-medium">
                                        {previewStatusMessage || '미리보기를 준비할 수 없습니다.'}
                                    </p>
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        원본 다운로드는 계속 사용할 수 있습니다.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="mx-auto flex w-fit min-w-full flex-col items-center gap-4 p-4">
                                <PdfDocument
                                    file={previewPdfUrl}
                                    options={PDF_OPTIONS}
                                    loading={
                                        <div className="flex items-center justify-center py-20 text-muted-foreground">
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                        </div>
                                    }
                                    onLoadSuccess={({ numPages: nextNumPages }) => {
                                        setNumPages(nextNumPages)
                                        setCurrentPage(1)
                                        setPageInput('1')
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
                                                className="rounded-xl border bg-white shadow-sm"
                                                style={{ width: renderedPageWidth }}
                                            >
                                                <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-muted-foreground">
                                                    <span>페이지 {pageNumber}</span>

                                                    {draftAnchor?.page === pageNumber && (
                                                        <Badge variant="secondary">선택한 위치</Badge>
                                                    )}
                                                </div>

                                                <div
                                                    ref={(node) => {
                                                        if (node) {
                                                            pageRefs.current[pageNumber] = node
                                                        }
                                                    }}
                                                    className={cn(
                                                        'relative',
                                                        zoom > 1 ? (isPanning ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-crosshair'
                                                    )}
                                                    onClick={(event) => handlePdfPageClick(pageNumber, event)}
                                                >
                                                    <Page
                                                        pageNumber={pageNumber}
                                                        width={renderedPageWidth}
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
                        <div>
                            <SheetTitle>댓글 패널</SheetTitle>
                            <SheetDescription className="sr-only">
                                문서 댓글과 검토 댓글을 확인하고 작성할 수 있는 사이드 패널입니다.
                            </SheetDescription>
                        </div>
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
