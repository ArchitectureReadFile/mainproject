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
          ? 'bg-[#020426] text-white'
          : 'text-gray-700 hover:bg-slate-100 hover:text-gray-900'
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

  if (!open) return null

  return (
    <>
      {/* 오버레이 */}
      <div
        className="fixed inset-0 z-[35] bg-slate-600/45"
        onClick={onClose}
      />

      {/* 드로어 */}
      <aside className="fixed top-0 right-0 z-40 h-dvh w-[min(86vw,320px)] bg-white border-l border-slate-200 shadow-xl overflow-y-auto">

        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <h3 className="m-0 text-lg font-bold text-slate-900">메뉴</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="flex items-center justify-center p-1 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-900 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* 프로필 */}
        <div className="border-b border-slate-200 py-2">
          <MenuItem
            to="/mypage"
            icon={<User size={18} />}
            label={isAuthenticated ? user?.username || '프로필' : '프로필'}
            active={location.pathname.startsWith('/mypage')}
            onClick={isAuthenticated ? onClose : onOpenLogin}
          />
        </div>

        {/* 비로그인 */}
        {!isAuthenticated && (
          <div className="border-b border-slate-200 py-2">
            <button
              type="button"
              onClick={onOpenLogin}
              className="flex items-center gap-3 w-full px-5 py-3 text-[0.9375rem] font-medium text-gray-700 hover:bg-slate-100 hover:text-gray-900 transition-colors"
            >
              <LogIn size={18} />
              <span>로그인</span>
            </button>
            <button
              type="button"
              onClick={onOpenSignup}
              className="flex items-center gap-3 w-full px-5 py-3 text-[0.9375rem] font-medium text-gray-700 hover:bg-slate-100 hover:text-gray-900 transition-colors"
            >
              <UserPlus size={18} />
              <span>회원가입</span>
            </button>
          </div>
        )}

        {/* 워크스페이스 */}
        {isAuthenticated && (
          <div className="border-b border-slate-200 py-2">
            <p className="mx-5 my-2 text-xs font-semibold text-slate-500 tracking-wide">워크스페이스</p>
            <MenuItem
              to="/workspace"
              icon={<FolderOpen size={18} />}
              label="워크스페이스"
              active={location.pathname.startsWith('/workspace')}
              onClick={onClose}
            />
          </div>
        )}

        {/* 홈 */}
        <div className="border-b border-slate-200 py-2">
          <MenuItem
            to="/"
            icon={<Home size={18} />}
            label="홈"
            active={location.pathname === '/'}
            onClick={onClose}
          />
        </div>

        {/* 관리자 */}
        {isAuthenticated && user?.role === 'ADMIN' && (
          <div className="border-b border-slate-200 py-2">
            <p className="mx-5 my-2 text-xs font-semibold text-slate-500 tracking-wide">관리자</p>
            <MenuItem
              to="/admin"
              icon={<Shield size={18} />}
              label="관리자 페이지"
              active={location.pathname.startsWith('/admin')}
              onClick={onClose}
            />
          </div>
        )}

        {/* 로그아웃 */}
        {isAuthenticated && (
          <div className="py-2">
            <button
              type="button"
              onClick={async () => {
                const loggedOut = await onLogout()
                if (loggedOut !== false) onClose()
              }}
              className="flex items-center gap-3 w-full px-5 py-3 text-[0.9375rem] font-medium text-gray-700 hover:bg-red-50 hover:text-red-600 transition-colors"
            >
              <LogOut size={18} />
              <span>로그아웃</span>
            </button>
          </div>
        )}
      </aside>
    </>
  )
}