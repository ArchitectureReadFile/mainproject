import Button from '@/components/ui/Button'
import { FolderOpen, Scale, Search, Shield, Sparkles, Upload } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../features/auth/index.js'

export default function LandingPage() {
  const { isAuthenticated, openAuthModal } = useAuth()
  const navigate = useNavigate()

  const handleUploadClick = () => {
    if (isAuthenticated) { navigate('/workspace'); return }
    openAuthModal('login')
  }

  const handleWorkspaceClick = () => {
    if (isAuthenticated) { navigate('/workspace'); return }
    openAuthModal('login')
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">

      {/* 히어로 */}
      <section className="flex flex-col items-center text-center gap-6 mb-16">
        <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
          <Scale className="w-8 h-8 text-blue-600" />
        </div>
        <h1 className="text-4xl font-bold">판례 AI 플랫폼</h1>
        <p className="text-muted-foreground text-lg leading-relaxed">
          AI 기술로 복잡한 법률 판례를 쉽게 이해하고,
          <br />
          유사 사례를 빠르게 검색할 수 있습니다
        </p>
        <div className="flex gap-3 flex-wrap justify-center">
          <Button onClick={handleUploadClick} className="gap-2">
            <Upload className="w-4 h-4" />
            판례 업로드하기
          </Button>
          <Button variant="outline" onClick={handleWorkspaceClick} className="gap-2">
            <FolderOpen className="w-4 h-4" />
            워크스페이스 보기
          </Button>
        </div>
      </section>

      {/* 기능 카드 */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
        <div className="p-6 border rounded-xl flex flex-col gap-2">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center mb-1">
            <Upload className="w-5 h-5 text-blue-600" />
          </div>
          <h4 className="font-semibold">간편한 업로드</h4>
          <p className="text-sm text-muted-foreground">PDF 파일을 드래그 앤 드롭하여 쉽게 업로드</p>
          <p className="text-sm text-muted-foreground/70">
            판례 문서를 선택하면 자동으로 텍스트를 추출하고 데이터베이스에 저장합니다.
          </p>
        </div>

        <div className="p-6 border rounded-xl flex flex-col gap-2">
          <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center mb-1">
            <Sparkles className="w-5 h-5 text-purple-600" />
          </div>
          <h4 className="font-semibold">AI 자동 요약</h4>
          <p className="text-sm text-muted-foreground">EXAONE이 핵심 내용을 자동으로 추출</p>
          <p className="text-sm text-muted-foreground/70">
            복잡한 법률 용어와 긴 판례 문서를 AI가 이해하기 쉽게 요약해드립니다.
          </p>
        </div>

        <div className="p-6 border rounded-xl flex flex-col gap-2">
          <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center mb-1">
            <Search className="w-5 h-5 text-green-600" />
          </div>
          <h4 className="font-semibold">RAG 검색</h4>
          <p className="text-sm text-muted-foreground">유사 판례를 즉시 찾아보세요</p>
          <p className="text-sm text-muted-foreground/70">
            ChromaDB 기반 벡터 검색으로 관련 판례를 빠르게 찾고 비교할 수 있습니다.
          </p>
        </div>
      </section>

      {/* 작동 방식 */}
      <section className="mb-16">
        <h2 className="text-2xl font-bold text-center mb-8">어떻게 작동하나요?</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { step: 1, title: '사례 입력',  desc: '챗봇에 법률 사례를 입력합니다' },
            { step: 2, title: '판례 검색',  desc: 'RAG로 관련 판례를 자동 검색합니다' },
            { step: 3, title: 'AI 해석',    desc: 'EXAONE이 판례를 해석하고 요약합니다' },
            { step: 4, title: '원본 확인',  desc: '판례 원본 링크로 직접 확인합니다' },
          ].map(({ step, title, desc }) => (
            <div key={step} className="flex flex-col items-center text-center gap-2">
              <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm">
                {step}
              </div>
              <h3 className="font-semibold text-sm">{title}</h3>
              <p className="text-xs text-muted-foreground">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 안내 */}
      <section className="p-6 bg-muted rounded-xl border">
        <h3 className="flex items-center gap-2 font-semibold mb-2">
          <Shield className="w-4 h-4 text-muted-foreground" />
          법률 자문 안내
        </h3>
        <p className="text-sm text-muted-foreground">
          본 시스템은 판례 정보를 제공하는 참고 도구입니다. 실제 법률 문제에 대해서는 반드시
          변호사 등 전문가와 상담하시기 바랍니다.
        </p>
      </section>
    </div>
  )
}