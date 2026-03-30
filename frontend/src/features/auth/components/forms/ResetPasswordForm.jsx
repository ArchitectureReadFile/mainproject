import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { getErrorMessageByCode } from '../../../../lib/errors'
import { resetPassword } from '../../api/authApi'
import { sendVerificationCode, verifyCode } from '../../api/emailApi'

export default function ResetPasswordForm({ setView }) {
  const [resetEmail, setResetEmail] = useState('')
  const [resetNewPassword, setResetNewPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [isCodeSent, setIsCodeSent] = useState(false)
  const [isVerified, setIsVerified] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const onSendCode = async () => {
    setError('')
    if (!resetEmail.trim()) { setError('이메일을 입력해주세요.'); return }
    setLoading(true)
    try {
      await sendVerificationCode(resetEmail)
      setIsCodeSent(true)
      toast.success('인증번호가 발송되었습니다.')
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '발송에 실패했습니다.'))
    } finally {
      setLoading(false)
    }
  }

  const onVerifyCode = async () => {
    setError('')
    if (!verificationCode.trim()) { setError('인증번호를 입력해주세요.'); return }
    setLoading(true)
    try {
      await verifyCode(resetEmail, verificationCode)
      setIsVerified(true)
      toast.success('인증이 완료되었습니다.')
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || '인증번호가 일치하지 않습니다.'))
    } finally {
      setLoading(false)
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
    <form onSubmit={onResetPassword} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reset-email">이메일 주소</Label>
        <div className="flex gap-2">
          <Input
            id="reset-email"
            ref={inputRef}
            type="email"
            value={resetEmail}
            onChange={(e) => setResetEmail(e.target.value)}
            disabled={loading || isVerified}
            placeholder="example@email.com"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onSendCode}
            disabled={loading || isVerified || !resetEmail}
            className="shrink-0"
          >
            {isCodeSent ? '재발송' : '번호발송'}
          </Button>
        </div>
      </div>

      {isCodeSent && !isVerified && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="verification-code">인증번호 확인</Label>
          <div className="flex gap-2">
            <Input
              id="verification-code"
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              disabled={loading}
              placeholder="6자리 숫자 입력"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onVerifyCode}
              disabled={loading || !verificationCode}
              className="shrink-0"
            >
              확인
            </Button>
          </div>
        </div>
      )}

      {isVerified && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-new-password">새로운 비밀번호</Label>
          <Input
            id="reset-new-password"
            type="password"
            value={resetNewPassword}
            onChange={(e) => setResetNewPassword(e.target.value)}
            disabled={loading}
            placeholder="8자 이상 영문, 숫자 조합"
          />
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" disabled={!isVerified || loading} className="w-full">
        {loading ? '처리 중...' : '비밀번호 변경하기'}
      </Button>

      <Button
        type="button"
        variant="ghost"
        className="w-full text-muted-foreground"
        onClick={() => setView('login')}
        disabled={loading}
      >
        로그인으로 돌아가기
      </Button>
    </form>
  )
}
