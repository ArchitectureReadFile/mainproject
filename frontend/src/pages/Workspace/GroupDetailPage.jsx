import {
    getGroupDetail, requestDeleteGroup, cancelDeleteGroup, getMembers, inviteMember,
    removeMember, changeMemberRole, transferOwner, leaveGroup, getGroupDocuments,
} from '@/shared/api/groups'
import {
    calcKoreanDday,
    formatKoreanDate,
    formatKoreanDateTime,
} from '@/shared/lib/datetime'
import {
    createExportJob,
    getExportDownloadUrl,
    getExportJob,
    getLatestExportJob,
} from '@/shared/api/exports'
import { setStoredExportIntent } from '@/features/export/utils/exportIntent'
import { ConfirmModal } from '@/shared/ui/confirm-modal'
import {
    AlertTriangle, Download, FileText, Home, Loader2,
    Trash2, Undo2, Users, ArrowLeft, Lock,
} from 'lucide-react'
import { useEffect, useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import UploadPage from '@/pages/Upload/index'
import DocumentsTab from '@/pages/Workspace/DocumentsTab'
import { Badge } from '@/shared/ui/badge'
import { useAuth } from '@/features/auth/index'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/Button'
import { Input } from '@/shared/ui/Input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/shared/ui/tooltip'
import { UploadProvider } from '@/features/upload/context/UploadContext'
import ApprovalsTab from '@/pages/Workspace/ApprovalsTab'
import TrashTab from '@/pages/Workspace/TrashTab'

const TABS = [
    { key: 'upload', label: '업로드', roles: ['OWNER', 'ADMIN', 'EDITOR'], hideWhenNotActive: true },
    { key: 'documents', label: '문서', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
    { key: 'approvals', label: '승인', roles: ['OWNER', 'ADMIN'] },
    { key: 'trash', label: '휴지통', roles: ['OWNER', 'ADMIN', 'EDITOR'] },
    { key: 'members', label: '멤버', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
    { key: 'workspace', label: '워크스페이스', roles: ['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] },
]

const GROUP_POLLING_INTERVAL = 5000
const EXPORT_POLLING_INTERVAL = 3000

const EXPORT_STATUS_LABEL = {
    PENDING: '요청됨',
    PROCESSING: '압축 파일 생성 중',
    READY: '다운로드 가능',
    FAILED: '생성 실패',
    EXPIRED: '보관 기간 만료',
    CANCELLED: '취소됨',
}

/**
 * export ZIP 다운로드를 시작한다.
 */
function triggerExportDownload(jobId, fileName) {
    const link = document.createElement('a')
    link.href = getExportDownloadUrl(jobId)
    link.download = fileName || 'workspace_documents.zip'
    document.body.appendChild(link)
    link.click()
    link.remove()
}

/**
 * export 만료 시각을 화면용 문자열로 변환한다.
 */
function formatExportExpiresAt(isoDate) {
    if (!isoDate) return null
    return formatKoreanDateTime(isoDate)
}


/**
 * 승인된 문서 수를 조회한다.
 */
async function getApprovedDocumentCount(groupId) {
    const response = await getGroupDocuments(groupId, {
        skip: 0,
        limit: 1,
        viewType: 'all',
    })
    return response.total ?? 0
}

/**
 * D-Day를 계산한다.
 */
function calcDday(isoDate) {
    return calcKoreanDday(isoDate)
}

/**
 * 워크스페이스 상태를 화면 분기에 맞게 해석한다.
 */
function getGroupViewState(group) {
    const isActive = group?.status === 'ACTIVE'
    const isDeletePending = group.status === 'DELETE_PENDING'
    const pendingReason = group?.pending_reason ?? null

    const isSubscriptionExpiredPending =
        isDeletePending && group.pending_reason === 'SUBSCRIPTION_EXPIRED'

    return {
        isActive,
        isDeletePending,
        isOwnerDeletePending:
            isDeletePending && pendingReason === 'OWNER_DELETE_REQUEST',
        isSubscriptionExpiredPending,
        isWriteRestricted: !isActive,
        isReadOnlyMode: isSubscriptionExpiredPending,
        canCancelDelete:
            isDeletePending && pendingReason === 'OWNER_DELETE_REQUEST',
    }
}

/**
 * 삭제 예정 상태에 대한 상단 안내 배너를 표시한다.
 */
function PendingNoticeBanner({ pendingReason }) {
    const isSubscriptionExpired = pendingReason === 'SUBSCRIPTION_EXPIRED'

    return (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <Lock className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
                <p className="font-semibold">
                    {isSubscriptionExpired ? '현재 읽기 전용 기간입니다.' : '현재 삭제 예정 상태입니다.'}
                </p>
                <p className="mt-1 text-amber-800">
                    {isSubscriptionExpired
                        ? '구독이 만료되어 문서와 승인 내역 조회, 다운로드만 가능하며, 업로드·승인·멤버 관리 같은 변경 작업은 제한됩니다.'
                        : '소유자가 워크스페이스 삭제를 요청한 상태입니다. 삭제 예정일까지 조회 및 다운로드는 가능하며, 워크스페이스 탭에서 삭제를 취소할 수 있습니다.'}
                </p>
            </div>
        </div>
    )
}


/**
 * 삭제 예정 상태를 안내하는 상단 배너를 표시한다.
 */
function DeletePendingBanner({ scheduledAt, pendingReason }) {
    if (!scheduledAt) {
        return (
            <div className="mb-5 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>
                    {pendingReason === 'SUBSCRIPTION_EXPIRED'
                        ? '구독 만료로 워크스페이스가 삭제 예정 상태로 전환되었습니다.'
                        : '해당 워크스페이스는 삭제 요청되어 삭제 예정 상태입니다.'}
                </span>
            </div>
        )
    }

    const dday = calcDday(scheduledAt)

    return (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
                <span className="font-semibold">
                    {dday}({formatKoreanDate(scheduledAt)} 삭제 예정)
                </span>
            </span>
        </div>
    )
}

const ROLE_STYLE = {
    OWNER: { label: 'OWNER', variant: 'default' },
    ADMIN: { label: 'ADMIN', variant: 'secondary' },
    EDITOR: { label: 'EDITOR', variant: 'outline' },
    VIEWER: { label: 'VIEWER', variant: 'outline' },
}

function RoleBadge({ role }) {
    const { label, variant } = ROLE_STYLE[role] ?? { label: role, variant: 'outline' }
    return (
        <Badge
            variant={variant}
            className="rounded-sm font-semibold justify-center w-15"
        >
            {label}
        </Badge>
    )
}

/**
 * 멤버 표시명을 반환
 */
function formatMemberDisplayName(member) {
    if (!member?.username) return '-'
    return member.is_active === false
        ? `${member.username}(탈퇴)`
        : member.username
}


function MembersTab({ group, setGroup, isWriteRestricted }) {
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
    const [confirmCancelInvite, setConfirmCancelInvite] = useState(null)
    const [actionLoading, setActionLoading] = useState(null)
    const [confirmInvite, setConfirmInvite] = useState(false)
    const [confirmTransfer, setConfirmTransfer] = useState(null)

    const handleInvite = async () => {
        if (!inviteUsername.trim()) return
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
            setInviteRole('EDITOR')
            toast.success('초대에 성공했습니다.')
        } catch (e) {
            setInviteError(e.message || '초대에 실패했습니다.')
        } finally {
            setInviteLoading(false)
        }
    }

    const rolePriority = {
        OWNER: 1,
        ADMIN: 2,
        EDITOR: 3,
        VIEWER: 4,
    }

    useEffect(() => {
        setLoading(true)
        getMembers(group.id)
            .then(setData)
            .catch((e) => setError(e.message ?? '멤버 목록을 불러오지 못했습니다.'))
            .finally(() => setLoading(false))
    }, [group.id])

    if (loading) {
        return (
            <div className="flex justify-center py-20">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return <div className="py-20 text-center text-sm text-destructive">{error}</div>
    }

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

    const isSubscriptionExpiredPending =
        group.status === 'DELETE_PENDING' &&
        group.pending_reason === 'SUBSCRIPTION_EXPIRED'

    const canInviteOrManageMembers =
        group.status === 'ACTIVE' &&
        (group.my_role === 'OWNER' || group.my_role === 'ADMIN')

    const canSeeInvited = canInviteOrManageMembers

    const canRolechange = (m) => {
        if (!canInviteOrManageMembers) return false
        if (m.user_id === user?.id) return false
        if (m.role === 'OWNER') return false
        if (group.my_role === 'ADMIN' && m.role === 'ADMIN') return false
        return true
    }

    const canTransferOwner = (m) => {
        const canTransferByState =
            group.status === 'ACTIVE' ||
            (
                group.status === 'DELETE_PENDING' &&
                group.pending_reason === 'SUBSCRIPTION_EXPIRED'
            )

        if (!canTransferByState) return false
        if (group.my_role !== 'OWNER') return false
        if (m.user_id === user?.id) return false
        if (m.role === 'OWNER') return false
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
            toast.success('멤버를 추방했습니다.')
        } catch (e) {
            toast.error(e.message || '추방에 실패했습니다.')
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
                    m.user_id === targetId ? { ...m, role } : m
                ),
            }))
            toast.success('권한이 변경됐습니다.')
        } catch (e) {
            toast.error(e.message || '권한 변경에 실패했습니다.')
        } finally {
            setActionLoading(null)
        }
    }

    const handleTransferOwner = (targetId) => {
        setConfirmTransfer(targetId)
    }

    /**
     * 초대 대기 중인 멤버의 초대를 취소한다.
     */
    const handleCancelInvite = async (targetId) => {
        setActionLoading(targetId)
        try {
            await removeMember(group.id, targetId)
            setData((prev) => ({
                ...prev,
                invited: prev.invited.filter((m) => m.user_id !== targetId),
            }))
            toast.success('초대를 취소했습니다.')
        } catch (e) {
            toast.error(e.message || '초대 취소에 실패했습니다.')
        } finally {
            setActionLoading(null)
            setConfirmCancelInvite(null)
        }
    }


    const executeTransferOwner = async (targetId) => {
        setActionLoading(targetId)

        try {
            await transferOwner(group.id, targetId)
            setData((prev) => ({
                ...prev,
                members: prev.members.map((m) => {
                    if (m.user_id === targetId) {
                        return { ...m, role: 'OWNER' }
                    }
                    if (m.user_id === user?.id) {
                        return { ...m, role: 'ADMIN' }
                    }
                    return m
                }),
            }))
            const updated = await getGroupDetail(group.id)
            setGroup(updated)
            toast.success('오너가 변경되었습니다.')
        } catch (e) {
            toast.error(e.message || '오너 변경 실패')
        } finally {
            setActionLoading(null)
            setConfirmTransfer(null)
        }
    }

    const getOwnerTooltip = (m) => {
        if (!m.is_premium) {
            return '프리미엄 플랜 사용자만 오너로 지정할 수 있습니다.'
        }
        if (m.has_owned_group) {
            return '이미 다른 워크스페이스의 오너입니다.'
        }
        return ''
    }

    const shouldShowTransferOwnerButton =
        group.my_role === 'OWNER' &&
        (
            group.status === 'ACTIVE' ||
            (
                group.status === 'DELETE_PENDING' &&
                group.pending_reason === 'SUBSCRIPTION_EXPIRED'
            )
        )

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {isWriteRestricted && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <p className="text-amber-800">
                        {isSubscriptionExpiredPending
                            ? '구독 만료 상태에서는 멤버 초대, 권한 변경, 추방은 제한되지만 프리미엄 멤버에게 오너 권한을 양도하여 워크스페이스를 복구할 수 있습니다.'
                            : '삭제 예정 상태에서는 멤버 초대, 권한 변경, 추방이 제한됩니다.'}
                    </p>
                </div>
            )}

            {canSeeInvited && (
                <div className="rounded-lg border p-4 space-y-3">
                    <h3 className="font-semibold text-sm">멤버 초대</h3>
                    <div className="flex gap-2">
                        <Input
                            placeholder="유저명 입력"
                            value={inviteUsername}
                            onChange={(e) => setInviteUsername(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
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
                                if (!inviteUsername.trim()) return
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

            <div className="flex gap-2">
                <Input
                    placeholder="유저명으로 검색"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="flex-1"
                />
                <Button variant="outline" onClick={handleSearch}>검색</Button>
            </div>

            <div className="rounded-lg border">
                <div className="px-5 py-4 border-b">
                    <h3 className="font-semibold">
                        멤버 <span className="text-muted-foreground font-normal text-sm">{filteredMembers.length}명</span>
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
                                        <span className="text-sm font-medium">{formatMemberDisplayName(m)}</span>
                                        {m.user_id === user?.id && (
                                            <span className="text-xs text-muted-foreground font-normal">(나)</span>
                                        )}
                                        <Badge
                                            variant={m.is_premium ? 'secondary' : 'outline'}
                                            className="text-[10px] px-1.5 py-0 h-4 font-normal leading-none shrink-0"
                                        >
                                            {m.is_premium ? 'Premium' : 'Free'}
                                        </Badge>
                                    </div>
                                    <span className="text-xs text-muted-foreground leading-none">
                                        {m.email}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {canRolechange(m) ? (
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
                                    ) : (
                                        <RoleBadge role={m.role} />
                                    )}

                                    {shouldShowTransferOwnerButton && (
                                        canTransferOwner(m) ? (
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
                                        )
                                    )}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {(canSeeInvited && (invited.length > 0 || filteredInvited.length > 0)) && (
                <div className="rounded-lg border">
                    <div className="px-5 py-4 border-b">
                        <h3 className="font-semibold">
                            초대 대기 중 <span className="text-muted-foreground font-normal text-sm">{filteredInvited.length}명</span>
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
                                            초대일: {formatKoreanDate(m.invited_at)}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <RoleBadge role={m.role} />
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setConfirmCancelInvite(m.user_id)}
                                            disabled={actionLoading === m.user_id}
                                            className="h-8 px-2 text-xs"
                                        >
                                            초대 취소 
                                        </Button>
                                    </div>                
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            <ConfirmModal
                open={confirmInvite}
                message={`${inviteUsername} 님을 ${inviteRole} 로 초대하시겠습니까?`}
                confirmLabel={inviteLoading ? '처리 중...' : '초대'}
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
                open={confirmCancelInvite !== null}
                message="해당 초대를 취소하시겠습니까?"
                confirmLabel={actionLoading ? '처리 중...' : '초대 취소'}
                onConfirm={() => handleCancelInvite(confirmCancelInvite)}
                onCancel={() => setConfirmCancelInvite(null)}
            />

            <ConfirmModal
                open={confirmTransfer !== null}
                message="해당 멤버에게 오너 권한을 양도하시겠습니까?"
                confirmLabel={actionLoading ? '처리 중...' : '양도'}
                onConfirm={() => executeTransferOwner(confirmTransfer)}
                onCancel={() => setConfirmTransfer(null)}
            />
        </div>
    )
}

function WorkspaceTab({ group, onUpdated, isWriteRestricted }) {
    const navigate = useNavigate()
    const isOwner = group.my_role === 'OWNER'
    const isAdmin = group.my_role === 'ADMIN'
    const isPending = group.status === 'DELETE_PENDING'
    const isOwnerDeletePending =
        isPending && group.pending_reason === 'OWNER_DELETE_REQUEST'

    const canDelete = isOwner && group.status === 'ACTIVE'
    const canCancelDelete = isOwner && isOwnerDeletePending
    const canLeave =
        group.my_role !== 'OWNER' &&
        (group.status === 'ACTIVE' || group.status === 'DELETE_PENDING')

    const canBackup =
        (isOwner || isAdmin) &&
        (group.status === 'ACTIVE' || group.status === 'DELETE_PENDING')

    const [confirmType, setConfirmType] = useState(null)
    const [loading, setLoading] = useState(false)
    const [exportJob, setExportJob] = useState(null)
    const [exportLoading, setExportLoading] = useState(false)

    /**
     * READY 상태의 기존 백업 ZIP을 다시 다운로드한다.
     */
    const handleDownloadExport = () => {
        if (!exportJob?.id) return
        triggerExportDownload(exportJob.id, exportJob.export_file_name)
    }

    /**
     * 새로운 워크스페이스 백업 export job을 생성한다.
     */
    const handleCreateNewExport = async () => {
        setExportLoading(true)
        try {
            const nextJob = await createExportJob(group.id)

            setStoredExportIntent({
                jobId: nextJob.id,
                groupId: group.id,
                autoDownload: true,
            })

            setExportJob(nextJob)
        } catch (e) {
            toast.error(e.message || '전체 다운로드 요청에 실패했습니다.')
        } finally {
            setExportLoading(false)
        }
    }

    const handleConfirm = async () => {
        setLoading(true)
        try {
            if (confirmType === 'delete') {
                const updated = await requestDeleteGroup(group.id)
                onUpdated(updated)
                toast.success('삭제 요청이 완료됐습니다.')
            } else if (confirmType === 'cancel') {
                const updated = await cancelDeleteGroup(group.id)
                onUpdated(updated)
                toast.success('삭제가 취소됐습니다.')
            } else if (confirmType === 'leave') {
                await leaveGroup(group.id)
                toast.success('워크스페이스에서 탈퇴했습니다.')
                navigate('/workspace')
            }
        } catch (e) {
            toast.error(e.message || '처리에 실패했습니다.')
        } finally {
            setLoading(false)
            setConfirmType(null)
        }
    }

    useEffect(() => {
        if (!canBackup) {
            setExportJob(null)
            return
        }

        setExportJob(null)

        getLatestExportJob(group.id)
            .then((job) => {
                if (!job) return
                setExportJob(job)
            })
            .catch((e) => {
                console.error('최근 export job 조회 실패:', e)
            })
    }, [group.id, canBackup])

    useEffect(() => {
        if (!exportJob || !['PENDING', 'PROCESSING'].includes(exportJob.status)) return

        const timerId = window.setInterval(() => {
            getExportJob(exportJob.id)
                .then((nextJob) => {
                    setExportJob(nextJob)
                })
                .catch((e) => {
                    console.error('export polling 실패:', e)
                })
        }, EXPORT_POLLING_INTERVAL)

        return () => window.clearInterval(timerId)
    }, [exportJob])


    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {isWriteRestricted && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <p className="text-amber-800">
                        {group.pending_reason === 'SUBSCRIPTION_EXPIRED'
                            ? '구독 만료 상태에서는 워크스페이스 정보 확인만 가능하며, 재구독으로 복구할 수 있습니다.'
                            : '삭제 예정 상태에서는 워크스페이스 정보 확인과 삭제 취소만 가능합니다.'}
                    </p>
                </div>
            )}

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
                            {formatKoreanDate(group.created_at)}
                        </span>
                    </div>
                    <div className="flex items-center border-t pt-3">
                        <span className="text-muted-foreground w-24 shrink-0">상태</span>
                        <span className={`font-medium ${isPending ? 'text-destructive' : 'text-green-600'}`}>
                            {isPending
                                ? group.delete_scheduled_at
                                    ? `삭제 예정 (${calcDday(group.delete_scheduled_at)})`
                                    : '삭제 예정'
                                : '정상'}
                        </span>
                    </div>
                </div>
            </div>

            {canBackup && (
                <div className="rounded-lg border p-5 space-y-3">
                    <h3 className="text-base font-semibold">데이터 관리 / 백업</h3>
                    <div className="space-y-1">
                        <p className="text-base text-muted-foreground">
                            워크스페이스 내 모든 문서(승인 대기 및 반려 문서 포함)를 ZIP 파일로 다운로드합니다.
                        </p>
                        <p className="text-sm text-muted-foreground">
                            백업 파일은 생성 시점의 문서 기준으로 만들어집니다. 이후 변경 사항을 반영하려면 새로 백업을 생성해주세요.
                        </p>
                    </div>

                    {exportJob && (
                        <div className="rounded-md bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                            <p>현재 상태: {EXPORT_STATUS_LABEL[exportJob.status] ?? exportJob.status}</p>
                            <p>
                                총 {exportJob.total_file_count}건 중 {exportJob.exported_file_count}건 포함
                                {exportJob.missing_file_count > 0
                                    ? ` · 누락 ${exportJob.missing_file_count}건`
                                    : ''}
                            </p>
                            {exportJob.status === 'READY' && exportJob.expires_at && (
                                <p>{formatExportExpiresAt(exportJob.expires_at)}까지 다시 다운로드할 수 있습니다.</p>
                            )}
                            {exportJob.status === 'FAILED' && exportJob.error_message && (
                                <p className="text-destructive">{exportJob.error_message}</p>
                            )}
                            {exportJob.status === 'EXPIRED' && (
                                <p>기존 백업 파일의 보관 기간이 만료되었습니다. 다시 생성해주세요.</p>
                            )}
                        </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2">
                        {exportJob?.status === 'READY' ? (
                            <>
                                <Button
                                    variant="outline"
                                    onClick={handleDownloadExport}
                                    className="flex items-center gap-2 border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                                >
                                    <Download className="h-4 w-4" />
                                    다시 다운로드
                                </Button>

                                <Button
                                    variant="outline"
                                    onClick={handleCreateNewExport}
                                    disabled={exportLoading}
                                    className="flex items-center gap-2 border-blue-200 text-blue-700 hover:bg-blue-50 hover:text-blue-800 disabled:border-slate-200 disabled:text-slate-400"
                                >
                                    {exportLoading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Download className="h-4 w-4" />
                                    )}
                                    새로 백업 생성
                                </Button>
                            </>
                        ) : (
                            <Button
                                variant="outline"
                                onClick={handleCreateNewExport}
                                disabled={exportLoading || ['PENDING', 'PROCESSING'].includes(exportJob?.status)}
                                className="flex items-center gap-2 border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900 disabled:border-slate-200 disabled:text-slate-400"
                            >
                                {exportLoading || ['PENDING', 'PROCESSING'].includes(exportJob?.status) ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Download className="h-4 w-4" />
                                )}
                                전체 다운로드
                            </Button>
                        )}
                    </div>
                </div>
            )}

            {(canDelete || canCancelDelete) && (
                <div className="rounded-lg border border-destructive/30 p-5 space-y-3">
                    <h3 className="text-base font-semibold text-destructive">워크스페이스 삭제</h3>
                    <p className="text-base text-muted-foreground">
                        {!isPending
                            ? '삭제 요청 후 30일 동안 읽기 전용 상태로 유지되며, 이후 접근이 제한됩니다.'
                            : group.delete_scheduled_at
                                ? `${formatKoreanDate(group.delete_scheduled_at)}까지 읽기 전용 상태로 유지됩니다.`
                                : '삭제 예정 상태입니다.'
                        }
                    </p>
                    {canDelete ? (
                        <Button
                            variant="outline"
                            onClick={() => setConfirmType('delete')}
                            className="flex items-center gap-2 rounded-md border border-destructive px-3 py-1.5 text-sm text-destructive hover:bg-destructive/5 transition-colors"
                        >
                            <Trash2 className="h-4 w-4" />
                            워크스페이스 삭제 요청
                        </Button>
                    ) : canCancelDelete ? (
                        <Button
                            variant="outline"
                            onClick={() => setConfirmType('cancel')}
                            className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                        >
                            <Undo2 className="h-4 w-4" />
                            삭제 취소
                        </Button>
                    ) : null}
                </div>
            )}

            {canLeave && (
                <div className="rounded-lg border border-destructive/30 p-5 space-y-3">
                    <h3 className="text-base font-semibold text-destructive">워크스페이스 탈퇴</h3>
                    <p className="text-base text-muted-foreground">
                        탈퇴하면 이 워크스페이스의 문서와 대화에 더 이상 접근할 수 없습니다.
                    </p>
                    <Button
                        variant="outline"
                        onClick={() => setConfirmType('leave')}
                        className="flex items-center gap-2 rounded-md border border-destructive px-3 py-1.5 text-sm text-destructive hover:bg-destructive/5 transition-colors"
                    >
                        워크스페이스 탈퇴
                    </Button>
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

            <ConfirmModal
                open={confirmType === 'leave'}
                message="정말 이 워크스페이스에서 탈퇴하시겠습니까? 탈퇴 후에는 다시 초대받아야 접근할 수 있습니다."
                confirmLabel={loading ? '처리 중...' : '탈퇴'}
                onConfirm={handleConfirm}
                onCancel={() => setConfirmType(null)}
            />
        </div>
    )
}


export default function GroupDetailPage() {
    const { group_id } = useParams()
    const [group, setGroup] = useState(null)
    const [approvedDocumentCount, setApprovedDocumentCount] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeTab, setActiveTab] = useState('documents')
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()
    const tabFromUrl = searchParams.get('tab')


    /**
     * 그룹 상세와 헤더용 승인 문서 수를 불러온다.
     */
    const loadGroupDetailPage = useCallback(async () => {
        const groupDetail = await getGroupDetail(group_id)
        setGroup(groupDetail)

        try {
            const nextApprovedDocumentCount = await getApprovedDocumentCount(group_id)
            setApprovedDocumentCount(nextApprovedDocumentCount)
        } catch (e) {
            console.error('승인 문서 수 조회 실패:', e)
            setApprovedDocumentCount(0)
        }
    }, [group_id])

    useEffect(() => {
        const timerId = window.setInterval(async () => {
            try {
                await loadGroupDetailPage()
            } catch (e) {
                console.error('그룹 상세 polling 실패:', e)
            }
        }, GROUP_POLLING_INTERVAL)

        return () => window.clearInterval(timerId)
    }, [loadGroupDetailPage])

    useEffect(() => {
        setActiveTab(tabFromUrl || 'documents')
    }, [tabFromUrl])

    const handleTabChange = (tab) => {
        setActiveTab(tab)
        const newParams = new URLSearchParams(searchParams)
        newParams.set('tab', tab)
        newParams.set('page', '1')
        setSearchParams(newParams)
    }

    useEffect(() => {
        setLoading(true)
        loadGroupDetailPage()
            .catch((e) => setError(e.message ?? '불러오기에 실패했습니다.'))
            .finally(() => setLoading(false))
    }, [loadGroupDetailPage])


    const viewState = group ? getGroupViewState(group) : null
    const isWriteRestricted = viewState?.isWriteRestricted ?? false

    const visibleTabs = useMemo(() =>
        group && viewState
            ? TABS.filter((t) =>
                t.roles.includes(group.my_role) &&
                !(t.hideWhenNotActive && !viewState.isActive)
            )
            : []
    , [group, viewState])

    useEffect(() => {
        if (visibleTabs.length && !visibleTabs.find((t) => t.key === activeTab)) {
            const nextTab = visibleTabs[0].key
            setActiveTab(nextTab)

            const nextParams = new URLSearchParams(searchParams)
            nextParams.set('tab', nextTab)
            nextParams.set('page', '1')
            setSearchParams(nextParams)
        }
    }, [visibleTabs, activeTab, searchParams, setSearchParams])

    if (loading) {
        return (
            <div className="flex justify-center py-28">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return <div className="py-28 text-center text-sm text-destructive">{error}</div>
    }

    return (
        <UploadProvider groupId={group_id}>
            <div className="p-6 max-w-5xl mx-auto">
                {viewState?.isDeletePending && (
                    <DeletePendingBanner
                        scheduledAt={group.delete_scheduled_at}
                        pendingReason={group.pending_reason}
                    />
                )}

                {viewState?.isDeletePending && (
                    <PendingNoticeBanner pendingReason={group.pending_reason} />
                )}
                <div className="mb-6">
                    <div className="mb-6 flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate('/workspace')}
                            className="gap-1.5 mb-3 -ml-2"
                        >
                            <ArrowLeft size={15} />
                            그룹 목록
                        </Button>
                    </div>
                    <div className="flex items-center gap-2">
                        <Home className="h-8 w-8" />
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
                                <span>승인된 문서 {approvedDocumentCount}개</span>
                            </div>
                        </div>
                </div>

                <div className="flex gap-2 border-b mb-6">
                    {visibleTabs.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => handleTabChange(tab.key)}
                            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                                activeTab === tab.key
                                    ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                                    : 'border-transparent text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {activeTab === 'upload' && <UploadPage myRole={group.my_role} />}
                {activeTab === 'documents' && <DocumentsTab group={group} />}
                {activeTab === 'approvals' && <ApprovalsTab group={group} />}
                {activeTab === 'trash' && <TrashTab group={group} />}
                {activeTab === 'members' && (
                    <TooltipProvider>
                        <MembersTab
                            group={group}
                            setGroup={setGroup}
                            isWriteRestricted={isWriteRestricted}
                        />
                    </TooltipProvider>
                )}

                {activeTab === 'workspace' && (
                    <WorkspaceTab
                        group={group}
                        onUpdated={(updated) => setGroup(updated)}
                        isWriteRestricted={isWriteRestricted}
                    />
                )}
            </div>
        </UploadProvider>
    )
}
