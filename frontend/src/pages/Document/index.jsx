import { deleteGroupDocument, getGroupDocumentDetail } from '@/api/groups'
import { downloadSummaryPdf } from '@/api/documents'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ArrowLeft, Download, Trash2 } from 'lucide-react'
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

    const canDelete = Boolean(doc?.can_delete)

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
        <div className="max-w-3xl mx-auto px-4 py-8 flex flex-col gap-5">
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

            {/* 제목 + 메타 */}
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
                </div>
            </div>

            {/* AI 요약 */}
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

            {/* 핵심 포인트 */}
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
        </div>
    )
}
