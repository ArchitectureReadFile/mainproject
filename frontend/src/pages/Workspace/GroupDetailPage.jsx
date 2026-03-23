import { getGroupDetail, requestDeleteGroup, cancelDeleteGroup, getMembers } from '@/api/groups'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import {
    AlertTriangle, FileText, Home, Loader2,
    Trash2, Undo2, Users, ArrowLeft,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import UploadPage from '@/pages/Upload/index'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/features/auth/index'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'


// 역할별 허용 탭
const TABS = [
    { key: 'upload', label: '업로드', roles: ['OWNER', 'ADMIN', 'EDITOR'], hideOnPending: true},
    { key: 'documents', label: '문서', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
    { key: 'trash', label: '휴지통', roles: ['OWNER', 'ADMIN', 'EDITOR'] },
    { key: 'members', label: '멤버', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'], hideOnPending: true },
    { key: 'workspace', label: '워크스페이스', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
]


// D-DAY 계산
function calcDday(isoDate) {
    if(!isoDate) return null
    const diff = Math.ceil((new Date(isoDate) - new Date()) / (1000 * 60 * 60 * 24))
    return diff <= 0 ? "D-0" : `D-${diff}`
}


// 삭제 예정 배너
function DeletePendingBanner({ scheduledAt }){
    const dday = calcDday(scheduledAt)
    return (
        <div className='mb-5 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm text-destructive'>
            <AlertTriangle className='h-4 w-4 shrink-0' />
            <span>
                해당 워크스페이스는 삭제예정입니다. 자료를 백업해주세요.{' '}  
                <span className='font-semibold'>
                    {dday}({new Date(scheduledAt).toLocaleDateString('ko-KR')} 삭제 예정)
                </span>
            </span>  
        </div>
    )
}


const ROLE_STYLE = {
    OWNER:  { label: 'OWNER',  variant: 'default' },
    ADMIN:  { label: 'ADMIN',  variant: 'secondary' },
    EDITOR: { label: 'EDITOR', variant: 'outline' },
    VIEWER: { label: 'VIEWER', variant: 'outline' },
}


function RoleBadge({ role }) {
    const { label, variant } = ROLE_STYLE[role] ?? { label: role, variant: 'outline' }
    return <Badge variant={variant}>{label}</Badge>
}


function MembersTab({ group }) {
    const { user } = useAuth()

    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [search, setSearch] = useState('')
    const [query, setQuery] = useState('') 

    const rolePriority = {
    OWNER: 1,
    ADMIN: 2,
    EDITOR: 3,
    VIEWER: 4
    }
    

    useEffect(() => {
        setLoading(true)
        getMembers(group.id)
            .then(setData)
            .catch((e) => setError(e.message ?? "멤버 목록을 불러오지 못했습니다."))
            .finally(() => setLoading(false))
    }, [group.id])

    if (loading) return (
        <div className="flex justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground"/>
        </div>
    )

    if (error) return (
        <div className="py-20 text-center text-sm text-destructive">{error}</div>
    )

    const { members = [], invited = [] } = data
    const handleSearch = () => setQuery(search.trim().toLowerCase())

    const sortedMembers = [...members].sort((a, b) => {
        if (a.user_id === user?.id) return -1
        if (b.user_id === user?.id) return 1
        return rolePriority[a.role] - rolePriority[b.role]
    })

    const filteredMembers = query
        ? sortedMembers.filter((m) => m.username.toLowerCase().includes(query))
        : sortedMembers
    const filteredInvited = query
        ? invited.filter((m) => m.username.toLowerCase().includes(query))
        : invited

    const canSeeInvited = group.my_role === 'OWNER' || group.my_role === 'ADMIN'

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {/* 검색 */}
            <div className="flex gap-2">
                <input
                    type="text"
                    placeholder="유저명으로 검색"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <button
                    onClick={handleSearch}
                    className="rounded-md border px-4 py-2 text-sm hover:bg-muted transition-colors"
                >
                검색
                </button>
            </div>

            {/* ACTIVE 멤버 */}
            <div className="rounded-lg border">
                <div className="px-5 py-4 border-b">
                    <h3 className="font-semibold">
                        멤버{' '}
                        <span className="text-muted-foreground font-normal text-sm">
                            {filteredMembers.length}명
                        </span>
                    </h3>
                </div>
                {filteredMembers.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-muted-foreground text-center">검색 결과가 없습니다.</p>
                ) : (
                    <ul>
                        {filteredMembers.map((m) => (
                            <li key={m.user_id} className="flex items-center justify-between px-5 py-3">
                                <div>
                                    <p className="text-sm font-medium">
                                        {m.username}
                                        {m.user_id === user?.id && (
                                            <span className="ml-1.5 text-xs text-muted-foreground font-normal">(나)</span>
                                        )}
                                    </p>
                                    <p className="text-xs text-muted-foreground">{m.email}</p>
                                </div>
                                <RoleBadge role={m.role} />
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {/* INVITED 멤버 */}
            {(canSeeInvited && (invited.length > 0 || filteredInvited.length > 0)) && (
                <div className="rounded-lg border">
                    <div className="px-5 py-4 border-b">
                        <h3 className="font-semibold">
                            초대 대기 중{' '}
                            <span className="text-muted-foreground font-normal text-sm">
                                {filteredInvited.length}명
                            </span>
                        </h3>
                    </div>
                    {filteredInvited.length === 0 ? (
                        <p className="px-5 py-6 text-sm text-muted-foreground text-center">검색 결과가 없습니다.</p>
                    ) : (
                        <ul className="divide-y">
                            {filteredInvited.map((m) => (
                                <li key={m.user_id} className="flex items-center justify-between px-5 py-3">
                                    <div>
                                        <p className="text-sm font-medium">{m.username}</p>
                                        <p className="text-xs text-muted-foreground">
                                            초대일: {new Date(m.invited_at).toLocaleDateString('ko-KR')}
                                        </p>
                                    </div>
                                    <RoleBadge role={m.role} />
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )

}


// 워크 스페이스 탭
function WorkspaceTab({ group, onUpdated }){
    // 권한 체크 오너 어드민이면 이름 변경, 그룹 상세 정보, 전체 다운, 그룹 삭제
    // 에디터, 뷰어면 그룹 상세정보만
    const isOwner = group.my_role === "OWNER"
    const isAdmin = group.my_role === "ADMIN"
    const isPending = group.status === "DELETE_PENDING"

    const canDelete = isOwner
    const canRename = isOwner || isAdmin
    const canDownload = isOwner || isAdmin

    const [confirmType, setConfirmType] = useState(null)
    const [loading, setLoading] = useState(false)

    const handleConfirm = async () => {
        setLoading(true)
        try {
            const updated = confirmType === "delete"
                ? await requestDeleteGroup(group.id)
                : await cancelDeleteGroup(group.id)
            onUpdated(updated)
            toast.success(confirmType === "delete" ? "삭제 요청이 완료됐습니다." : "삭제가 취소됐습니다.")
        } catch (e) {
            toast.error(e.message || "처리에 실패했습니다.")
        } finally {
            setLoading(false)
            setConfirmType(null)
        }
    }

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            
            {/* 그룹 상세 정보 — 전체 공개 */}
            <div className="rounded-lg border p-5 space-y-3">
                <h3 className="text-base font-semibold">그룹 상세 정보</h3>
                <div className="space-y-2 text-base">
                    <div className="flex items-center">
                        <span className="text-muted-foreground w-24 shrink-0">이름</span> 
                        <span className="font-medium text-slate-900">{group.name}</span>
                    </div>
                    <div className="flex items-start">
                        <span className="text-muted-foreground w-24 shrink-0">설명</span>
                        <span className="font-medium text-foreground break-all whitespace-pre-wrap">{group.description || '—'}</span>
                    </div>
                    <div className="flex items-center">
                        <span className="text-muted-foreground w-24 shrink-0 pt-0.5">소유자</span>
                        <span className="font-medium text-slate-900">{group.owner_username}</span>
                    </div>
                    <div className="flex items-center">
                        <span className="text-muted-foreground w-24 shrink-0">멤버</span>
                        <span className="font-medium text-slate-900">{group.member_count}명</span>
                    </div>
                    <div className="flex items-center">
                        <span className="text-muted-foreground w-24 shrink-0">문서</span>
                        <span className="font-medium text-slate-900">{group.document_count}개</span>
                    </div>
                    <div className="flex items-center">
                        <span className="text-muted-foreground w-24 shrink-0 pb-3">생성일</span>
                        <span className="font-medium text-slate-900">
                            {new Date(group.created_at).toLocaleDateString('ko-KR')}
                        </span>
                    </div>
                    <div className="flex items-center border-t pt-3">
                        <span className="text-muted-foreground w-24 shrink-0">상태</span>
                        <span className={`font-medium ${isPending ? 'text-destructive' : 'text-green-600'}`}>
                            {isPending
                                ? `삭제 예정 (${calcDday(group.delete_scheduled_at)})`
                                : '정상'}
                        </span>
                    </div>
                </div>
            </div>

            {/* 그룹 삭제 — OWNER */}
            {canDelete && (
                <div className="rounded-lg border border-destructive/30 p-5 space-y-3">
                    <h3 className="text-base font-semibold text-destructive">워크스페이스 삭제</h3>
                    <p className="text-base text-muted-foreground">
                        {!isPending
                            ? '삭제 요청 후 30일이 지나면 워크스페이스가 영구 삭제됩니다.'
                            : `${new Date(group.delete_scheduled_at).toLocaleDateString('ko-KR')}에 해당 워크스페이스가 영구 삭제됩니다. 취소할 수 있습니다.`
                        }
                    </p>
                    {!isPending ? (
                        <button
                            onClick={() => setConfirmType('delete')}
                            className="flex items-center gap-2 rounded-md border border-destructive px-3 py-1.5 text-sm text-destructive hover:bg-destructive/5 transition-colors"
                        >
                            <Trash2 className="h-4 w-4" />
                            워크스페이스 삭제 요청
                        </button>
                    ) : (
                        <button
                            onClick={() => setConfirmType('cancel')}
                            className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                        >
                            <Undo2 className="h-4 w-4" />
                            삭제 취소
                        </button>
                    )}
                </div>
            )}

            <ConfirmModal
                open={confirmType === 'delete'}
                message="워크스페이스를 삭제 요청합니다. 30일 후 영구 삭제되며, 그 전까지 취소할 수 있습니다."
                confirmLabel={loading ? '처리 중...' : '삭제 요청'}
                onConfirm={handleConfirm}
                onCancel={() => setConfirmType(null)}
            />
            <ConfirmModal
                open={confirmType === 'cancel'}
                message="삭제 요청을 취소하고 워크스페이스를 복구합니다."
                confirmLabel={loading ? '처리 중...' : '삭제 취소'}
                onConfirm={handleConfirm}
                onCancel={() => setConfirmType(null)}
            />

        </div>

    )

}


export default function GroupDetailPage() {
    const { group_id } = useParams()
    const [group, setGroup] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeTab, setActiveTab] = useState('documents')
    const navigate = useNavigate()

    useEffect(() => {
        setLoading(true)
        getGroupDetail(group_id)
        .then(setGroup)
        .catch((e) => setError(e.message ?? '불러오기에 실패했습니다.'))
        .finally(() => setLoading(false))
    }, [group_id])

    const visibleTabs = group
        ? TABS.filter((t) => 
            t.roles.includes(group.my_role) &&
            ! (t.hideOnPending && group.status === "DELETE_PENDING")
        )
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

        {/* 삭제 예정 배너 */}
        {group.status == "DELETE_PENDING" && (
            <DeletePendingBanner scheduledAt={group.delete_scheduled_at} />
        )}

        {/* 헤더 */}
        <div className="mb-6">
            {/* 뒤로가기 버튼 */}
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="gap-1.5 mb-3 -ml-2">
                <ArrowLeft size={15} />
                뒤로 가기
            </Button>
            <div className="flex items-center gap-2">
                <Home className="h-8 w-8 "/>
                <h1 className="text-2xl font-bold">{group.name}</h1>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 border border-blue-200">
                    {group.my_role}
                </span>
            </div>
            <div className="flex items-center gap-4 mt-3 text-sm">

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
                className={`px-4 py-2 text-sm font-medium text-slate-900 border-b-2 transition-colors ${
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
        {activeTab === 'documents' && <div>문서 섹션</div>}
        {activeTab === 'trash'     && <div>휴지통 섹션</div>}
        {activeTab === 'members'   && (
            <MembersTab group={group}/>
        )}
        {activeTab === "workspace" && (
            <WorkspaceTab group={group} onUpdated={(updated) => setGroup(updated)} />
        )}
        </div>
    )
}