import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  BarChart3,
  Database,
  Gauge,
  RefreshCw,
  Search,
  Shield,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useAuth } from '../../features/auth/index.js'

const TABS = [
  { key: 'overview', label: '개요', Icon: BarChart3 },
  { key: 'usage', label: '사용량', Icon: Gauge },
  { key: 'db', label: 'RAG DB 관리', Icon: Database },
  { key: 'members', label: '회원 관리', Icon: Users },
]

const OVERVIEW_STATS = [
  { label: '전체 회원', value: '1,284', hint: '+23 이번 주' },
  { label: 'PREMIUM 전환율', value: '18.4%', hint: '236명 프리미엄', accent: 'text-primary' },
  { label: '활성 워크스페이스', value: '142', hint: '삭제 예정 3개' },
  { label: 'AI 처리 성공률', value: '97.2%', hint: '이번 달 기준', accent: 'text-success' },
]

const STORAGE_USAGE = {
  used: 84.3,
  limit: 200,
  percent: 42,
}

const SERVICE_USAGE = {
  documentJobs: {
    used: 1847,
    limit: 3000,
    percent: 62,
  },
  breakdown: [
    { label: '완료', percent: 92, className: 'bg-success' },
    { label: '처리 중', percent: 5, className: 'bg-warning' },
    { label: '실패', percent: 3, className: 'bg-destructive' },
  ],
}

const RAG_USAGE = {
  precedentCount: '24,381',
  vectorStorageMb: '12,840',
  indexBreakdown: {
    done: '24,195',
    pending: '186',
    failed: '54',
  },
  vectorPercent: 58,
  vectorLimitLabel: '22,000 MB',
}

const RAG_DAILY_INGESTS = [
  { label: '월', percent: 55 },
  { label: '화', percent: 74 },
  { label: '수', percent: 48 },
  { label: '목', percent: 82 },
  { label: '금', percent: 63 },
  { label: '토', percent: 20 },
  { label: '일', percent: 16 },
]

const DAILY_UPLOADS = [
  { label: '월', percent: 40 },
  { label: '화', percent: 65 },
  { label: '수', percent: 50 },
  { label: '목', percent: 90 },
  { label: '금', percent: 55 },
  { label: '토', percent: 30 },
  { label: '일', percent: 20 },
]

const DB_METRICS = [
  { label: '등록 판례', value: '24,381' },
  { label: '인덱싱 완료', value: '24,195', accent: 'text-success' },
  { label: '인덱싱 대기', value: '186', accent: 'text-warning' },
]

const DB_PANELS = [
  {
    id: 'failed',
    title: '인덱싱 실패 항목',
    description: '벡터화 또는 메타 추출 과정에서 실패한 판례 목록',
    countLabel: '54건',
    countClassName: 'text-destructive',
    columns: ['제목', '등록일', '상태', '오류'],
    rows: [
      ['대법원 2023다12345', '2026-03-14', 'FAILED', '본문 추출 실패'],
      ['서울고법 2024나4031', '2026-03-13', 'FAILED', '벡터 저장 실패'],
      ['형사판례 2021도9982', '2026-03-12', 'FAILED', '지원되지 않는 원문 형식'],
    ],
  },
  {
    id: 'pending',
    title: '인덱싱 대기 항목',
    description: '아직 벡터화가 시작되지 않았거나 큐에서 대기 중인 판례',
    countLabel: '186건',
    countClassName: 'text-warning',
    columns: ['제목', '등록일', '대기 시간'],
    rows: [
      ['대법원 2026다00123', '2026-03-16', '2시간'],
      ['계약분쟁 판례 모음', '2026-03-16', '1시간'],
      ['공정거래법 해설서', '2026-03-16', '30분'],
    ],
  },
  {
    id: 'court',
    title: '법원별 등록 판례 수',
    description: '관리 중인 판례 데이터를 법원 기준으로 집계',
    countLabel: '4개 법원',
    countClassName: 'text-muted-foreground',
    columns: ['법원명', '판례 수', '비율'],
    rows: [
      ['대법원', '9,241', '37.9%'],
      ['서울고등법원', '4,812', '19.7%'],
      ['서울중앙지방법원', '3,609', '14.8%'],
      ['부산고등법원', '2,104', '8.6%'],
    ],
  },
  {
    id: 'recent',
    title: '최근 등록 판례',
    description: '가장 최근 등록된 RAG용 판례 메타 10건',
    countLabel: '최근 10건',
    countClassName: 'text-muted-foreground',
    columns: ['제목', '등록일', '상태'],
    rows: [
      ['대법원 2026다00123', '2026-03-16 10:11', 'DONE'],
      ['계약분쟁사례', '2026-03-16 09:55', 'PROCESSING'],
      ['노동법 해석서', '2026-03-16 09:32', 'DONE'],
    ],
  },
]

const MEMBER_ROWS = [
  {
    id: 1,
    username: '김대표',
    email: 'daeyo@abclaw.kr',
    plan: 'PREMIUM',
    activeGroupCount: 1,
    createdAt: '2024-01-12',
  },
  {
    id: 2,
    username: '이변호사',
    email: 'lee@xyzlaw.kr',
    plan: 'PREMIUM',
    activeGroupCount: 2,
    createdAt: '2024-02-03',
  },
  {
    id: 3,
    username: '박직원',
    email: 'park@abclaw.kr',
    plan: 'FREE',
    activeGroupCount: 1,
    createdAt: '2024-03-21',
  },
  {
    id: 4,
    username: '최실무',
    email: 'choi@defcorp.kr',
    plan: 'FREE',
    activeGroupCount: 0,
    createdAt: '2024-04-08',
  },
]

function SectionHeader({ title, description, actions = null }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </div>
  )
}

function MetricCard({ label, value, hint, accent = '' }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`mt-2 text-3xl font-semibold tracking-tight ${accent}`}>{value}</p>
        <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  )
}

function ProgressBar({ percent, className }) {
  return (
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary">
      <div className={`h-full rounded-full ${className}`} style={{ width: `${percent}%` }} />
    </div>
  )
}

function SearchField({ value, onChange, placeholder }) {
  return (
    <div className="relative w-full max-w-sm">
      <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="pl-9"
      />
    </div>
  )
}

function StatusBadge({ status }) {
  const meta = {
    DONE: { label: '완료', variant: 'success' },
    PROCESSING: { label: '처리 중', variant: 'warning' },
    FAILED: { label: '실패', variant: 'destructive' },
    PENDING: { label: '대기', variant: 'secondary' },
  }[status] ?? { label: status, variant: 'outline' }

  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

function PlanBadge({ plan }) {
  return <Badge variant={plan === 'PREMIUM' ? 'default' : 'outline'}>{plan}</Badge>
}

function OverviewTab() {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="관리자 대시보드"
        description="플랫폼 운영 지표를 한눈에 보고, RAG/회원 상태를 빠르게 파악할 수 있는 개요 화면입니다."
        actions={<div className="text-xs text-muted-foreground">2026년 3월 16일 기준</div>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {OVERVIEW_STATS.map((item) => (
          <MetricCard key={item.label} {...item} />
        ))}
      </div>
    </div>
  )
}

function UsageTab() {
  return (
    <div className="space-y-6">
      <SectionHeader
        title="사용량"
        description="서비스 사용량과 RAG 사용량을 분리해서 보고, 확장 필요 여부를 판단합니다."
      />

      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold">서비스 사용량</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            고객 워크스페이스가 사용하는 저장소와 문서 처리량을 모니터링합니다.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">업로드 용량 추이</CardTitle>
              <CardDescription>최근 7일 업로드 볼륨</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">
                {STORAGE_USAGE.used} GB{' '}
                <span className="text-sm font-normal text-muted-foreground">/ {STORAGE_USAGE.limit} GB</span>
              </p>
              <ProgressBar percent={STORAGE_USAGE.percent} className="bg-primary" />
              <div className="mt-5 flex h-24 items-end gap-2">
                {DAILY_UPLOADS.map((item) => (
                  <div key={item.label} className="flex flex-1 flex-col items-center gap-2">
                    <div className="flex h-full w-full items-end">
                      <div
                        className="w-full rounded-t-sm bg-primary/45"
                        style={{ height: `${item.percent}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{item.label}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">문서 처리량</CardTitle>
              <CardDescription>워크스페이스 문서 처리 상태 분포</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-2xl font-semibold">
                {SERVICE_USAGE.documentJobs.used}건{' '}
                <span className="text-sm font-normal text-muted-foreground">/ {SERVICE_USAGE.documentJobs.limit}건</span>
              </p>
              <ProgressBar percent={SERVICE_USAGE.documentJobs.percent} className="bg-success" />
              {SERVICE_USAGE.breakdown.map((item) => (
                <div key={item.label}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span>{item.percent}%</span>
                  </div>
                  <ProgressBar percent={item.percent} className={item.className} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold">RAG 사용량</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            판례 메타 등록량, 인덱싱 상태, 벡터 저장량을 기준으로 확장 필요 여부를 판단합니다.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">RAG 인덱싱 볼륨</CardTitle>
              <CardDescription>최근 7일 판례 등록 및 인덱싱 추이</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">등록 판례 수</p>
                  <p className="mt-2 text-2xl font-semibold">{RAG_USAGE.precedentCount}</p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">인덱싱 완료</p>
                  <p className="mt-2 text-2xl font-semibold text-success">{RAG_USAGE.indexBreakdown.done}</p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">인덱싱 대기</p>
                  <p className="mt-2 text-2xl font-semibold text-warning">{RAG_USAGE.indexBreakdown.pending}</p>
                </div>
              </div>
              <div className="mt-5 flex h-24 items-end gap-2">
                {RAG_DAILY_INGESTS.map((item) => (
                  <div key={item.label} className="flex flex-1 flex-col items-center gap-2">
                    <div className="flex h-full w-full items-end">
                      <div
                        className="w-full rounded-t-sm bg-success/50"
                        style={{ height: `${item.percent}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{item.label}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">벡터 저장량</CardTitle>
              <CardDescription>ChromaDB 저장량과 인덱싱 실패 비율</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-2xl font-semibold">
                {RAG_USAGE.vectorStorageMb} MB{' '}
                <span className="text-sm font-normal text-muted-foreground">/ {RAG_USAGE.vectorLimitLabel}</span>
              </p>
              <ProgressBar percent={RAG_USAGE.vectorPercent} className="bg-primary" />
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">성공</p>
                  <p className="mt-2 text-xl font-semibold text-success">{RAG_USAGE.indexBreakdown.done}</p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">대기</p>
                  <p className="mt-2 text-xl font-semibold text-warning">{RAG_USAGE.indexBreakdown.pending}</p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="text-xs text-muted-foreground">실패</p>
                  <p className="mt-2 text-xl font-semibold text-destructive">{RAG_USAGE.indexBreakdown.failed}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function DbPanel({ title, description, countLabel, countClassName, columns, rows }) {
  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
          <span className={`text-sm font-medium ${countClassName}`}>{countLabel}</span>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="border-b text-left text-xs text-muted-foreground">
            <tr>
              {columns.map((column) => (
                <th key={column} className="px-2 py-2 font-medium">{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${title}-${index}`} className="border-b last:border-0">
                {row.map((cell, cellIndex) => (
                  <td key={`${title}-${index}-${cellIndex}`} className="px-2 py-3 text-sm">
                    {cellIndex === row.length - 1 && ['DONE', 'PROCESSING', 'FAILED', 'PENDING'].includes(cell)
                      ? <StatusBadge status={cell} />
                      : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function DbTab() {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="RAG DB 관리"
        description="URL 기반으로 등록된 판례 메타와 인덱싱 상태를 운영합니다."
        actions={(
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">판례 URL 추가</Button>
            <Button variant="outline" size="sm">
              <RefreshCw size={14} />
              인덱스 재생성
            </Button>
          </div>
        )}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {DB_METRICS.map((item) => (
          <MetricCard key={item.label} {...item} hint="" />
        ))}
      </div>

      <div className="space-y-4">
        {DB_PANELS.map((panel) => (
          <DbPanel key={panel.id} {...panel} />
        ))}
      </div>
    </div>
  )
}

function MembersTab() {
  const [query, setQuery] = useState('')
  const [planFilter, setPlanFilter] = useState('ALL')

  const filteredMembers = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return MEMBER_ROWS.filter((member) => {
      const matchesQuery = !keyword || [member.username, member.email].some((value) =>
        value.toLowerCase().includes(keyword)
      )
      const matchesPlan = planFilter === 'ALL' || member.plan === planFilter
      return matchesQuery && matchesPlan
    })
  }, [planFilter, query])

  return (
    <div className="space-y-4">
      <SectionHeader
        title="회원 관리"
        description="회원과 구독 상태를 조회하고 운영 액션을 연결할 수 있는 영역입니다."
      />

      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-col gap-3 sm:flex-row">
            <SearchField value={query} onChange={setQuery} placeholder="이름 또는 이메일 검색" />
            <select
              value={planFilter}
              onChange={(event) => setPlanFilter(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="ALL">전체</option>
              <option value="PREMIUM">PREMIUM</option>
              <option value="FREE">FREE</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead className="border-b text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-2 py-2 font-medium">이름</th>
                  <th className="px-2 py-2 font-medium">이메일</th>
                  <th className="px-2 py-2 font-medium">플랜</th>
                  <th className="px-2 py-2 font-medium">활성 워크스페이스</th>
                  <th className="px-2 py-2 font-medium">가입일</th>
                  <th className="px-2 py-2 font-medium text-right">작업</th>
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((member) => (
                  <tr key={member.id} className="border-b last:border-0">
                    <td className="px-2 py-3 font-medium">{member.username}</td>
                    <td className="px-2 py-3 text-muted-foreground">{member.email}</td>
                    <td className="px-2 py-3"><PlanBadge plan={member.plan} /></td>
                    <td className="px-2 py-3 text-muted-foreground">{member.activeGroupCount}개</td>
                    <td className="px-2 py-3 text-muted-foreground">{member.createdAt}</td>
                    <td className="px-2 py-3 text-right">
                      <Button variant="outline" size="sm">관리</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-right text-xs text-muted-foreground">총 1,284명</p>
        </CardContent>
      </Card>
    </div>
  )
}

export default function AdminPage() {
  const { user } = useAuth()

  if (user?.role !== 'ADMIN') {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-muted-foreground">
        <Shield size={48} />
        <p>접근 권한이 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-primary/10 p-3 text-primary">
            <Shield size={28} />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">관리자 대시보드</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              플랫폼 운영 지표, RAG 판례 데이터베이스, 회원 상태를 관리합니다.
            </p>
          </div>
        </div>
        <Badge variant="outline">ADMIN ONLY</Badge>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto rounded-xl p-1">
          {TABS.map(({ key, label, Icon }) => (
            <TabsTrigger key={key} value={key} className="gap-2">
              <Icon size={15} />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview"><OverviewTab /></TabsContent>
        <TabsContent value="usage"><UsageTab /></TabsContent>
        <TabsContent value="db"><DbTab /></TabsContent>
        <TabsContent value="members"><MembersTab /></TabsContent>
      </Tabs>
    </div>
  )
}
