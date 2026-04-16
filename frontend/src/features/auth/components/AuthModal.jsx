import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui/Dialog'
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
    login:          '로그인하여 스마트한 법률 상담을 시작해보세요.',
    signup:         '지금 가입하고 더 편리한 분석을 경험하세요.',
    confirmAccount: '가입하신 정보를 확인하여 계정을 찾아드릴게요.',
    resetPassword:  '본인 인증 후 비밀번호를 재설정해 주세요.',
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-[400px] p-8 rounded-[24px] border-none shadow-2xl overflow-hidden bg-background">
        <DialogHeader className="space-y-1 mb-4">
          <DialogTitle>
            {titles[view]}
          </DialogTitle>
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
