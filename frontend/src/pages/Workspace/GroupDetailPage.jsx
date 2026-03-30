import { 
    getGroupDetail, requestDeleteGroup, cancelDeleteGroup, getMembers, inviteMember, 
    removeMember, changeMemberRole, transferOwner,
} from '@/api/groups'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import {
    AlertTriangle, FileText, Home, Loader2,
    Trash2, Undo2, Users, ArrowLeft, 
} from 'lucide-react'
import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import UploadPage from '@/pages/Upload/index'
import DocumentsTab from '@/pages/Workspace/DocumentsTab'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/features/auth/index'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip'
import { UploadProvider } from '@/features/upload/context/UploadContext'
import ApprovalsTab from '@/pages/Workspace/ApprovalsTab'


// 역할별 허용 탭
const TABS = [
    { key: 'upload', label: '업로드', roles: ['OWNER', 'ADMIN', 'EDITOR'], hideOnPending: true },
    { key: 'documents', label: '문서', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
    { key: 'approvals', label: '승인', roles: ['OWNER', 'ADMIN'] },
    { key: 'trash', label: '휴지통', roles: ['OWNER', 'ADMIN', 'EDITOR'] },
    { key: 'members', label: '멤버', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'], hideOnPending: true },
    { key: 'workspace', label: '워크스페이스', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
]


const GROUP_POLLING_INTERVAL = 5000


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
    return <Badge 
        variant={variant}
        className={"rounded-sm font-semibold justify-center w-15"}
        >
            {label}
        </Badge>
}


function MembersTab({ group, setGroup }) {
    const { user } = useAuth()

    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [search, setSearch] = useState('')
    const [query, setQuery] = useState('') 
    const [inviteUsername, setInviteUsername] = useState('')
    const [inviteRole, setInviteRole] = useState('EDITOR')
    const [inviteLoading, setInviteLoading] = useState(false)
    const [inviteError, setInviteError] = useState('')
    const [confirmRemove, setConfirmRemove] = useState(null)  
    const [actionLoading, setActionLoading] = useState(null)  
    const [confirmInvite, setConfirmInvite] = useState(false)
    const [confirmTransfer, setConfirmTransfer] = useState(null)


    const handleInvite = async () => {
        if(!inviteUsername.trim()) return
        setInviteLoading(true)
        setInviteError('')
        try {
            const newMember = await inviteMember(group.id, {
                username: inviteUsername.trim(),
                role: inviteRole,
            })
            setData((prev) => ({
                ...prev,
                invited: [...prev.invited, newMember],
            }))
            setInviteUsername('')
            setInviteRole("EDITOR")
            toast.success("초대에 성공했습니다.")
        } catch (e) {
            setInviteError(e.message || "초대에 실패했습니다.")
        } finally {
            setInviteLoading(false)
        }
    }

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

    const canRolechange = (m) => {
        if (!canSeeInvited) return false
        if (m.user_id === user?.id) return false
        if (m.role === "OWNER") return false
        if (group.my_role === "ADMIN" && m.role === "ADMIN") return false
        return true
    }

    const canTransferOwner = (m) => {
        if (group.my_role !== "OWNER") return false
        if (m.user_id === user?.id) return false
        if (m.role === "OWNER") return false

        if (!m.is_premium) return false
        if (m.has_owned_group) return false

        return true
    }

    const handleRemove = async (targetId) => {
        setActionLoading(targetId)
        try {
            await removeMember(group.id, targetId)
            setData((prev) => ({
                ...prev,
                members: prev.members.filter((m) => m.user_id !== targetId),
            }))
            toast.success("멤버를 추방했습니다.")
        } catch (e) {
            toast.error(e.message || "추방에 실패했습니다.")
        } finally {
            setActionLoading(null)
            setConfirmRemove(null)
        }
    }

    const handleRoleChange = async (targetId, role) => {
        setActionLoading(targetId)
        try {
            await changeMemberRole(group.id, targetId, role)
            setData((prev) => ({
                ...prev,
                members: prev.members.map((m) => 
                    m.user_id === targetId ? { ...m, role} : m
                ),
            }))
            toast.success("권한이 변경됐습니다.")
        } catch (e) {
            toast.error(e.message || '권한 변경에 실패했습니다.')
        } finally {
            setActionLoading(null)
        }
    }

    const handleTransferOwner = (targetId) => {
        setConfirmTransfer(targetId)
    }

    const executeTransferOwner = async (targetId) => {
        setActionLoading(targetId)

        try {
            await transferOwner(group.id, targetId)
            setData((prev) => ({
                ...prev,
                members: prev.members.map((m) => {
                    if (m.user_id === targetId) {
                        return {...m, role: "OWNER"}
                    }
                    if (m.user_id === user?.id) {
                        return { ...m, role: "ADMIN" }  
                    }
                    return m
                }),
            }))
            const updated = await getGroupDetail(group.id)
            setGroup(updated)

            toast.success("오너가 변경되었습니다.")
        } catch (e) {
            toast.error(e.message || "오너 변경 실패")
        } finally {
            setActionLoading(null)
            setConfirmTransfer(null)
        }
    }

    const getOwnerTooltip = (m) => {
        if (!m.is_premium) {
            return "프리미엄 플랜 사용자만 오너로 지정할 수 있습니다."
        }
        if (m.has_owned_group) {
            return "이미 다른 워크스페이스의 오너입니다."
        }
        return ""
    }


    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {/* 초대(OWNER/ADMIN만) */}
            {canSeeInvited && (
                <div className="rounded-lg border p-4 space-y-3">
                    <h3 className="font-semibold text-sm">멤버 초대</h3>
                    <div className="flex gap-2">
                        <Input 
                            placeholder="유저명 입력"
                            value={inviteUsername}
                            onChange={(e) => setInviteUsername(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleInvite()}
                        />
                        <Select value={inviteRole} onValueChange={setInviteRole}>
                            <SelectTrigger className="w-32">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="ADMIN">ADMIN</SelectItem>
                                <SelectItem value="EDITOR">EDITOR</SelectItem>
                                <SelectItem value="VIEWER">VIEWER</SelectItem>
                            </SelectContent>
                        </Select>
                        <Button
                            variant="outline"
                            onClick={() => {
                                if(!inviteUsername.trim()) return
                                setConfirmInvite(true)
                            }}
                            disabled={inviteLoading || !inviteUsername.trim()}
                        >
                            {inviteLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : '초대'}
                        </Button>
                    </div>
                    {inviteError && (
                        <p className="text-xs text-destructive">{inviteError}</p>
                    )}
                </div>
            )}

            {/* 검색 */}
            <div className="flex gap-2">
                <Input
                    placeholder="유저명으로 검색"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="flex-1"
                />
                <Button 
                    variant="outline"
                    onClick={handleSearch}
                >
                검색
                </Button>
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
                                <div className="flex flex-col gap-0.5">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium">{m.username}</span>
                                        {m.user_id === user?.id && (
                                            <span className="text-xs text-muted-foreground font-normal">(나)</span>
                                        )} 
                                        <Badge 
                                            variant={m.is_premium ? "secondary" : "outline"}
                                            className="text-[10px] px-1.5 py-0 h-4 font-normal leading-none shrink-0"
                                            >
                                            {m.is_premium ? "Premium" : "Free"}
                                        </Badge>
                                    </div>
                                    <span className="text-xs text-muted-foreground leading-none">
                                        {m.email}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {canRolechange(m) && (
                                        <>
                                            <Select
                                                value={m.role}
                                                onValueChange={(role) => handleRoleChange(m.user_id, role)}
                                                disabled={actionLoading === m.user_id}
                                            >
                                                <SelectTrigger className="w-28 h-8 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="ADMIN">ADMIN</SelectItem>
                                                    <SelectItem value="EDITOR">EDITOR</SelectItem>
                                                    <SelectItem value="VIEWER">VIEWER</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            {canTransferOwner(m) ? (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={actionLoading === m.user_id}
                                                    onClick={() => handleTransferOwner(m.user_id)}
                                                    className="h-8 px-2 text-xs"
                                                >
                                                    OWNER 변경
                                                </Button>
                                            ) : (
                                                <Tooltip delayDuration={0}>
                                                    <TooltipTrigger asChild>
                                                        <span className="inline-block">
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled
                                                                className="h-8 px-2 text-xs opacity-50"
                                                            >
                                                                OWNER 변경
                                                            </Button>
                                                        </span>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {getOwnerTooltip(m)}
                                                    </TooltipContent>
                                                </Tooltip>
                                            )}
                                            <Button
                                                variant="destructive"
                                                size="sm"
                                                onClick={() => setConfirmRemove(m.user_id)}
                                                disabled={actionLoading === m.user_id}
                                                className="hover:text-destructive hover:bg-destructive/10 h-8 px-2"
                                            >
                                                추방
                                            </Button>
                                        </>
                                    )}
                                    {!canRolechange(m) && <RoleBadge role={m.role} />}
                                </div>
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

            <ConfirmModal 
                open={confirmInvite}
                message={`${inviteUsername} 님을 ${inviteRole} 로 초대하시겠습니까?`}
                confirmLabel={inviteLoading ? "처리 중..." : "초대"}
                onConfirm={() => {
                    setConfirmInvite(false)
                    handleInvite()
                }}
                onCancel={() => setConfirmInvite(false)}
            />

            <ConfirmModal
                open={confirmRemove !== null}
                message="해당 멤버를 추방하시겠습니까?"
                confirmLabel={actionLoading ? '처리 중...' : '추방'}
                onConfirm={() => handleRemove(confirmRemove)}
                onCancel={() => setConfirmRemove(null)}
            />

            <ConfirmModal
                open={confirmTransfer !== null}
                message="해당 멤버에게 오너 권한을 양도하시겠습니까?"
                confirmLabel={actionLoading ? "처리 중..." : "양도"}
                onConfirm={() => executeTransferOwner(confirmTransfer)}
                onCancel={() => setConfirmTransfer(null)}
            />
        </div>
        
    )

}


// 워크 스페이스 탭
function WorkspaceTab({ group, onUpdated }){
    // 권한 체크 오너 어드민이면 이름 변경, 그룹 상세 정보, 전체 다운, 그룹 삭제
    // 에디터, 뷰어면 그룹 상세정보만
    const isOwner = group.my_role === "OWNER"
    //const isAdmin = group.my_role === "ADMIN"
    const isPending = group.status === "DELETE_PENDING"

    const canDelete = isOwner
    //const canRename = isOwner || isAdmin
    //const canDownload = isOwner || isAdmin

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
                        <Button
                            variant="outline"
                            onClick={() => setConfirmType('delete')}
                            className="flex items-center gap-2 rounded-md border border-destructive px-3 py-1.5 text-sm text-destructive hover:bg-destructive/5 transition-colors"
                        >
                            <Trash2 className="h-4 w-4" />
                            워크스페이스 삭제 요청
                        </Button>
                    ) : (
                        <Button
                            variant="outline"
                            onClick={() => setConfirmType('cancel')}
                            className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                        >
                            <Undo2 className="h-4 w-4" />
                            삭제 취소
                        </Button>
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
    const [searchParams, setSearchParams] = useSearchParams()
    const tabFromUrl = searchParams.get("tab")

    useEffect(() => {
        const timerId = window.setInterval(async () => {
            try {
                const updated = await getGroupDetail(group_id)
                setGroup(updated)
            } catch (e) {
                console.error('그룹 상세 polling 실패:', e)
            }
        }, GROUP_POLLING_INTERVAL)

        return () => window.clearInterval(timerId)
    }, [group_id])


    useEffect(() => {
        setActiveTab(tabFromUrl || "documents")
    }, [tabFromUrl])
    
    const handleTabChange = (tab) => {
        setActiveTab(tab)
        const newParams = new URLSearchParams(searchParams)
        newParams.set("tab", tab)

        setSearchParams(newParams)
    }

    useEffect(() => {
        setLoading(true)
        getGroupDetail(group_id)
        .then(setGroup)
        .catch((e) => setError(e.message ?? '불러오기에 실패했습니다.'))
        .finally(() => setLoading(false))
    }, [group_id])

    const visibleTabs = useMemo(() => 
        group
            ? TABS.filter((t) => 
                t.roles.includes(group.my_role) &&
                ! (t.hideOnPending && group.status === "DELETE_PENDING")
            )
            : []
            ,[group])

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
        <UploadProvider groupId={group_id}>
            <div className="p-6 max-w-5xl mx-auto">

            {/* 삭제 예정 배너 */}
            {group.status == "DELETE_PENDING" && (
                <DeletePendingBanner scheduledAt={group.delete_scheduled_at} />
            )}

            {/* 헤더 */}
            <div className="mb-6">
                {/* 뒤로가기 버튼 */}
                <div className="mb-6 flex items-center gap-2">
                    <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => navigate("/workspace")} className="gap-1.5 mb-3 -ml-2"
                    >
                        <ArrowLeft size={15} />
                        그룹 목록
                    </Button>
                </div>
                <div className="flex items-center gap-2">
                    <Home className="h-8 w-8 "/>
                    <h1 className="text-2xl font-bold">{group.name}</h1>
                    <Badge 
                    variant={group.my_role === 'OWNER' ? 'default' : 'secondary'}
                    className="text-[10px] px-2 py-0.5 rounded-sm font-semibold tracking-tight"
                    >
                    {group.my_role}
                    </Badge>
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
                    onClick={() => handleTabChange(tab.key)}
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
            {activeTab === 'upload' && <UploadPage myRole={group.my_role} />}
            {activeTab === 'documents' && (<DocumentsTab group={group} />
            )}
            {activeTab === 'approvals' && <ApprovalsTab group={group} />}
            {activeTab === 'trash'     && <div>휴지통 섹션</div>}
            {activeTab === 'members'   && (
                <TooltipProvider>
                    <MembersTab group={group} setGroup={setGroup}/>
                </TooltipProvider>
            )}
            {activeTab === "workspace" && (
                <WorkspaceTab group={group} onUpdated={(updated) => setGroup(updated)} />
            )}
            </div>
        </UploadProvider>
    )
}
