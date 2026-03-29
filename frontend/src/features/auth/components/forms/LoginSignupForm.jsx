import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { useEffect, useRef, useState } from 'react'
import { getErrorMessageByCode } from '../../../../lib/errors'
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

  const [form, setForm] = useState(isLogin ? LOGIN_INIT : SIGNUP_INIT)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [emailVerify, setEmailVerify] = useState(EMAIL_VERIFY_INIT)
  const firstInputRef = useRef(null)

  useEffect(() => {
    setForm(isLogin ? LOGIN_INIT : SIGNUP_INIT)
    setError('')
    setEmailVerify(EMAIL_VERIFY_INIT)
    firstInputRef.current?.focus()
  }, [isLogin])

  const onChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setError('')
  }

  const handleSendCode = async () => {
    if (!form.email) {
      setEmailVerify((prev) => ({ ...prev, error: '이메일을 입력해주세요.' }))
      return
    }
    setEmailVerify((prev) => ({ ...prev, sending: true, error: '', success: '' }))
    try {
      await sendVerificationCode(form.email)
      setEmailVerify((prev) => ({ ...prev, codeSent: true, sending: false, success: '인증번호가 발송되었습니다.' }))
    } catch {
      setEmailVerify((prev) => ({ ...prev, sending: false, error: '인증번호 발송에 실패했습니다.' }))
    }
  }

  const handleVerifyCode = async () => {
    if (!emailVerify.code) {
      setEmailVerify((prev) => ({ ...prev, error: '인증번호를 입력해주세요.' }))
      return
    }
    setEmailVerify((prev) => ({ ...prev, verifying: true, error: '', success: '' }))
    try {
      await verifyCode(form.email, emailVerify.code)
      setEmailVerify((prev) => ({ ...prev, verifying: false, verified: true, success: '이메일 인증이 완료되었습니다.' }))
    } catch {
      setEmailVerify((prev) => ({ ...prev, verifying: false, error: '인증번호가 올바르지 않습니다.' }))
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
      } else {
        await signup({ username: form.username, email: form.email, password: form.password })
      }
      onClose()
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '요청 처리 중 오류가 발생했습니다.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {!isLogin && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="auth-username">이름</Label>
            <Input
              id="auth-username"
              ref={firstInputRef}
              value={form.username || ''}
              onChange={(e) => onChange('username', e.target.value)}
              disabled={loading}
              autoComplete="name"
              placeholder="홍길동"
            />
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="auth-email">이메일</Label>
          <div className="flex gap-2">
            <Input
              id="auth-email"
              ref={isLogin ? firstInputRef : null}
              type="email"
              value={form.email}
              onChange={(e) => {
                onChange('email', e.target.value)
                if (!isLogin) setEmailVerify(EMAIL_VERIFY_INIT)
              }}
              disabled={loading || (!isLogin && emailVerify.verified)}
              autoComplete="email"
              placeholder="example@email.com"
            />
            {!isLogin && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSendCode}
                disabled={emailVerify.sending || emailVerify.verified}
                className="shrink-0"
              >
                {emailVerify.verified ? '인증 완료' : emailVerify.sending ? '발송 중...' : emailVerify.codeSent ? '재발송' : '인증'}
              </Button>
            )}
          </div>
          {!isLogin && emailVerify.codeSent && !emailVerify.verified && (
            <div className="flex gap-2 mt-1">
              <Input
                value={emailVerify.code}
                onChange={(e) => setEmailVerify((prev) => ({ ...prev, code: e.target.value, error: '' }))}
                placeholder="인증번호 6자리"
                maxLength={6}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleVerifyCode}
                disabled={emailVerify.verifying}
                className="shrink-0"
              >
                {emailVerify.verifying ? '확인 중...' : '확인'}
              </Button>
            </div>
          )}
          {!isLogin && emailVerify.error && (
            <p className="text-xs text-destructive">{emailVerify.error}</p>
          )}
          {!isLogin && emailVerify.success && (
            <p className="text-xs text-success">{emailVerify.success}</p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="auth-password">비밀번호</Label>
          <Input
            id="auth-password"
            type="password"
            value={form.password}
            onChange={(e) => onChange('password', e.target.value)}
            disabled={loading}
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            placeholder="8자 이상 영문, 숫자 조합"
          />
        </div>

        {!isLogin && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="auth-confirm-password">비밀번호 확인</Label>
            <Input
              id="auth-confirm-password"
              type="password"
              value={form.confirmPassword || ''}
              onChange={(e) => onChange('confirmPassword', e.target.value)}
              disabled={loading}
              autoComplete="new-password"
              placeholder="비밀번호를 다시 입력해주세요"
            />
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? '처리 중...' : isLogin ? '이메일로 로그인' : '회원가입'}
        </Button>
      </form>

      {isLogin && (
        <>
          <div className="relative my-1">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs text-muted-foreground">
              <span className="bg-background px-2">또는</span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Button type="button" variant="outline" className="w-full gap-2">
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.91c1.71-1.58 2.69-3.9 2.69-6.62z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.8.54-1.83.85-3.05.85-2.34 0-4.32-1.58-5.03-3.71H.95v2.3A8.99 8.99 0 0 0 9 18z" fill="#34A853"/>
                <path d="M3.97 10.71A5.41 5.41 0 0 1 3.68 9c0-.59.1-1.17.29-1.71V4.99H.95A8.99 8.99 0 0 0 0 9c0 1.45.35 2.82.95 4.01l3.02-2.3z" fill="#FBBC05"/>
                <path d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0 5.48 0 2.39 2.02.95 4.99l3.02 2.3c.71-2.13 2.69-3.71 5.03-3.71z" fill="#EA4335"/>
              </svg>
              Google로 계속하기
            </Button>
            <Button type="button" variant="outline" className="w-full gap-2">
              <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
              </svg>
              GitHub으로 계속하기
            </Button>
          </div>

          <div className="flex justify-center gap-3 text-xs text-muted-foreground">
            <button type="button" className="hover:text-foreground" onClick={() => setView('confirmAccount')}>
              가입 정보 확인
            </button>
            <span>|</span>
            <button type="button" className="hover:text-foreground" onClick={() => setView('resetPassword')}>
              비밀번호 재설정
            </button>
          </div>
        </>
      )}

      <div className="flex justify-center items-center gap-2 text-sm pt-2 border-t">
        <span className="text-muted-foreground">
          {isLogin ? '계정이 없으신가요?' : '이미 계정이 있으신가요?'}
        </span>
        <button
          type="button"
          className="font-medium hover:underline"
          onClick={() => setView(isLogin ? 'signup' : 'login')}
          disabled={loading}
        >
          {isLogin ? '회원가입' : '로그인'}
        </button>
      </div>
    </div>
  )
}
