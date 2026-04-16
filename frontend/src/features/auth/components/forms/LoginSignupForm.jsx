import { Button } from '@/shared/ui/Button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/ui/Dialog'
import { Input } from '@/shared/ui/Input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/lib/utils'
import { AlertCircle, CheckCircle2, Info, Lock, Mail, User, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getErrorMessageByCode } from '@/shared/lib/errors'
import { reactivateAccount } from '../../api/authApi.js'
import { sendVerificationCode, verifyCode } from '../../api/emailApi.js'
import { useAuth } from '../../context/AuthContext.jsx'

const LOGIN_INIT = { email: '', password: '' }
const SIGNUP_INIT = { username: '', email: '', password: '', confirmPassword: '' }
const EMAIL_VERIFY_INIT = {
  codeSent: false, code: '', verified: false,
  sending: false, verifying: false, error: '', success: '',
}

export default function LoginSignupForm({ view, setView, onClose }) {
  const { login, signup } = useAuth()
  const isLogin = view === 'login'

  const [initialEmail, setInitialEmail] = useState('')
  const [form, setForm] = useState(isLogin ? LOGIN_INIT : SIGNUP_INIT)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [emailVerify, setEmailVerify] = useState(EMAIL_VERIFY_INIT)
  const firstInputRef = useRef(null)

  const [showReactivateModal, setShowReactivateModal] = useState(false)
  const [pendingCredentials, setPendingCredentials] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const errCode = params.get('error')
    const emailParam = params.get('email')
    const actionParam = params.get('action')

    if (errCode === 'not_registered' || actionParam === 'signup') {
      if (emailParam) {
        const decodedEmail = decodeURIComponent(emailParam)
        setInitialEmail(decodedEmail)
      }
      setView('signup')

      params.delete('error')
      params.delete('message')
      params.delete('email')
      params.delete('action')
      const newUrl = window.location.pathname + (params.toString() ? `?${params.toString()}` : '')
      window.history.replaceState({}, '', newUrl)
    } else if (errCode === 'account_inactive') {
      setError('비활성화된 계정이거나 탈퇴 대기 중인 계정입니다. 로그인으로 복구를 시도해주세요.')
    } else if (errCode === 'social_auth_failed') {
      setError('소셜 로그인 정보 조회에 실패했습니다.')
    }
  }, [setView])

  useEffect(() => {
    setForm(isLogin ? { ...LOGIN_INIT } : { ...SIGNUP_INIT, email: initialEmail || '' })
    setError('')

    if (!isLogin && initialEmail) {
      setEmailVerify({ ...EMAIL_VERIFY_INIT, verified: true, success: '소셜 계정 인증이 완료된 이메일입니다.' })
    } else {
      setEmailVerify(EMAIL_VERIFY_INIT)
    }

    firstInputRef.current?.focus()
  }, [isLogin, initialEmail])

  const onChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setError('')
  }

  const handleSendCode = async () => {
    if (!form.email) {
      setError('이메일을 입력해주세요.')
      return
    }
    setEmailVerify((prev) => ({ ...prev, sending: true, error: '', success: '' }))
    try {
      await sendVerificationCode(form.email)
      setEmailVerify((prev) => ({ ...prev, codeSent: true, sending: false, success: '인증번호가 발송되었습니다.' }))
      setError('')
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '인증번호 발송에 실패했습니다.'))
      setEmailVerify((prev) => ({ ...prev, sending: false }))
    }
  }

  const handleVerifyCode = async () => {
    if (!emailVerify.code) {
      setError('인증번호를 입력해주세요.')
      return
    }
    setEmailVerify((prev) => ({ ...prev, verifying: true, error: '', success: '' }))
    try {
      await verifyCode(form.email, emailVerify.code)
      setEmailVerify((prev) => ({ ...prev, verifying: false, verified: true, success: '이메일 인증이 완료되었습니다.' }))
      setError('')
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '인증번호가 올바르지 않습니다.'))
      setEmailVerify((prev) => ({ ...prev, verifying: false }))
    }
  }

  const validate = () => {
    if (!form.email) return '이메일을 입력해주세요.'
    if (!form.password || form.password.length < 8) return '비밀번호는 8자 이상이어야 합니다.'
    if (!isLogin) {
      if (!form.username || form.username.trim().length < 2) return '이름은 2자 이상이어야 합니다.'
      if (!emailVerify.verified) return '이메일 인증을 완료해주세요.'
      if (!form.confirmPassword) return '비밀번호 확인을 입력해주세요.'
      if (form.password !== form.confirmPassword) return '비밀번호가 일치하지 않습니다.'
    }
    return ''
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    const message = validate()
    if (message) { setError(message); return }
    setLoading(true)
    try {
      if (isLogin) {
        await login({ email: form.email, password: form.password })
        onClose()
      } else {
        const isSocial = !!initialEmail
        const autoLogged = await signup({
          username: form.username,
          email: form.email,
          password: form.password,
          autoLogin: isSocial
        })

        if (autoLogged) {
          onClose()
        } else {
          window.location.href = '/'
        }
      }
    } catch (err) {
      if (err.code === 'USER_010' || err.response?.data?.code === 'USER_010') {
        setPendingCredentials({ email: form.email, password: form.password })
        setShowReactivateModal(true)
      } else {
        setError(getErrorMessageByCode(err.code, err.message || '요청 처리 중 오류가 발생했습니다.'))
      }
    } finally {
      setLoading(false)
    }
  }

  const handleReactivateConfirm = async () => {
    if (!pendingCredentials) return
    try {
      await reactivateAccount(pendingCredentials)
      window.location.reload()
    } catch {
      setError("계정 복구에 실패했습니다.")
      setShowReactivateModal(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {!isLogin && (
          <div className="flex flex-col gap-1.5 animate-in fade-in duration-300">
            <Label htmlFor="auth-username" className="text-[12px] font-semibold text-muted-foreground ml-1">이름</Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
              <Input
                id="auth-username"
                ref={firstInputRef}
                className="pl-9 h-11  bg-muted/5 focus:ring-0 focus:border-muted-foreground/40 transition-colors duration-200 placeholder:text-muted-foreground/40 shadow-none text-foreground"
                value={form.username || ''}
                onChange={(e) => onChange('username', e.target.value)}
                disabled={loading}
                autoComplete="name"
                placeholder="홍길동"
              />
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="auth-email" className="text-[12px] font-semibold text-muted-foreground ml-1">이메일</Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
              <Input
                id="auth-email"
                ref={isLogin ? firstInputRef : null}
                type="email"
                className={cn(
                  "pl-9 h-11 bg-muted/5 focus:ring-0 focus:border-muted-foreground/40 transition-colors duration-200 placeholder:text-muted-foreground/40 shadow-none text-foreground",
                  !isLogin && emailVerify.verified && "pr-10"
                )}
                value={form.email}
                onChange={(e) => {
                  onChange('email', e.target.value)
                  if (!isLogin) setEmailVerify(EMAIL_VERIFY_INIT)
                }}
                disabled={loading || (!isLogin && emailVerify.verified)}
                autoComplete="email"
                placeholder="example@email.com"
              />
              {!isLogin && emailVerify.verified && (
                <CheckCircle2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-600" />
              )}
            </div>
            {!isLogin && !emailVerify.verified && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSendCode}
                disabled={emailVerify.sending || !form.email.trim()}
                className="shrink-0 h-11 px-4 font-bold border-muted-foreground/40 bg-muted/5 hover:bg-muted/10 text-muted-foreground transition-all duration-300"
              >
                {emailVerify.sending ? (
                  <span className="animate-pulse">...</span>
                ) : emailVerify.codeSent ? (
                  '재발송'
                ) : (
                  '인증요청'
                )}
              </Button>
            )}
          </div>
          {!isLogin && emailVerify.codeSent && !emailVerify.verified && (
            <div className="flex flex-col gap-2 mt-1 animate-in slide-in-from-top-1 duration-300">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
                  <Input
                    className="pl-9 h-11 bg-muted/5 focus:ring-0 focus:border-muted-foreground/40 shadow-none text-foreground font-medium"
                    value={emailVerify.code}
                    onChange={(e) => setEmailVerify((prev) => ({ ...prev, code: e.target.value, error: '' }))}
                    placeholder="인증번호"
                    maxLength={6}
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleVerifyCode}
                  disabled={emailVerify.verifying || !emailVerify.code.trim()}
                  className="shrink-0 h-11 px-6 font-bold bg-indigo-500/75 hover:bg-indigo-500/85 dark:bg-indigo-600/60 dark:hover:bg-indigo-600/70 text-white shadow-none transition-all duration-300"
                >
                  {emailVerify.verifying ? <span className="animate-pulse">...</span> : '확인'}
                </Button>
              </div>
              {error && (
                <div className="bg-destructive/10 p-2 rounded-lg flex items-start gap-2 animate-in slide-in-from-top-1 duration-200">
                  <AlertCircle className="w-3.5 h-3.5 text-destructive mt-0.5 shrink-0" />
                  <p className="text-[12px] font-bold text-destructive leading-tight">{error}</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="auth-password" className="text-[12px] font-semibold text-muted-foreground ml-1">비밀번호</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
            <Input
              id="auth-password"
              type="password"
              className="pl-9 h-11  bg-muted/5 focus:ring-0 focus:border-muted-foreground/40 transition-colors duration-200 placeholder:text-muted-foreground/40 shadow-none text-foreground"
              value={form.password}
              onChange={(e) => onChange('password', e.target.value)}
              disabled={loading}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              placeholder="8자 이상 영문, 숫자 조합"
            />
          </div>
        </div>

        {!isLogin && (
          <div className="flex flex-col gap-1.5 animate-in fade-in duration-300">
            <Label htmlFor="auth-confirm-password" className="text-[12px] font-semibold text-muted-foreground ml-1">비밀번호 확인</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
              <Input
                id="auth-confirm-password"
                type="password"
                className="pl-9 h-11  bg-muted/5 focus:ring-0 focus:border-muted-foreground/40 transition-colors duration-200 placeholder:text-muted-foreground/40 shadow-none text-foreground"
                value={form.confirmPassword || ''}
                onChange={(e) => onChange('confirmPassword', e.target.value)}
                disabled={loading}
                autoComplete="new-password"
                placeholder="비밀번호 재입력"
              />
            </div>
          </div>
        )}

        {error && (isLogin || !emailVerify.codeSent || emailVerify.verified) && (
          <div className="bg-destructive/10 p-2 rounded-lg flex items-start gap-2 animate-in slide-in-from-top-1 duration-200">
            <AlertCircle className="w-3.5 h-3.5 text-destructive mt-0.5 shrink-0" />
            <p className="text-[12px] font-bold text-destructive leading-tight">{error}</p>
          </div>
        )}

        <Button
          type="submit"
          disabled={loading || (!isLogin && !emailVerify.verified)}
          className="w-full h-11 text-base font-bold mt-1 bg-indigo-500/80 hover:bg-indigo-500/90 dark:bg-indigo-600/70 dark:hover:bg-indigo-600/80 text-white shadow-none transition-all active:scale-[0.99]"
        >
          {loading ? <span className="animate-pulse">...</span> : isLogin ? '로그인' : '가입하기'}
        </Button>
      </form>

      {isLogin && (
        <div className="flex flex-col gap-6 mt-2">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t text-[#868e96]" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase font-black tracking-widest text-muted-foreground/100">
              <span className="bg-background px-3">또는</span>
            </div>
          </div>

          <div className="flex justify-center gap-6 px-2">
            <Button
              type="button"
              variant="outline"
              className="w-11 h-11 rounded-full p-0  bg-muted/5 hover:border-muted-foreground/40 hover:bg-muted/10 transition-all shadow-none"
              onClick={() => window.location.href = `/api/auth/social/google/login`}
            >
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.91c1.71-1.58 2.69-3.9 2.69-6.62z" fill="#4285F4" />
                <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.8.54-1.83.85-3.05.85-2.34 0-4.32-1.58-5.03-3.71H.95v2.3A8.99 8.99 0 0 0 9 18z" fill="#34A853" />
                <path d="M3.97 10.71A5.41 5.41 0 0 1 3.68 9c0-.59.1-1.17.29-1.71V4.99H.95A8.99 8.99 0 0 0 0 9c0 1.45.35 2.82.95 4.01l3.02-2.3z" fill="#FBBC05" />
                <path d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0 5.48 0 2.39 2.02.95 4.99l3.02 2.3c.71-2.13 2.69-3.71 5.03-3.71z" fill="#EA4335" />
              </svg>
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-11 h-11 rounded-full p-0  bg-muted/5 hover:border-muted-foreground/40 hover:bg-muted/10 transition-all shadow-none"
              onClick={() => window.location.href = `/api/auth/social/github/login`}
            >
              <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" className="text-muted-foreground">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
            </Button>
          </div>

          <div className="flex flex-col gap-6 mt-2">
            <div className="flex justify-center gap-8 text-[12.5px] font-bold text-muted-foreground/80">
              <button type="button" className="cursor-pointer hover:text-foreground transition-colors" onClick={() => setView('confirmAccount')}>
                계정 찾기
              </button>
              <span className="text-muted/30">|</span>
              <button type="button" className="cursor-pointer hover:text-foreground transition-colors" onClick={() => setView('resetPassword')}>
                비밀번호 재설정
              </button>
            </div>

            <div className="flex justify-center items-center gap-2 border-t border-muted/40 text-[13.5px]">
              <span className="text-muted-foreground/70 font-medium">
                {isLogin ? '처음이신가요?' : '이미 회원이신가요?'}
              </span>
              <button
                type="button"
                className="cursor-pointer font-black text-indigo-600/90 dark:text-indigo-400/90 hover:underline underline-offset-4 decoration-2"
                onClick={() => setView(isLogin ? 'signup' : 'login')}
                disabled={loading}
              >
                {isLogin ? '무료 회원가입' : '로그인하기'}
              </button>
            </div>
          </div>
        </div>
      )}

      {!isLogin && (
        <div className="flex justify-center items-center gap-2 pt-6 border-t border-muted/40 text-[13.5px]">
          <span className="text-muted-foreground/70 font-medium">이미 회원이신가요?</span>
          <button
            type="button"
            className="cursor-pointer font-black text-indigo-600/90 dark:text-indigo-400/90 hover:underline underline-offset-4 decoration-2"
            onClick={() => setView('login')}
            disabled={loading}
          >
            로그인하기
          </button>
        </div>
      )}

      <Dialog open={showReactivateModal} onOpenChange={setShowReactivateModal}>
        <DialogContent className="max-w-[380px] p-8 rounded-[24px] border-none shadow-2xl bg-background">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3 text-lg font-bold text-foreground/90">
              <div className="w-10 h-10 rounded-full bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center">
                <Info className="w-5 h-5 text-amber-600" />
              </div>
              계정 복구 안내
            </DialogTitle>
            <DialogDescription className="py-4 text-[15px] leading-relaxed text-foreground/80 font-bold">
              현재 탈퇴 대기 중인 계정입니다.<br />
              로그인하시면 가입 정보가 즉시 복구됩니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-3 mt-2">
            <Button variant="outline" onClick={() => setShowReactivateModal(false)} className="h-11 flex-1 rounded-xl  text-muted-foreground font-bold shadow-none">
              취소
            </Button>
            <Button onClick={handleReactivateConfirm} className="h-11 flex-[1.5] rounded-xl bg-indigo-500/90 hover:bg-indigo-500 text-white shadow-none font-black">
              복구하고 로그인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
