import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { User2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../../../features/auth'
import { updateUsername } from '../../../features/auth/api/authApi'

export default function ProfileSection() {
  const { user, setUser } = useAuth()
  const [isEditing, setIsEditing] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (user) setNewUsername(user.username)
  }, [user, isEditing])

  const handleCancel = () => {
    setIsEditing(false)
    setNewUsername(user?.username || '')
    setErrorMsg('')
  }

  const handleUsernameUpdate = async () => {
    if (!newUsername.trim() || newUsername === user?.username) {
      setIsEditing(false)
      return
    }
    setIsUpdating(true)
    setErrorMsg('')
    try {
      const updatedUser = await updateUsername(newUsername)
      setUser(updatedUser)
      toast.success("이름 변경 완료")
      setIsEditing(false)
   } catch (error) {
      const rawMessage = error.message || ""
      let displayMsg = "이름 변경에 실패했습니다."

      if (rawMessage.includes("at most 10 characters")) {
        displayMsg = "이름은 최대 10자까지만 가능합니다."
      } else if (rawMessage) {
        displayMsg = rawMessage.replace("Error: ", "")
      }

      setErrorMsg(displayMsg)
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <Card className="border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-none rounded-xl overflow-hidden">
      <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-900/50">
        <CardTitle className="text-sm font-bold flex items-center gap-2 text-zinc-700 dark:text-zinc-300 uppercase tracking-tight">
          <User2 size={16} className="text-blue-500" /> 기본 프로필
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        {!isEditing ? (
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-[11px] font-bold text-zinc-400 uppercase ml-1">이름</p>
              <p className="text-sm font-black text-zinc-800 dark:text-zinc-200 ml-1">{user?.username}</p>
            </div>
            <Button
              variant="outline"
              onClick={() => setIsEditing(true)}
              className="h-9 px-4 text-xs font-bold border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 active:scale-95"
            >
              변경
            </Button>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row gap-2 items-start animate-in fade-in duration-200">
            <div className="flex-1 space-y-1 relative">
              <p className="text-[11px] font-bold text-zinc-400 uppercase ml-1">새 이름</p>
              <Input
                value={newUsername}
                onChange={(e) => {
                  setNewUsername(e.target.value)
                  if (errorMsg) setErrorMsg('')
                }}
                autoFocus
                className="h-9 text-sm rounded-lg border-zinc-200 dark:border-zinc-800 dark:bg-zinc-900 focus-visible:ring-zinc-100"
              />
              {errorMsg && (
                <p className="text-[11px] text-red-500 font-medium absolute mt-1 ml-1">
                  {errorMsg}
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0 pt-[18px]">
              <Button
                variant="ghost"
                onClick={handleCancel}
                className="h-9 px-4 text-xs font-bold text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all active:scale-95"
              >
                취소
              </Button>
              <Button
                variant="outline"
                onClick={handleUsernameUpdate}
                disabled={isUpdating}
                className="h-9 px-4 text-xs font-bold border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 active:scale-95"
              >
                {isUpdating ? '저장 중' : '저장'}
              </Button>
            </div>
          </div>
        )}
        {isEditing && errorMsg && <div className="h-5" />}
      </CardContent>
    </Card>
  )
}