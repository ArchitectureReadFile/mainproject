import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/card'
import { Dialog, DialogContent, DialogDescription } from '@/shared/ui/Dialog'
import { Input } from '@/shared/ui/Input'
import { cn } from '@/shared/lib/utils'
import { AlertCircle, AlertTriangle, ArrowLeft, Check, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../features/auth'
import { deactivateAccount } from '../../../features/auth/api/authApi'
import { sendVerificationCode, verifyCode } from '../../../features/auth/api/emailApi'

const EMAIL_VERIFY_INIT = {
  codeSent: false, code: '', verified: false,
  sending: false, verifying: false, error: '',
}

export default function WithdrawalSection() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [emailVerify, setEmailVerify] = useState(EMAIL_VERIFY_INIT)
  const [withdrawalError, setWithdrawalError] = useState('')
  const [isWithdrawDialogOpen, setIsWithdrawDialogOpen] = useState(false)
  const [step, setStep] = useState(1)

  const hasSocialLinked = user?.social_providers?.length > 0;

  const handleModalOpenChange = (open) => {
    setIsWithdrawDialogOpen(open)
    if (!open) {
      setTimeout(() => {
        setEmailVerify(EMAIL_VERIFY_INIT)
        setWithdrawalError('')
        setStep(1)
      }, 300)
    }
  }

  const handleSendCode = async () => {
    if (!user?.email) return
    setEmailVerify((prev) => ({ ...prev, sending: true, error: '' }))
    try {
      await sendVerificationCode(user.email)
      setEmailVerify((prev) => ({ ...prev, codeSent: true, sending: false }))
      setStep(2)
    } catch {
      setEmailVerify((prev) => ({ ...prev, sending: false, error: '인증번호 발송에 실패했습니다. 다시 시도해주세요.' }))
    }
  }

  const handleVerifyCode = async () => {
    if (!emailVerify.code || emailVerify.code.length < 6) {
      setEmailVerify((prev) => ({ ...prev, error: '인증번호 6자리를 모두 입력해주세요.' }))
      return
    }
    setEmailVerify((prev) => ({ ...prev, verifying: true, error: '' }))
    try {
      await verifyCode(user.email, emailVerify.code)
      setEmailVerify((prev) => ({ ...prev, verifying: false, verified: true }))
      setStep(3)
    } catch {
      setEmailVerify((prev) => ({ ...prev, verifying: false, error: '인증번호가 올바르지 않습니다.' }))
    }
  }

  const handleWithdrawal = async () => {
    setWithdrawalError('')
    try {
      await deactivateAccount()
      setStep(4)
    } catch (error) {
      console.error('Withdrawal failed:', error)
      let errorMessage = error.response?.data?.detail?.message || error.message || "회원 탈퇴 처리에 실패했습니다."
      if (errorMessage.startsWith('Error: ')) {
        errorMessage = errorMessage.replace('Error: ', '')
      }
      setWithdrawalError(errorMessage)
    }
  }

  const handleFinalExit = (action) => {
    setUser(null)
    setIsWithdrawDialogOpen(false)
    if (action === 'signup') {
      navigate('/?action=signup', { replace: true })
    } else {
      navigate('/', { replace: true })
    }
  }

  return (
    <>
      <div className="space-y-6 pt-24">
        <div className="flex items-center gap-2 px-2">
          <div className="h-px flex-1 bg-zinc-200 dark:bg-slate-800" />
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest">위험 구역</span>
          <div className="h-px flex-1 bg-zinc-200 dark:bg-slate-800" />
        </div>

        <Card className="border-red-200 dark:border-red-900/20 rounded-2xl shadow-sm overflow-hidden border bg-white dark:bg-slate-900">
          <div className="p-6 bg-red-50/30 dark:bg-red-900/10 flex flex-col items-center text-center gap-4 w-full">
            <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center shrink-0">
              <AlertTriangle size={24} className="text-red-600 dark:text-red-500" />
            </div>
            <div>
              <h4 className="text-lg font-black text-red-600 dark:text-red-500 mb-2">회원 탈퇴</h4>
              {hasSocialLinked ? (
                <p className="text-sm text-red-500/80 dark:text-red-400/80 leading-relaxed font-medium">
                  소셜 로그인이 연동되어 있습니다.<br className="hidden md:block" />
                  안전한 정보 파기를 위해 <strong className="dark:text-red-400">소셜 연동을 모두 해제</strong>한 후 다시 시도해주세요.
                </p>
              ) : (
                <p className="text-sm text-red-500/80 dark:text-red-400/80 leading-relaxed font-medium">
                  계정을 삭제하면 개인 정보와 상담 내역은 영구 삭제되지만, <br className="hidden md:block" />
                  워크스페이스의 <strong className="dark:text-red-400">공유 데이터는 익명화되어 보존</strong>되며 복구할 수 없습니다.
                </p>
              )}
            </div>
            <div className="mt-4 flex justify-center w-full">
              <Button
                variant="destructive"
                onClick={() => setIsWithdrawDialogOpen(true)}
                disabled={hasSocialLinked}
                className="rounded-xl font-bold px-8 h-12 shadow-lg shadow-red-100 dark:shadow-none bg-red-500 hover:bg-red-600 transition-all hover:scale-[1.02] active:scale-[0.98] w-full md:w-auto flex items-center gap-2 disabled:opacity-50 disabled:pointer-events-none"
              >
                <Trash2 size={18} />
                탈퇴 절차 진행하기
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <Dialog open={isWithdrawDialogOpen} onOpenChange={handleModalOpenChange}>
        <DialogContent
          className="sm:max-w-[440px] p-0 overflow-hidden border-zinc-200 dark:border-slate-800"
          onInteractOutside={(e) => e.preventDefault()}
        >
          {step > 1 && (
            <button
              onClick={() => setStep(step - 1)}
              className="absolute left-4 top-4 z-50 opacity-70 transition-opacity hover:opacity-100 text-zinc-500 hover:text-zinc-900 dark:text-slate-400 dark:hover:text-slate-100 focus:outline-none"
            >
              <ArrowLeft className="h-4 w-4" strokeWidth={2.5} />
            </button>
          )}

          <div className="px-8 pt-8 pb-6 bg-zinc-50 dark:bg-slate-900/50 border-b border-zinc-100 dark:border-slate-800">
            <div className="flex items-center justify-between max-w-[320px] mx-auto relative">
              <div className="flex flex-col items-center relative z-10">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300",
                  step > 1 ? "bg-blue-600 text-white" :
                    step === 1 ? "bg-blue-600 text-white ring-4 ring-blue-100 dark:ring-blue-900/30" :
                      "bg-zinc-200 text-zinc-500 dark:bg-slate-800 dark:text-slate-400"
                )}>
                  {step > 1 ? <Check size={18} strokeWidth={3} /> : "1"}
                </div>
                <span className={cn("text-[11px] font-bold mt-2.5 absolute -bottom-6 w-max transition-colors",
                  step >= 1 ? "text-blue-600 dark:text-blue-500" : "text-zinc-400"
                )}>
                  이메일 확인
                </span>
              </div>

              <div className={cn("flex-1 h-1 mx-1 rounded-full transition-colors duration-300",
                step >= 2 ? "bg-blue-600" : "bg-zinc-200 dark:bg-slate-800"
              )} />

              <div className="flex flex-col items-center relative z-10">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300",
                  step > 2 ? "bg-blue-600 text-white" :
                    step === 2 ? "bg-blue-600 text-white ring-4 ring-blue-100 dark:ring-blue-900/30" :
                      "bg-zinc-200 text-zinc-500 dark:bg-slate-800 dark:text-slate-400"
                )}>
                  {step > 2 ? <Check size={18} strokeWidth={3} /> : "2"}
                </div>
                <span className={cn("text-[11px] font-bold mt-2.5 absolute -bottom-6 w-max transition-colors",
                  step >= 2 ? "text-blue-600 dark:text-blue-500" : "text-zinc-400"
                )}>
                  인증번호
                </span>
              </div>

              <div className={cn("flex-1 h-1 mx-1 rounded-full transition-colors duration-300",
                step >= 3 ? "bg-red-500" : "bg-zinc-200 dark:bg-slate-800"
              )} />

              <div className="flex flex-col items-center relative z-10">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300",
                  step > 3 ? "bg-red-500 text-white" :
                    step === 3 ? "bg-red-500 text-white ring-4 ring-red-100 dark:ring-red-900/30" :
                      "bg-zinc-200 text-zinc-500 dark:bg-slate-800 dark:text-slate-400"
                )}>
                  {step > 3 ? <Check size={18} strokeWidth={3} /> : "3"}
                </div>
                <span className={cn("text-[11px] font-bold mt-2.5 absolute -bottom-6 w-max transition-colors",
                  step >= 3 ? "text-red-600 dark:text-red-500" : "text-zinc-400"
                )}>
                  최종 승인
                </span>
              </div>

              <div className={cn("flex-1 h-1 mx-1 rounded-full transition-colors duration-300",
                step >= 4 ? "bg-green-500" : "bg-zinc-200 dark:bg-slate-800"
              )} />

              <div className="flex flex-col items-center relative z-10">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300",
                  step === 4 ? "bg-green-500 text-white ring-4 ring-green-100 dark:ring-green-900/30" :
                    "bg-zinc-200 text-zinc-500 dark:bg-slate-800 dark:text-slate-400"
                )}>
                  4
                </div>
                <span className={cn("text-[11px] font-bold mt-2.5 absolute -bottom-6 w-max transition-colors",
                  step === 4 ? "text-green-600 dark:text-green-500" : "text-zinc-400"
                )}>
                  완료
                </span>
              </div>
            </div>
          </div>

          <div className="pt-6 pb-2">
            {step === 1 && (
              <div className="flex flex-col animate-in fade-in zoom-in-95 duration-200">
                <div className="text-center mb-6">
                  <DialogDescription className="text-sm font-medium text-zinc-500 dark:text-slate-400">
                    안전한 탈퇴 처리를 위해 가입하신 이메일로<br />본인 확인을 진행합니다.
                  </DialogDescription>
                </div>

                <div className="px-6 pb-6 space-y-6">
                  <div className="space-y-2.5">
                    <label className="text-xs font-bold text-zinc-500 dark:text-slate-400 pl-1">계정 이메일</label>
                    <Input
                      value={user?.email || ''}
                      disabled
                      className="bg-zinc-50 dark:bg-slate-800/50 text-zinc-500 h-12 rounded-xl text-center font-medium"
                    />
                  </div>

                  {emailVerify.error && (
                    <div className="flex items-center justify-center gap-1.5 text-sm font-bold text-red-500 dark:text-red-400">
                      <AlertTriangle size={16} /> {emailVerify.error}
                    </div>
                  )}

                  <Button
                    onClick={handleSendCode}
                    disabled={emailVerify.sending}
                    className="w-full h-12 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white text-base shadow-sm"
                  >
                    {emailVerify.sending ? '인증번호 발송 중...' : '인증번호 발송하기'}
                  </Button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col animate-in slide-in-from-right-8 duration-300 relative">
                <div className="text-center mb-6">
                  <DialogDescription className="text-sm font-medium text-zinc-500 dark:text-slate-400">
                    이메일로 발송된 6자리 인증번호를 입력해주세요.
                  </DialogDescription>
                </div>

                <div className="px-6 pb-6 space-y-6">
                  <Input
                    value={emailVerify.code}
                    onChange={(e) => setEmailVerify((prev) => ({ ...prev, code: e.target.value.replace(/[^0-9]/g, ''), error: '' }))}
                    placeholder="000000"
                    maxLength={6}
                    className="h-16 rounded-xl text-center tracking-[1em] text-2xl font-black bg-zinc-50 dark:bg-slate-800/50 focus-visible:ring-blue-500 border-zinc-200 dark:border-slate-700 placeholder:text-zinc-300 dark:placeholder:text-slate-700"
                  />

                  {emailVerify.error && (
                    <div className="flex items-center justify-center gap-1.5 text-sm font-bold text-red-500 dark:text-red-400">
                      <AlertTriangle size={16} /> {emailVerify.error}
                    </div>
                  )}

                  <div className="space-y-4 pt-2">
                    <Button
                      onClick={handleVerifyCode}
                      disabled={emailVerify.verifying || emailVerify.code.length < 6}
                      className="w-full h-12 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white text-base shadow-sm transition-all active:scale-[0.98]"
                    >
                      {emailVerify.verifying ? '확인 중...' : '인증 완료하기'}
                    </Button>

                    <div className="text-center">
                      <button
                        onClick={handleSendCode}
                        disabled={emailVerify.sending}
                        className="text-xs font-bold text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400 underline underline-offset-4 transition-colors"
                      >
                        {emailVerify.sending ? '재발송 중...' : '인증번호 재발송'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col animate-in slide-in-from-right-8 duration-300">
                <div className="text-center mb-6">
                  <DialogDescription className="text-sm font-medium text-red-500/80 dark:text-red-400/80">
                    마지막 단계입니다.<br />정말로 계정을 삭제하시겠습니까?
                  </DialogDescription>
                </div>

                <div className="px-6 pb-6 space-y-8">
                  <div className="bg-zinc-50 dark:bg-slate-800/50 border border-zinc-200 dark:border-slate-700 rounded-xl p-5 text-left shadow-sm">
                    <h5 className="font-bold text-zinc-800 dark:text-slate-200 mb-3 flex items-center gap-2">
                      <AlertTriangle size={18} className="text-amber-500" /> 꼭 알아두세요
                    </h5>
                    <ul className="list-disc list-inside text-sm text-zinc-600 dark:text-slate-400 space-y-2.5">
                      <li>탈퇴 승인 즉시 계정은 <strong className="font-bold text-zinc-900 dark:text-slate-100">비활성화 상태</strong>로 전환됩니다.</li>
                      <li>비활성화 시점으로부터 <strong className="font-bold text-zinc-900 dark:text-slate-100">7일간의 유예 기간</strong>이 주어집니다.</li>
                      <li>유예 기간 내에 다시 로그인하시면 탈퇴가 자동 취소됩니다.</li>
                      <li>7일 경과 후 다음 데이터가 <strong className="font-bold underline">영구 삭제</strong>됩니다:
                        <div className="mt-2 ml-5 p-3 bg-zinc-100/50 dark:bg-slate-800/30 rounded-lg space-y-1 text-[13px] text-zinc-500 dark:text-slate-500 font-medium">
                          <p>• 계정 프로필 및 소셜 로그인 연동 정보</p>
                          <p>• 개인용 AI 상담 및 모든 대화 기록</p>
                          <p>• 구독 상태 및 수신한 모든 알림 내역</p>
                          <p>• 파일 내보내기(Export) 요청 기록</p>
                        </div>
                      </li>
                      <li className="text-[12px] opacity-80 italic">※ 공유 워크스페이스에 남긴 문서나 댓글은 삭제되지 않으며 '알 수 없음'으로 익명화됩니다.</li>
                    </ul>
                  </div>

                  {withdrawalError && (
                    <div className="bg-destructive/10 p-2 rounded-lg flex items-start gap-2 animate-in slide-in-from-top-1 duration-200">
                      <AlertCircle className="w-3.5 h-3.5 text-destructive mt-0.5 shrink-0" />
                      <p className="text-[12px] font-bold text-destructive leading-tight whitespace-pre-line">{withdrawalError}</p>
                    </div>
                  )}

                  <Button
                    variant="destructive"
                    onClick={handleWithdrawal}
                    className="w-full h-12 rounded-xl font-bold text-base bg-red-500 hover:bg-red-600 shadow-md shadow-red-100 dark:shadow-none"
                  >
                    최종 탈퇴 승인
                  </Button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="flex flex-col animate-in zoom-in-95 duration-300 text-center px-6 pb-8">
                <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Check size={40} className="text-green-600 dark:text-green-500" />
                </div>
                
                <h3 className="text-xl font-black text-zinc-800 dark:text-slate-100 mb-3">탈퇴 처리가 완료되었습니다</h3>
                <p className="text-sm font-medium text-zinc-500 dark:text-slate-400 leading-relaxed mb-8">
                  그동안 서비스를 이용해 주셔서 감사합니다.<br />
                  <strong className="text-zinc-900 dark:text-slate-200">7일의 유예 기간이 지난 후</strong> 모든 데이터가 영구 삭제됩니다.
                </p>

                <div className="grid grid-cols-2 gap-3 w-full">
                  <Button
                    variant="outline"
                    onClick={() => handleFinalExit('home')}
                    className="h-12 rounded-xl font-bold border-zinc-200 dark:border-slate-700 hover:bg-zinc-50 dark:hover:bg-slate-800"
                  >
                    홈으로 가기
                  </Button>
                  <Button
                    onClick={() => handleFinalExit('signup')}
                    className="h-12 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 dark:shadow-none"
                  >
                    새로 가입하기
                  </Button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
