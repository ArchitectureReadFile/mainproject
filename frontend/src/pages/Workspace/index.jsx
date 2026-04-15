import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/Button'
import { Card, CardFooter, CardHeader } from '@/shared/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/Dialog'
import { Input } from '@/shared/ui/Input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'
import {
  Calendar,
  FileText,
  FolderOpen,
  Loader2,
  Plus,
  Users,
  Home,
  CreditCard,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createGroup, getMyGroups } from '@/shared/api/groups'
import { calcKoreanDday, formatKoreanDate } from '@/shared/lib/datetime'

const ROLE_STYLE = {
  OWNER: { label: 'OWNER', variant: 'default' },
  ADMIN: { label: 'ADMIN', variant: 'secondary' },
  EDITOR: { label: 'EDITOR', variant: 'outline' },
  VIEWER: { label: 'VIEWER', variant: 'outline' },
}

/**
 * D-Day를 계산한다.
 */
function calcDday(isoDate) {
  return calcKoreanDday(isoDate)
}

function RoleBadge({ role }) {
  const { label, variant } = ROLE_STYLE[role] ?? { label: role, variant: 'outline' }
  return <Badge variant={variant}>{label}</Badge>
}

function StatusBadge({ status, scheduledAt }) {
  if (status === 'ACTIVE') return null
  const dday = calcDday(scheduledAt)
  return <Badge variant="destructive">삭제 예정 {dday}</Badge>
}

/**
 * 오너 워크스페이스 접근 제한 안내를 표시한다.
 */
function OwnerWorkspaceNotice({ reason, onUpgrade }) {
  const isSubscriptionExpired = reason === 'SUBSCRIPTION_EXPIRED'

  return (
    <div className="rounded-2xl border border-red-200 bg-red-50/70 px-5 py-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-700">
            <CreditCard className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-red-900">워크스페이스 접근이 제한되었습니다</p>
            <p className="mt-1 text-sm leading-6 text-red-800">
              {isSubscriptionExpired
                ? '구독 만료로 워크스페이스 접근이 제한되었습니다. 데이터는 만료 후 60일 동안 보관되며, 기간 안에 재구독하면 복구할 수 있습니다.'
                : '삭제 유예 기간이 종료되어 내가 만든 워크스페이스에 더 이상 접근할 수 없습니다.'}
            </p>
          </div>
        </div>

        {isSubscriptionExpired && (
          <Button onClick={onUpgrade} className="shrink-0 gap-2">
            <CreditCard className="h-4 w-4" />
            구독 관리하러 가기
          </Button>
        )}
      </div>
    </div>
  )
}

function GroupCard({ group, onClick }) {
  const isDeleting = group.status !== 'ACTIVE'

  return (
    <Card
      onClick={onClick}
      className={`cursor-pointer transition-shadow hover:shadow-md min-h-[230px] flex flex-col justify-between ${isDeleting ? 'opacity-60' : ''}`}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex h-13 w-13 items-center justify-center rounded-lg bg-muted">
              <Home className="h-8 w-8" />
            </div>
            <p className="mt-1 truncate font-semibold">{group.name}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">OWNER: {group.owner_username}</p>
          </div>
          <div className="flex shrink-0 gap-1.5">
            <StatusBadge status={group.status} scheduledAt={group.delete_scheduled_at} />
            <RoleBadge role={group.my_role} />
          </div>
        </div>
      </CardHeader>

      <div className="px-6">
        <hr className="border-muted" />
      </div>

      <CardFooter className="gap-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Users className="h-3.5 w-3.5" />
          {group.member_count}명
        </span>
        <span className="flex items-center gap-1">
          <FileText className="h-3.5 w-3.5" />
          {group.document_count}개
        </span>
        <span className="flex items-center gap-1 ml-auto">
          <Calendar className="h-3.5 w-3.5" />
          {formatKoreanDate(group.created_at)}
        </span>
      </CardFooter>
    </Card>
  )
}

function CreateGroupCard({ onClick }) {
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer border-dashed transition-shadow hover:shadow-md flex items-center justify-center min-h-[230px]"
    >
      <div className="flex flex-col items-center gap-2 text-muted-foreground">
        <Plus className="h-6 w-6" />
        <span className="text-sm">새 워크스페이스 생성</span>
      </div>
    </Card>
  )
}

/**
 * 그룹 생성 모달이다.
 */
function CreateGroupDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleClose = () => {
    setName('')
    setDescription('')
    setError('')
    onClose()
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('워크스페이스 이름을 입력해주세요.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const group = await createGroup({
        name: name.trim(),
        description: description.trim() || undefined,
      })
      onCreated(group)
      handleClose()
    } catch (e) {
      setError(e.message || '생성에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>워크스페이스 생성</DialogTitle>
          <DialogDescription>
            워크스페이스 이름과 설명을 입력해 새 작업 공간을 생성하세요.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ws-name">이름 *</Label>
            <Input
              id="ws-name"
              placeholder="예: 글로벌 아카데미"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              maxLength={100}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ws-desc">설명 (선택)</Label>
            <Textarea
              id="ws-desc"
              placeholder="워크스페이스에 대한 간단한 설명을 입력하세요"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              maxLength={500}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={loading}>
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading && <Loader2 className="animate-spin" />}
            생성
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GroupSection({ title, groups, onCardClick }) {
  if (groups.length === 0) return null

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {groups.map((g) => (
          <GroupCard key={g.id} group={g} onClick={() => onCardClick(g.id)} />
        ))}
      </div>
    </section>
  )
}

function EmptyState({ onOpen }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-28 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <FolderOpen className="h-8 w-8 text-muted-foreground" />
      </div>
      <div>
        <p className="font-semibold">아직 워크스페이스가 없어요</p>
        <p className="mt-1 text-sm text-muted-foreground">
          워크스페이스를 만들어 법률 문서를 팀과 함께 관리하세요
        </p>
      </div>
      <Button onClick={onOpen} className="gap-2">
        <Plus className="h-4 w-4" />
        새 워크스페이스 생성
      </Button>
    </div>
  )
}

export default function WorkspacePage() {
  const navigate = useNavigate()
  const [groups, setGroups] = useState([])
  const [hasBlockedOwnedGroup, setHasBlockedOwnedGroup] = useState(false)
  const [blockedOwnedGroupReason, setBlockedOwnedGroupReason] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    getMyGroups()
      .then(({ groups, has_blocked_owned_group, blocked_owned_group_reason }) => {
        setGroups(groups)
        setHasBlockedOwnedGroup(has_blocked_owned_group)
        setBlockedOwnedGroupReason(blocked_owned_group_reason)
      })
      .catch((e) => setError(e.message || '불러오기에 실패했습니다.'))
      .finally(() => setLoading(false))
  }, [])

  const handleCreated = (newGroup) => {
    setGroups((prev) => [newGroup, ...prev])
  }

  const myGroups = groups.filter((g) => g.my_role === 'OWNER')
  const invitedGroups = groups.filter((g) => g.my_role !== 'OWNER')

  const hasActiveOwnerGroup = myGroups.some((group) => group.status === 'ACTIVE')
  const hasSubscriptionExpiredOwnerGroup = myGroups.some(
    (group) => group.pending_reason === 'SUBSCRIPTION_EXPIRED'
  )

  const isBlockedBySubscriptionExpired =
    blockedOwnedGroupReason === 'SUBSCRIPTION_EXPIRED'

  const canCreateOwnerWorkspace =
    !hasActiveOwnerGroup &&
    !hasSubscriptionExpiredOwnerGroup &&
    !isBlockedBySubscriptionExpired

  const shouldShowBlockedNotice =
    hasBlockedOwnedGroup && blockedOwnedGroupReason === 'SUBSCRIPTION_EXPIRED'


  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div>
        <h1 className="mb-3 text-2xl font-bold">워크스페이스</h1>
        <p className="mb-10 text-sm text-muted-foreground">
          내가 속한 그룹을 관리하고 법률 문서를 업로드하세요
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-28">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="py-28 text-center text-sm text-destructive">{error}</div>
      ) : groups.length === 0 && !shouldShowBlockedNotice && canCreateOwnerWorkspace ? (
        <EmptyState onOpen={() => setDialogOpen(true)} />
      ) : (
        <>
          <section className="mb-8">
            <h2 className="mb-3 text-sm font-semibold">내가 만든 워크스페이스</h2>

            {myGroups.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {myGroups.map((group) => (
                  <GroupCard
                    key={group.id}
                    group={group}
                    onClick={() => navigate(`/workspace/${group.id}`)}
                  />
                ))}

                {canCreateOwnerWorkspace && (
                  <CreateGroupCard onClick={() => setDialogOpen(true)} />
                )}
              </div>
            ) : shouldShowBlockedNotice ? (
              <OwnerWorkspaceNotice
                reason={blockedOwnedGroupReason}
                onUpgrade={() => navigate('/mypage')}
              />
            ) : canCreateOwnerWorkspace ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <CreateGroupCard onClick={() => setDialogOpen(true)} />
              </div>
            ) : null}
          </section>

          <GroupSection
            title="초대받은 워크스페이스"
            groups={invitedGroups}
            onCardClick={(id) => navigate(`/workspace/${id}`)}
          />
        </>
      )}

      <CreateGroupDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  )
}
