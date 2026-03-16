import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useEffect, useState } from 'react'
import ConfirmAccountForm from './forms/ConfirmAccountForm.jsx'
import LoginSignupForm from './forms/LoginSignupForm.jsx'
import ResetPasswordForm from './forms/ResetPasswordForm.jsx'

export default function AuthModal({ mode, open, onClose }) {
  const [view, setView] = useState(mode)

  useEffect(() => {
    if (open) setView(mode)
  }, [open, mode])

  const titles = {
    login:          '로그인',
    signup:         '회원가입',
    confirmAccount: '가입 정보 확인',
    resetPassword:  '비밀번호 재설정',
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{titles[view]}</DialogTitle>
        </DialogHeader>

        {(view === 'login' || view === 'signup') && (
          <LoginSignupForm view={view} setView={setView} onClose={onClose} />
        )}
        {view === 'confirmAccount' && (
          <ConfirmAccountForm setView={setView} />
        )}
        {view === 'resetPassword' && (
          <ResetPasswordForm setView={setView} />
        )}
      </DialogContent>
    </Dialog>
  )
}