import { deleteGroupDocument, getGroupDocumentDetail, getGroupDocumentOriginalUrl } from '@/api/groups'
import { downloadSummaryPdf } from '@/api/documents'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ArrowLeft, Download, Trash2, ExternalLink } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { toast } from 'sonner'

export default function DocumentPage() {
    const { group_id, doc_id } = useParams()
    const navigate = useNavigate()
    const location = useLocation()

    const [doc, setDoc] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [showDeleteModal, setShowDeleteModal] = useState(false)

    const backToListUrl = `/workspace/${group_id}${location.search || '?tab=documents'}`
    const originalPdfUrl = getGroupDocumentOriginalUrl(group_id, doc_id)

    useEffect(() => {
        const load = async () => {
            try {
                const docData = await getGroupDocumentDetail(group_id, doc_id)
                setDoc(docData)
            } catch (e) {
                setError(e.message || '문서를 불러오지 못했습니다.')
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [group_id, doc_id])


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

    const STATUS_MESSAGE = {
        PENDING: 'AI 요약 대기 중입니다. 잠시 후 다시 확인해주세요.',
        PROCESSING: 'AI가 문서를 분석하고 있습니다. 잠시 후 요약이 표시됩니다.',
        FAILED: '요약 생성에 실패했습니다. 다시 업로드하거나 관리자에게 문의해주세요.',
    }

    const s = doc
    const statusMessage = STATUS_MESSAGE[s.status] ?? null
    const hasSummary = Boolean(s.summary_text)

    const isDeletedDocument = Boolean(doc?.delete_scheduled_at)
    const canDelete = Boolean(doc?.can_delete) && !isDeletedDocument

    const isPendingReview = doc?.approval_status === 'PENDING_REVIEW'
    const isRejected = doc?.approval_status === 'REJECTED'

    const calcDday = (isoDate) => {
        if (!isoDate) return null
        const diff = Math.ceil((new Date(isoDate) - new Date()) / (1000 * 60 * 60 * 24))
        return diff <= 0 ? 'D-0' : `D-${diff}`
    }

    const deletedDday = calcDday(doc?.delete_scheduled_at)

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

    return (
        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col gap-5">
            <div className="flex items-center justify-between">
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
                            <a href={originalPdfUrl} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="gap-1.5">
                                    <ExternalLink size={14} />
                                    원문 새 탭
                                </Button>
                            </a>
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
                <h1 className="text-2xl font-bold mb-3">{s.title || '문서 상세'}</h1>
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
                        <span>
                            {s.created_at
                                ? new Date(s.created_at).toLocaleString('ko-KR', {
                                      year: 'numeric',
                                      month: '2-digit',
                                      day: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                      hour12: false,
                                  })
                                : '-'}
                        </span>
                    </div>
                </div>
            </div>

            <Card className="p-6">
                <h3 className="text-sm font-semibold text-muted-foreground mb-2">AI 요약</h3>

                {hasSummary ? (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{s.summary_text}</p>
                ) : statusMessage ? (
                    <div className="rounded-md border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        {statusMessage}
                    </div>
                ) : (
                    <p className="text-sm leading-relaxed text-muted-foreground">요약 정보가 없습니다.</p>
                )}
            </Card>

            <Card className="p-6">
                <h3 className="text-sm font-semibold text-muted-foreground mb-3">핵심 포인트</h3>
                {s.key_points?.length ? (
                    <ul className="list-disc pl-5 space-y-2 text-sm">
                        {s.key_points.map((point) => (
                            <li key={point}>{point}</li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm font-medium">-</p>
                )}
            </Card>

            <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b px-6 py-4">
                    <div>
                        <h3 className="text-sm font-semibold text-muted-foreground">원문 PDF</h3>
                        <p className="mt-1 text-xs text-muted-foreground">
                            브라우저 기본 PDF 뷰어로 원문을 바로 확인할 수 있습니다.
                        </p>
                    </div>
                    <a href={originalPdfUrl} target="_blank" rel="noreferrer">
                        <Button variant="outline" size="sm" className="gap-1.5">
                            <ExternalLink size={14} />
                            새 탭에서 보기
                        </Button>
                    </a>
                </div>

                <div className="h-[75vh] bg-muted/20">
                    <iframe
                        title={`${s.title || '문서'} 원문 PDF`}
                        src={originalPdfUrl}
                        className="h-full w-full"
                    />
                </div>
            </Card>
        </div>
    )
}
