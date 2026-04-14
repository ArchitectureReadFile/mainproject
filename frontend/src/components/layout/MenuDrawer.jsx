import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
} from '@/components/ui/Sheet'
import { cn } from '@/lib/utils'
import { FolderOpen, Home, LogIn, LogOut, Shield, UserPlus, X } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'

const AVATAR_COLORS = [
  'bg-red-500', 'bg-orange-500', 'bg-amber-500',
  'bg-emerald-500', 'bg-teal-500', 'bg-cyan-500',
  'bg-sky-500', 'bg-blue-500', 'bg-indigo-500',
  'bg-violet-500', 'bg-purple-500', 'bg-pink-500', 'bg-rose-500'
]

const getAvatarColor = (seed) => {
  if (!seed) return 'bg-zinc-800'
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function MenuItem({ to, icon, label, active, onClick, isButton = false, className }) {
  const content = (
    <>
      <span className="shrink-0 transition-transform duration-200 group-active:scale-90">
        {icon}
      </span>
      <span className="flex-1 text-left truncate">{label}</span>
    </>
  )

  const commonClasses = cn(
    'group flex items-center gap-3 px-4 py-3 text-[0.9375rem] font-medium transition-all duration-200',
    active
      ? 'bg-accent text-foreground shadow-sm'
      : 'text-muted-foreground hover:bg-accent hover:text-foreground active:scale-[0.98]',
    'rounded-lg mx-3 w-[calc(100%-1.5rem)]',
    className
  )

  if (isButton) {
    return (
      <button onClick={onClick} className={cn('border-none bg-transparent cursor-pointer', commonClasses)}>
        {content}
      </button>
    )
  }

  return (
    <Link to={to} onClick={onClick} className={cn('no-underline', commonClasses)}>
      {content}
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

  const avatarBgColor = useMemo(() => {
    return getAvatarColor(user?.email || user?.username || 'guest')
  }, [user])

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="p-0 flex flex-col overflow-x-hidden h-full">
        <SheetHeader className="px-6 pt-6 pb-2 border-b-0 shrink-0 flex flex-row items-center justify-between">
          <SheetDescription className="sr-only">
            사이드 메뉴입니다.
          </SheetDescription>
          <span className="text-[0.65rem] font-black tracking-[0.3em] text-muted-foreground/50 uppercase select-none">
            Readfile
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="닫기"
            className="rounded-full hover:bg-accent -mr-2"
          >
            <X size={18} />
          </Button>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto overflow-x-hidden pt-1 pb-4 flex flex-col gap-1">
          {isAuthenticated && user && (
            <>
              <Link 
                to="/mypage" 
                onClick={onClose}
                className="group px-5 py-5 mx-3 mb-2 flex items-center gap-4 hover:bg-accent/50 rounded-2xl transition-all no-underline border border-transparent active:scale-[0.98]"
              >
                <Avatar className="size-12 border-2 border-background shadow-md shrink-0 transition-transform group-hover:scale-105">
                  <AvatarImage src={user.profileImage} alt={user.username} />
                  <AvatarFallback className={cn('text-white text-lg font-bold shadow-inner', avatarBgColor)}>
                    {(user.username || user.email || '?').charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex flex-col min-w-0">
                  <span className="font-bold text-foreground truncate group-hover:text-primary transition-colors text-base">
                    {user.username || '사용자'}
                  </span>
                  <span className="text-[0.7rem] text-muted-foreground truncate uppercase tracking-wider">프로필 보기</span>
                </div>
              </Link>
              <Separator className="mx-6 mb-4 opacity-30" />
            </>
          )}

          <div className="flex flex-col gap-1">
            <MenuItem
              to="/"
              icon={<Home size={20} />}
              label="홈"
              active={location.pathname === '/'}
              onClick={onClose}
            />

            {isAuthenticated && (
              <MenuItem
                to="/workspace"
                icon={<FolderOpen size={20} />}
                label="워크스페이스"
                active={location.pathname.startsWith('/workspace')}
                onClick={onClose}
              />
            )}
          </div>

          {isAuthenticated && user?.role === 'ADMIN' && (
            <>
              <div className="px-7 pt-4 pb-2">
                <p className="text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground/60">System</p>
              </div>
              <MenuItem
                to="/admin"
                icon={<Shield size={20} />}
                label="관리자 페이지"
                active={location.pathname.startsWith('/admin')}
                onClick={onClose}
              />
            </>
          )}
        </div>

        <div className="shrink-0 flex flex-col overflow-hidden bg-background border-t border-border/40">
          {!isAuthenticated ? (
            <div className="flex flex-col">
              <MenuItem
                isButton
                onClick={onOpenLogin}
                icon={<LogIn size={20} />}
                label="로그인"
                className="mx-0 w-full rounded-none px-7 h-14"
              />
              <MenuItem
                isButton
                onClick={onOpenSignup}
                icon={<UserPlus size={20} />}
                label="회원가입"
                className="mx-0 w-full rounded-none px-7 h-14"
              />
            </div>
          ) : (
            <MenuItem
              isButton
              onClick={async () => {
                const loggedOut = await onLogout()
                if (loggedOut !== false) onClose()
              }}
              icon={<LogOut size={20} />}
              label="로그아웃"
              className="mx-0 w-full rounded-none px-7 h-14 text-destructive hover:bg-destructive/10 active:bg-destructive/15 transition-colors"
            />
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
