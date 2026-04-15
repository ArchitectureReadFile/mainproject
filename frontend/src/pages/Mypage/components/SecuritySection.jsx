import { Button } from '@/shared/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/Input'
import { Lock } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { updatePassword } from '../../../features/auth/api/authApi'
import WithdrawalSection from './WithdrawalSection'

export default function SecuritySection() {
  const [step, setStep] = useState(1)
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '', confirm_new_password: '' })
  const [errorMsg, setErrorMsg] = useState('')

  const handlePasswordUpdate = async () => {
    if (pwForm.new_password !== pwForm.confirm_new_password) {
      return setErrorMsg("새 비밀번호 확인이 일치하지 않습니다.")
    }
    
    setErrorMsg('')
    try {
      await updatePassword(pwForm)
      toast.success("비밀번호가 변경되었습니다.")
      setPwForm({ current_password: '', new_password: '', confirm_new_password: '' })
      setStep(1)
    } catch (error) {
      const rawMessage = error.message || ""
      
      if (rawMessage.includes("at least 8 characters")) {
        setErrorMsg("비밀번호는 최소 8자 이상이어야 합니다.")
      } else if (rawMessage.includes("Invalid") || rawMessage.includes("current password")) {
        setErrorMsg("현재 비밀번호가 일치하지 않습니다.")
      } else {
        setErrorMsg(rawMessage.replace("Error: ", ""))
      }
    }
  }

  return (
    <div className="space-y-12">
      <Card className="border-zinc-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-none rounded-xl overflow-hidden">
       <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-slate-900 bg-zinc-50/50 dark:bg-slate-900/50">
          <CardTitle className="text-sm font-bold flex items-center gap-3 text-zinc-700 dark:text-slate-300 uppercase tracking-tight">
            <div className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
              <Lock size={14} className="text-zinc-600 dark:text-slate-400" />
            </div>
            비밀번호
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          {step === 1 ? (
            <div className="flex items-center justify-between animate-in fade-in duration-300">
              <div className="space-y-1">
                <p className="text-[11px] font-bold text-zinc-400 dark:text-slate-500 uppercase">암호 </p>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-black text-zinc-800 dark:text-slate-200">••••••••••••••••••••••••••</span>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={() => setStep(2)}
                className="rounded-lg h-9 px-4 text-xs font-bold border-zinc-200 dark:border-slate-800 hover:bg-zinc-50 dark:bg-slate-900 dark:hover:bg-slate-800 transition-all active:scale-95"
              >
                변경
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-6 animate-in slide-in-from-right-2 duration-300">
              <div className="w-full sm:max-w-md space-y-4">
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-zinc-400 uppercase ml-1">현재 비밀번호</label>
                  <Input
                    type="password"
                    value={pwForm.current_password}
                    onChange={(e) => {
                      setPwForm({ ...pwForm, current_password: e.target.value })
                      if (errorMsg.includes("현재")) setErrorMsg('')
                    }}
                    className="h-10 rounded-lg dark:bg-slate-900 shadow-none border-zinc-200 dark:border-slate-800"
                    placeholder="현재 비밀번호를 입력하세요"
                  />
                  {errorMsg.includes("현재") && (
                    <p className="text-[11px] font-medium text-red-500 mt-1 ml-1">{errorMsg}</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-zinc-400 uppercase ml-1">새 비밀번호</label>
                  <Input
                    type="password"
                    value={pwForm.new_password}
                    onChange={(e) => {
                        setPwForm({ ...pwForm, new_password: e.target.value })
                        if (errorMsg.includes("최소")) setErrorMsg('')
                    }}
                    className="h-10 rounded-lg dark:bg-slate-900 shadow-none border-zinc-200 dark:border-slate-800"
                  />
                  {errorMsg.includes("최소") && (
                    <p className="text-[11px] font-medium text-red-500 mt-1 ml-1">{errorMsg}</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-zinc-400 uppercase ml-1">새 비밀번호 확인</label>
                  <Input
                    type="password"
                    value={pwForm.confirm_new_password}
                    onChange={(e) => {
                      setPwForm({ ...pwForm, confirm_new_password: e.target.value })
                      if (errorMsg.includes("확인")) setErrorMsg('')
                    }}
                    className="h-10 rounded-lg dark:bg-slate-900 shadow-none border-zinc-200 dark:border-slate-800"
                  />
                  {errorMsg.includes("확인") && (
                    <p className="text-[11px] font-medium text-red-500 mt-1 ml-1">{errorMsg}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setStep(1)
                    setErrorMsg('')
                  }}
                  className="h9 px-4 text-xs font-bold text-zinc-400 hover:text-zinc-900 dark:hover:text-slate-100 transition-all active:scale-95"
                >
                  이전
                </Button>
                <Button
                  variant="outline"
                  onClick={handlePasswordUpdate}
                  className="h-9 px-4 text-xs font-bold rounded-lg border-zinc-200 dark:border-slate-800 hover:bg-zinc-50 dark:bg-slate-900 dark:hover:bg-slate-800 transition-all active:scale-95"
                >
                  변경 완료
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <WithdrawalSection />
    </div>
  )
}
