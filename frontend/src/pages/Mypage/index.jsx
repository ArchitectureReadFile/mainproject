import client from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { Input } from '@/components/ui/Input'
import { Calendar, LogOut, Mail, Users } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { meApi } from '../../features/auth/api/authApi'
import { getMyInvitations, acceptInvite, declineInvite } from '@/api/groups'


export default function MypagePage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [username, setUsername] = useState('')
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const inputRef = useRef(null)
  const [invitations, setInvitations] = useState([])
  const [inviteError, setInviteError] = useState(null)
  const [inviteLoading, setInviteLoading] = useState(true)

  const fetchUser = useCallback(async () => {
    try {
      const data = await meApi()
      setUser(data)
      setUsername(data.username)
    } catch (e) {
      toast.error(e.message || '사용자 정보를 불러오지 못했습니다.')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }, [navigate])

  useEffect(() => { fetchUser() }, [fetchUser])

  const fetchInvitations = useCallback(async () => {
      try {
          const data = await getMyInvitations()
          setInvitations(data)
      } catch (e) {
          setInviteError(e.message || '초대 목록을 불러오지 못했습니다.')
      } finally {
          setInviteLoading(false)
      }
  }, [])

  useEffect(() => { fetchInvitations() }, [fetchInvitations])

  const handleAccept = async (groupId) => {
    try {
      await acceptInvite(groupId)
      setInvitations((prev) => prev.filter((i) => i.group_id !== groupId))
      toast.success("초대를 수락했습니다.")
    } catch (e) {
      toast.error(e.message || "수락에 실패했습니다.")
    }
  }

  const handleDecline = async (groupId) => {
    try {
      await declineInvite(groupId)
      setInvitations((prev) => prev.filter((i) => i.group_id !== groupId))
      toast.success("초대를 거절했습니다.")
    } catch (e) {
      toast.error(e.message || "거절에 실패했습니다.")
    }
  }


  const handleUpdateUsername = async () => {
    try {
      const res = await client.patch('/auth/username', { username })
      setUser((prev) => ({ ...prev, username: res.data.username }))
      setEditing(false)
      toast.success('이름이 변경되었습니다.')
    } catch {
      toast.error('이름 변경 실패')
    }
  }

  const handleDeleteConfirm = async () => {
    try {
      await client.delete('/auth/delete')
      toast.success('회원탈퇴가 완료되었습니다.')
      localStorage.clear()
      navigate('/')
      window.location.reload()
    } catch {
      toast.error('회원탈퇴 실패')
      setShowDeleteModal(false)
    }
  }

  if (loading || !user) return (
    <div className="p-8 text-center text-muted-foreground">Loading...</div>
  )

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">프로필</h1>
        <p className="text-muted-foreground text-sm mt-1">계정 정보를 확인하고 관리하세요</p>
      </div>

      {/* 기본 정보 */}
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          <div>
            {editing ? (
              <div className="flex items-center gap-2">
                <Input
                  ref={inputRef}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleUpdateUsername() }}
                  className="text-lg font-semibold max-w-[200px]"
                  autoFocus
                />
                <Button size="sm" onClick={handleUpdateUsername}>저장</Button>
                <Button size="sm" variant="outline" onClick={() => { setUsername(user.username); setEditing(false) }}>취소</Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold">{user.username}</h2>
                <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                  이름 수정
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Mail className="w-4 h-4 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">이메일</p>
                <p className="text-foreground">{user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Calendar className="w-4 h-4 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">가입일</p>
                <p className="text-foreground">{new Date(user.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 초대 목록 */}
      {inviteError && (
          <Card>
              <CardContent className="pt-6 text-sm text-destructive">{inviteError}</CardContent>
          </Card>
      )}
      {inviteLoading ? null : invitations.length > 0 && (
          <Card>
              <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      받은 초대
                  </CardTitle>
                  <CardDescription>워크스페이스 초대 요청입니다.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                  {invitations.map((inv) => (
                      <div key={inv.group_id} className="flex items-center justify-between rounded-lg border p-3">
                          <div>
                              <p className="text-sm font-medium">{inv.group_name}</p>
                              <p className="text-xs text-muted-foreground">
                                  {inv.owner_username} · {inv.role}
                                  {inv.invited_at && ` · ${new Date(inv.invited_at).toLocaleDateString('ko-KR')}`}
                              </p>
                          </div>
                          <div className="flex gap-2">
                              <Button size="sm" onClick={() => handleAccept(inv.group_id)}>
                                  수락
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => handleDecline(inv.group_id)}>
                                  거절
                              </Button>
                          </div>
                      </div>
                  ))}
              </CardContent>
          </Card>
      )}

      {/* 계정 설정 */}
      <Card>
        <CardHeader>
          <CardTitle>계정 설정</CardTitle>
          <CardDescription>계정 및 보안 관리</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            className="w-full gap-2"
            onClick={() => setShowDeleteModal(true)}
          >
            <LogOut className="w-4 h-4" />
            회원탈퇴
          </Button>
        </CardContent>
      </Card>

      <ConfirmModal
        open={showDeleteModal}
        message={'정말로 회원탈퇴를 하시겠습니까?\n탈퇴 후 계정 정보는 복구할 수 없습니다.'}
        confirmLabel="탈퇴하기"
        cancelLabel="취소"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteModal(false)}
      />
    </div>
  )
}
