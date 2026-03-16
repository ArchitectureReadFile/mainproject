import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { FolderOpen, Home, LogIn, LogOut, Shield, User, UserPlus, X } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

function MenuItem({ to, icon, label, active, onClick }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 px-5 py-3 text-[0.9375rem] font-medium no-underline transition-colors rounded-l-lg',
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-foreground hover:bg-accent hover:text-accent-foreground'
      )}
    >
      {icon}
      <span>{label}</span>
    </Link>
  )
}

export default function MenuDrawer({
  open,
  onClose,
  isAuthenticated,
  user,
  onOpenLogin,
  onOpenSignup,
  onLogout,
}) {
  const location = useLocation()

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>메뉴</SheetTitle>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="닫기">
            <X size={20} />
          </Button>
        </SheetHeader>

        <div className="py-2">
          <MenuItem
            to="/mypage"
            icon={<User size={18} />}
            label={isAuthenticated ? user?.username || '프로필' : '프로필'}
            active={location.pathname.startsWith('/mypage')}
            onClick={isAuthenticated ? onClose : onOpenLogin}
          />
        </div>

        <Separator />

        {!isAuthenticated && (
          <>
            <div className="py-2">
              <Button
                variant="ghost"
                className="flex items-center gap-3 w-full justify-start px-5 h-12 text-[0.9375rem] font-medium rounded-none"
                onClick={onOpenLogin}
              >
                <LogIn size={18} />
                <span>로그인</span>
              </Button>
              <Button
                variant="ghost"
                className="flex items-center gap-3 w-full justify-start px-5 h-12 text-[0.9375rem] font-medium rounded-none"
                onClick={onOpenSignup}
              >
                <UserPlus size={18} />
                <span>회원가입</span>
              </Button>
            </div>
            <Separator />
          </>
        )}

        {isAuthenticated && (
          <>
            <div className="py-2">
              <p className="mx-5 my-2 text-xs font-semibold text-muted-foreground tracking-wide">워크스페이스</p>
              <MenuItem
                to="/workspace"
                icon={<FolderOpen size={18} />}
                label="워크스페이스"
                active={location.pathname.startsWith('/workspace')}
                onClick={onClose}
              />
            </div>
            <Separator />
          </>
        )}

        <div className="py-2">
          <MenuItem
            to="/"
            icon={<Home size={18} />}
            label="홈"
            active={location.pathname === '/'}
            onClick={onClose}
          />
        </div>

        {isAuthenticated && user?.role === 'ADMIN' && (
          <>
            <Separator />
            <div className="py-2">
              <p className="mx-5 my-2 text-xs font-semibold text-muted-foreground tracking-wide">관리자</p>
              <MenuItem
                to="/admin"
                icon={<Shield size={18} />}
                label="관리자 페이지"
                active={location.pathname.startsWith('/admin')}
                onClick={onClose}
              />
            </div>
          </>
        )}

        {isAuthenticated && (
          <>
            <Separator />
            <div className="py-2">
              <Button
                variant="ghost"
                className="flex items-center gap-3 w-full justify-start px-5 h-12 text-[0.9375rem] font-medium rounded-none hover:bg-destructive/10 hover:text-destructive"
                onClick={async () => {
                  const loggedOut = await onLogout()
                  if (loggedOut !== false) onClose()
                }}
              >
                <LogOut size={18} />
                <span>로그아웃</span>
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}