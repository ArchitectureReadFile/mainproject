import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import { BarChart3, CheckCircle, FileText, Search, Settings, Shield, Trash2, Users, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../../features/auth/index.js'

const TABS = [
  { key: 'dashboard', label: '대시보드',   Icon: BarChart3 },
  { key: 'users',     label: '사용자 관리', Icon: Users },
  { key: 'cases',     label: '판례 관리',   Icon: FileText },
  { key: 'settings',  label: '시스템 설정', Icon: Settings },
]

function SectionHeader({ title, sub }) {
  return (
    <div className="mb-4">
      <h3 className="text-base font-semibold">{title}</h3>
      {sub && <p className="text-sm text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="relative mb-4">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="pl-8"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function EmptyRow({ colSpan }) {
  return (
    <tr>
      <td colSpan={colSpan} className="text-center py-8 text-sm text-muted-foreground">데이터가 없습니다.</td>
    </tr>
  )
}

function DashboardTab() {
  const STAT_CARDS = [
    { label: '총 사용자',   sub: '활성 사용자' },
    { label: '총 판례',     sub: '전체 판례 데이터' },
    { label: '오늘 업로드', sub: '신규 판례 업로드' },
    { label: '활성 사용자', sub: '전체 대비 비율' },
  ]
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STAT_CARDS.map(({ label, sub }) => (
          <Card key={label} className="p-4">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold my-1">—</p>
            <p className="text-xs text-muted-foreground">{sub}</p>
          </Card>
        ))}
      </div>
      <Card className="p-4">
        <SectionHeader title="최근 활동" />
        <p className="text-sm text-muted-foreground">API 연동 후 표시됩니다.</p>
      </Card>
    </div>
  )
}

function UsersTab() {
  const [search, setSearch] = useState('')
  const users = []
  const filtered = users.filter(({ name, email }) =>
    name.toLowerCase().includes(search.toLowerCase()) ||
    email.toLowerCase().includes(search.toLowerCase())
  )
  return (
    <Card className="p-4">
      <SectionHeader title="사용자 관리" sub="등록된 모든 사용자를 관리합니다" />
      <SearchInput value={search} onChange={setSearch} placeholder="이름 또는 이메일로 검색..." />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4">사용자</th>
              <th className="pb-2 pr-4">역할</th>
              <th className="pb-2 pr-4">상태</th>
              <th className="pb-2 pr-4">가입일</th>
              <th className="pb-2 pr-4">업로드 수</th>
              <th className="pb-2">작업</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? <EmptyRow colSpan={6} /> : filtered.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium">{u.name[0]}</span>
                    <div>
                      <p className="font-medium">{u.name}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <Badge variant={u.role === 'ADMIN' ? 'default' : 'secondary'}>
                    {u.role === 'ADMIN' ? '관리자' : '일반'}
                  </Badge>
                </td>
                <td className="py-3 pr-4">
                  <Badge variant={u.status === 'active' ? 'success' : 'destructive'}>
                    {u.status === 'active' ? '활성' : '비활성'}
                  </Badge>
                </td>
                <td className="py-3 pr-4 text-muted-foreground">{u.joinDate}</td>
                <td className="py-3 pr-4 text-muted-foreground">{u.uploadCount}건</td>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">{u.status === 'active' ? '비활성화' : '활성화'}</Button>
                    <Button variant="destructive" size="icon" className="h-8 w-8"><Trash2 size={14} /></Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function CasesTab() {
  const [search, setSearch] = useState('')
  const cases = []
  const CASE_STATUS_META = {
    approved: { label: '승인됨', variant: 'success' },
    pending:  { label: '대기중', variant: 'warning' },
    rejected: { label: '거부됨', variant: 'destructive' },
  }
  const filtered = cases.filter(({ title }) => title.toLowerCase().includes(search.toLowerCase()))
  return (
    <Card className="p-4">
      <SectionHeader title="판례 관리" sub="업로드된 모든 판례를 관리합니다" />
      <SearchInput value={search} onChange={setSearch} placeholder="판례 제목으로 검색..." />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4">제목</th>
              <th className="pb-2 pr-4">업로더</th>
              <th className="pb-2 pr-4">업로드일</th>
              <th className="pb-2 pr-4">상태</th>
              <th className="pb-2 pr-4">조회수</th>
              <th className="pb-2">작업</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? <EmptyRow colSpan={6} /> : filtered.map((c) => {
              const meta = CASE_STATUS_META[c.status] ?? { label: c.status, variant: 'secondary' }
              return (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-medium">{c.title}</td>
                  <td className="py-3 pr-4 text-muted-foreground">{c.uploader}</td>
                  <td className="py-3 pr-4 text-muted-foreground">{c.uploadDate}</td>
                  <td className="py-3 pr-4"><Badge variant={meta.variant}>{meta.label}</Badge></td>
                  <td className="py-3 pr-4 text-muted-foreground">{c.views}회</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      {c.status === 'pending' && (
                        <>
                          <Button variant="outline" size="icon" className="h-8 w-8"><CheckCircle size={14} /></Button>
                          <Button variant="outline" size="icon" className="h-8 w-8"><XCircle size={14} /></Button>
                        </>
                      )}
                      <Button variant="destructive" size="icon" className="h-8 w-8"><Trash2 size={14} /></Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function SettingsTab() {
  const SETTINGS_GROUPS = [
    { title: 'AI 설정',      items: ['EXAONE 모델 설정', 'ChromaDB 연결 설정', '요약 파라미터 조정'] },
    { title: '데이터베이스', items: ['MariaDB 연결 상태', '데이터 백업', '데이터 정리'] },
    { title: '시스템',       items: ['로그 확인', '캐시 관리'], danger: ['시스템 초기화'] },
  ]
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {SETTINGS_GROUPS.map(({ title, items, danger }) => (
        <Card key={title} className="p-4">
          <SectionHeader title={title} />
          <div className="flex flex-col gap-2">
            {items.map((label) => <Button key={label} variant="outline" className="w-full">{label}</Button>)}
            {danger?.map((label) => <Button key={label} variant="destructive" className="w-full">{label}</Button>)}
          </div>
        </Card>
      ))}
    </div>
  )
}

const TAB_CONTENT = { dashboard: DashboardTab, users: UsersTab, cases: CasesTab, settings: SettingsTab }

export default function AdminPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState('dashboard')

  if (user?.role !== 'ADMIN') {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
        <Shield size={48} />
        <p>접근 권한이 없습니다.</p>
      </div>
    )
  }

  const TabContent = TAB_CONTENT[tab]

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div className="flex items-center gap-3 mb-8">
        <Shield size={28} className="text-primary" />
        <div>
          <h1 className="text-2xl font-bold">관리자 페이지</h1>
          <p className="text-sm text-muted-foreground">시스템 전체를 관리하고 모니터링합니다</p>
        </div>
      </div>

      <div className="flex gap-2 mb-6 border-b pb-2">
        {TABS.map(({ key, label, Icon }) => (
          <Button
            key={key}
            variant={tab === key ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab(key)}
            className="gap-1.5"
          >
            <Icon size={15} />{label}
          </Button>
        ))}
      </div>

      <TabContent />
    </div>
  )
}