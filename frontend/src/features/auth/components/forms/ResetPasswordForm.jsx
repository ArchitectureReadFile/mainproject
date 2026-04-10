import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { Mail, ShieldCheck, Lock, ChevronLeft, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { getErrorMessageByCode } from '../../../../lib/errors'
import { resetPassword } from '../../api/authApi'
import { sendVerificationCode, verifyCode } from '../../api/emailApi'

const EMAIL_VERIFY_INIT = {
  codeSent: false, code: '', verified: false,
  sending: false, verifying: false, error: '', success: '',
};

export default function ResetPasswordForm({ setView }) {
  const [resetEmail, setResetEmail] = useState('')
  const [resetNewPassword, setResetNewPassword] = useState('')
  const [emailVerify, setEmailVerify] = useState(EMAIL_VERIFY_INIT)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const onSendCode = async () => {
    setError('')
    if (!resetEmail.trim()) { setError('이메일을 입력해주세요.'); return }
    setEmailVerify((prev) => ({ ...prev, sending: true, error: '', success: '' }))
    try {
      await sendVerificationCode(resetEmail)
      setEmailVerify((prev) => ({ ...prev, codeSent: true, sending: false, success: '인증번호가 발송되었습니다.' }))
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '발송에 실패했습니다.'))
      setEmailVerify((prev) => ({ ...prev, sending: false }))
    }
  }

  const onVerifyCode = async () => {
    setError('')
    if (!emailVerify.code.trim()) { setError('인증번호를 입력해주세요.'); return }
    setEmailVerify((prev) => ({ ...prev, verifying: true }))
    try {
      await verifyCode(resetEmail, emailVerify.code)
      setEmailVerify((prev) => ({ ...prev, verifying: false, verified: true }))
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '인증번호가 일치하지 않습니다.'))
      setEmailVerify((prev) => ({ ...prev, verifying: false }))
    }
  }

  const onResetPassword = async (e) => {
    e.preventDefault()
    setError('')
    if (!resetNewPassword || resetNewPassword.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.')
      return
    }
    setLoading(true)
    try {
      await resetPassword(resetEmail, resetNewPassword)
      toast.success('비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요.')
      setView('login')
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '비밀번호 변경에 실패했습니다.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 py-0.5">
      <form onSubmit={onResetPassword} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-email" className="text-[12px] font-semibold text-muted-foreground ml-1">이메일 주소</Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
              <Input
                id="reset-email"
                ref={inputRef}
                type="email"
                className="pl-9 h-11 bg-muted/5 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-muted-foreground/40 shadow-none text-foreground"
                value={resetEmail}
                onChange={(e) => {
                  setResetEmail(e.target.value)
                  setEmailVerify(EMAIL_VERIFY_INIT)
                }}
                disabled={loading || emailVerify.verified}
                placeholder="example@email.com"
              />
              {emailVerify.verified && (
                <CheckCircle2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-600 animate-in zoom-in duration-300" />
              )}
            </div>
            {!emailVerify.verified && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onSendCode}
                disabled={emailVerify.sending || emailVerify.verified || !resetEmail.trim()}
                className="shrink-0 h-11 px-4 font-bold bg-muted/5 hover:bg-muted/10 text-muted-foreground transition-all duration-300 border-muted-foreground/40"
              >
                {emailVerify.verified ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                ) : emailVerify.sending ? (
                  <span className="animate-pulse">...</span>
                ) : emailVerify.codeSent ? (
                  '재발송'
                ) : (
                  '인증요청'
                )}
              </Button>
            )}
          </div>
        </div>

        {emailVerify.codeSent && !emailVerify.verified && (
          <div className="flex flex-col gap-1.5 animate-in fade-in slide-in-from-top-2 duration-300">
            <Label htmlFor="verification-code" className="text-[12px] font-semibold text-muted-foreground ml-1">인증번호</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
                <Input
                  id="verification-code"
                  type="text"
                  className="pl-9 h-11 bg-muted/5 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-muted-foreground/40 shadow-none text-foreground font-medium"
                  value={emailVerify.code}
                  onChange={(e) => setEmailVerify((prev) => ({ ...prev, code: e.target.value, error: '' }))}
                  disabled={loading || emailVerify.verifying}
                  placeholder="6자리 숫자"
                  maxLength={6}
                />
              </div>
              <Button
                type="button"
                onClick={onVerifyCode}
                disabled={emailVerify.verifying || !emailVerify.code.trim()}
                className="shrink-0 h-11 px-6 font-bold bg-indigo-500/75 hover:bg-indigo-500/85 dark:bg-indigo-600/60 dark:hover:bg-indigo-600/70 text-white shadow-none transition-all duration-300"
              >
                {emailVerify.verifying ? <span className="animate-pulse">...</span> : '확인'}
              </Button>
            </div>
          </div>
        )}

        {emailVerify.verified && (
          <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-top-2 duration-500">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reset-new-password" className="text-[12px] font-semibold text-muted-foreground ml-1">새로운 비밀번호</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
                <Input
                  id="reset-new-password"
                  type="password"
                  className="pl-9 h-11 bg-muted/5 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-muted-foreground/40 shadow-none text-foreground"
                  value={resetNewPassword}
                  onChange={(e) => setResetNewPassword(e.target.value)}
                  disabled={loading}
                  placeholder="8자 이상 영문, 숫자 조합"
                  autoFocus
                />
              </div>
            </div>

            <Button 
              type="submit" 
              disabled={loading} 
              className="w-full h-11 text-base font-bold mt-1 bg-indigo-500/80 hover:bg-indigo-500/90 dark:bg-indigo-600/70 dark:hover:bg-indigo-600/80 text-white shadow-none transition-all active:scale-[0.99]"
            >
              {loading ? <span className="animate-pulse">...</span> : '비밀번호 변경하기'}
            </Button>
          </div>
        )}

        {error && (
          <div className="bg-destructive/10 p-2.5 rounded-lg flex items-start gap-2 animate-in slide-in-from-top-1 duration-200">
            <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
            <p className="text-[13px] font-bold text-destructive leading-tight">{error}</p>
          </div>
        )}

        <div className="pt-6 border-t border-muted/40">
          <Button
            type="button"
            variant="ghost"
            className="w-full text-muted-foreground/70 hover:text-foreground gap-2 h-10 text-[13px] font-bold transition-all duration-300"
            onClick={() => setView('login')}
            disabled={loading}
          >
            <ChevronLeft className="w-4 h-4" />
            로그인으로 돌아가기
          </Button>
        </div>
      </form>
    </div>
  );
}
