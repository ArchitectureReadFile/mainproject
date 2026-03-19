import { getGroupDetail } from '@/api/groups'
import { Loader2, Home, Users, FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import UploadPage from '@/pages/Upload/index'

// 역할별 허용 탭
const TABS = [
    { key: 'upload',    label: '업로드',    roles: ['OWNER', 'ADMIN', 'EDITOR'] },
    { key: 'documents', label: '문서 목록', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
    { key: 'trash',     label: '휴지통',    roles: ['OWNER', 'ADMIN', 'EDITOR'] },
    { key: 'members',   label: '멤버 관리', roles: ['OWNER', 'ADMIN'] },
]

export default function GroupDetailPage() {
    const { group_id } = useParams()
    const [group, setGroup] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeTab, setActiveTab] = useState('documents')

    useEffect(() => {
        setLoading(true)
        getGroupDetail(group_id)
        .then(setGroup)
        .catch((e) => setError(e.message ?? '불러오기에 실패했습니다.'))
        .finally(() => setLoading(false))
    }, [group_id])

    const visibleTabs = group
        ? TABS.filter((t) => t.roles.includes(group.my_role))
        : []

    useEffect(() => {
        if (visibleTabs.length && !visibleTabs.find((t) => t.key === activeTab)) {
        setActiveTab(visibleTabs[0].key)
        }
    }, [visibleTabs, activeTab])

    if (loading) return (
        <div className="flex justify-center py-28">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
    )
    if (error) return (
        <div className="py-28 text-center text-sm text-destructive">{error}</div>
    )

    return (
        <div className="p-6 max-w-5xl mx-auto">
        {/* 헤더 */}
        <div className="mb-6">
            <div className="flex items-center gap-2">
                <Home className="h-8 w-8 "/>
                <h1 className="text-2xl font-bold">{group.name}</h1>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 border border-blue-200">
                    {group.my_role}
                </span>
            </div>
            <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">

                <div className="flex items-center gap-1">
                    <Users className="h-4 w-4" /> 
                    <span>멤버 {group.member_count}명</span>
                </div>

                <div className="h-3 w-px bg-border" /> 

                <div className="flex items-center gap-1">
                    <FileText className="h-4 w-4" /> 
                    <span>문서 {group.document_count}개</span>
                </div>
            </div>
        </div>

        {/* 탭 */}
        <div className="flex gap-2 border-b mb-6">
            {visibleTabs.map((tab) => (
            <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
            >
                {tab.label}
            </button>
            ))}
        </div>

        {/* 컨텐츠 — 추가 예정 */}
        {activeTab === 'upload' && <UploadPage />}
        {activeTab === 'documents' && <div>문서 목록 섹션</div>}
        {activeTab === 'trash'     && <div>휴지통 섹션</div>}
        {activeTab === 'members'   && <div>멤버 관리 섹션</div>}
        </div>
    )
}