import { deleteDocument, downloadSummaryPdf, fetchDocumentDetail } from '@/api/documents'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ArrowLeft, Download, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

export default function DocumentPage() {
  const { doc_id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { user } = useAuth()
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchDocumentDetail(doc_id)
        setDoc(data)
      } catch {
        setError('문서를 불러오지 못했습니다.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [doc_id])

  if (loading) return (
    <div className="max-w-3xl mx-auto px-4 py-12 text-center text-muted-foreground">
      불러오는 중...
    </div>
  )

  if (error || !doc) return (
    <div className="max-w-3xl mx-auto px-4 py-12 text-center text-destructive">
      {error || '문서를 찾을 수 없습니다.'}
    </div>
  )

  const s = doc
  const isAdmin = user?.role === 'ADMIN'
  const isOwner = user?.username === doc?.uploader
  const canDelete = isAdmin || isOwner

  const handleDownload = async () => {
    if (!s.summary_id) return
    try {
      await downloadSummaryPdf(s.summary_id, s.case_number, s.summary_title)
    } catch {
      toast.error('다운로드에 실패했습니다.')
    }
  }

  const handleDeleteConfirm = async () => {
    try {
      await deleteDocument(doc_id)
      navigate('/workspace', { state: { deleted: true } })
    } catch {
      toast.error('삭제에 실패했습니다.')
      setShowDeleteModal(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 flex flex-col gap-5">

      {/* 상단 액션 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="gap-1.5">
          <ArrowLeft size={15} />
          워크스페이스로
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
                <Button variant="destructive" size="sm" onClick={() => setShowDeleteModal(true)} className="gap-1.5">
                  <Trash2 size={14} />
                  삭제
                </Button>
              </TooltipTrigger>
              <TooltipContent>문서를 영구 삭제합니다</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>

      <ConfirmModal
        open={showDeleteModal}
        message={'정말 삭제하시겠습니까?\n삭제된 문서는 복구할 수 없습니다.'}
        confirmLabel="삭제"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteModal(false)}
      />

      {/* 제목 + 메타 */}
      <div className="px-1">
        <h1 className="text-2xl font-bold mb-3">{s.case_name || s.summary_title || '제목 없음'}</h1>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <div className="flex gap-1.5">
            <span className="font-medium text-foreground">법원</span>
            <span>{s.court_name || '-'}</span>
          </div>
          <div className="flex gap-1.5">
            <span className="font-medium text-foreground">사건번호</span>
            <span>{s.case_number || '-'}</span>
          </div>
          <div className="flex gap-1.5">
            <span className="font-medium text-foreground">판결일</span>
            <span>{s.judgment_date || '-'}</span>
          </div>
        </div>
      </div>

      {/* 섹션 카드들 */}
      {[
        { title: 'AI 요약',   content: s.summary_main },
        { title: '사실 관계', content: s.facts },
        { title: '판결 주문', content: s.judgment_order },
        { title: '판단 근거', content: s.judgment_reason },
        { title: '관련 법령', content: s.related_laws },
      ].map(({ title, content }) => (
        <Card key={title} className="p-6">
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">{title}</h3>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{content || '-'}</p>
        </Card>
      ))}

      {/* 당사자 */}
      <Card className="p-6">
        <h3 className="text-sm font-semibold text-muted-foreground mb-3">당사자</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">원고</p>
            <p className="text-sm font-medium">{s.plaintiff || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">피고</p>
            <p className="text-sm font-medium">{s.defendant || '-'}</p>
          </div>
        </div>
      </Card>
    </div>
  )
}