import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Mail } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../../../features/auth'
import { updateEmail } from '../../../features/auth/api/authApi'
import { sendVerificationCode, verifyCode } from '../../../features/auth/api/emailApi'

export default function EmailSection() {
  const { user, setUser } = useAuth()
  const [step, setStep] = useState(1)
  const [newEmail, setNewEmail] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const handleCancel = () => {
    setStep(1)
    setNewEmail('')
    setCode('')
    setErrorMsg('')
  }

  const handleSendCode = async () => {
    if (!newEmail) return setErrorMsg("새 이메일을 입력해주세요.")
    setLoading(true)
    setErrorMsg('')
    try {
      await sendVerificationCode(newEmail)
      setStep(3)
    } catch (error) {
      const errorMessage = error.message || "이메일 전송에 실패했습니다."
      setErrorMsg(errorMessage.replace("Error: ", ""))
    } finally {
      setLoading(false)
    }
  }

  const handleFinalUpdate = async () => {
    setLoading(true)
    setErrorMsg('')
    try {
      await verifyCode(newEmail, code)
      const updatedUser = await updateEmail(newEmail)
      setUser(updatedUser)
      toast.success("이메일이 변경되었습니다.")
      handleCancel()
    } catch (error) {
      setErrorMsg(error.response?.data?.detail?.message || "인증에 실패했습니다.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-none rounded-xl overflow-hidden">
      <CardHeader className="py-4 px-6 border-b border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-900/50">
        <CardTitle className="text-sm font-bold flex items-center gap-2 text-zinc-700 dark:text-zinc-300 uppercase tracking-tight">
          <Mail size={16} className="text-blue-500" /> 이메일
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        {step === 1 ? (
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase">현재 계정</p>
              <div className="flex items-center gap-2">
                <span className="text-sm font-black text-zinc-800 dark:text-zinc-200">{user?.email}</span>
                <Badge variant="outline" className="h-5 px-1.5 text-[10px] border-emerald-500/20 text-emerald-600 bg-emerald-50/30 dark:bg-emerald-500/10 uppercase">인증됨</Badge>
              </div>
            </div>
            <Button variant="outline" onClick={() => setStep(2)} className="h-9 px-4 text-xs font-bold border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 active:scale-95">변경</Button>
          </div>
        ) : step === 2 ? (
          <div className="space-y-1 animate-in fade-in duration-300">
            <label className="text-[11px] font-bold text-zinc-400 uppercase ml-1">새 주소</label>
            <div className="flex gap-2 items-start">
              <div className="flex-1 relative">
                <Input
                  value={newEmail}
                  onChange={(e) => {
                    setNewEmail(e.target.value)
                    if (errorMsg) setErrorMsg('')
                  }}
                  placeholder="example@email.com"
                  className="h-10 rounded-lg dark:bg-zinc-900 shadow-none border-zinc-200 dark:border-zinc-800 focus-visible:ring-zinc-200"
                />
                {errorMsg && (
                  <p className="text-[11px] text-red-500 font-medium absolute mt-1 ml-1">
                    {errorMsg}
                  </p>
                )}
              </div>
              <div className="flex gap-2 shrink-0 pt-0.5">
                <Button variant="ghost" onClick={handleCancel} className="h-9 px-4 text-xs font-bold text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all active:scale-95">
                  취소
                </Button>
                <Button variant="outline" onClick={handleSendCode} disabled={loading} className="h-9 px-4 text-xs font-bold border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-all active:scale-95">
                  {loading ? '전송 중' : '전송'}
                </Button>
              </div>
            </div>
            {errorMsg && <div className="h-5" />}
          </div>
        ) : (
          <div className="space-y-1 animate-in slide-in-from-right-2 duration-300">
            <label className="text-[11px] font-bold text-zinc-400 uppercase ml-1">인증</label>
            <div className="flex gap-2 items-start">
              <div className="flex-1 relative">
                <Input
                  value={code}
                  onChange={(e) => {
                    setCode(e.target.value)
                    if (errorMsg) setErrorMsg('')
                  }}
                  placeholder="전송된 6자리 인증코드를 입력하여 검증해주세요"
                  maxLength={6}
                  className="h-10 rounded-lg dark:bg-zinc-900 shadow-none border-zinc-200 dark:border-zinc-800 text-center font-bold tracking-widest"
                />
                {errorMsg && (
                  <p className="text-[11px] text-red-500 font-medium absolute mt-1 ml-1">
                    {errorMsg}
                  </p>
                )}
              </div>
              <div className="flex gap-2 shrink-0 pt-0.5">
                <Button variant="ghost" onClick={handleCancel} className="h-10 px-4 font-bold text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all active:scale-95">
                  취소
                </Button>
                <Button variant="outline" onClick={handleFinalUpdate} disabled={loading} className="h-10 rounded-lg border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 font-bold px-5 transition-all active:scale-95">
                  {loading ? '확인 중' : '확인'}
                </Button>
              </div>
            </div>
            {errorMsg && <div className="h-5" />}
          </div>
        )}
      </CardContent>
    </Card>
  )
}