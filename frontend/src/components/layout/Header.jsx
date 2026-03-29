import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/Button'
import { useTheme } from '@/hooks/useTheme'
import { LogIn, Menu, Moon, Scale, Sun, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthModal, useAuth } from '../../features/auth/index.js'
import MenuDrawer from './MenuDrawer.jsx'

export default function Header() {
  const {
    user,
    isAuthenticated,
    isBootstrapping,
    logout,
    authModalOpen,
    authModalMode,
    openAuthModal,
    closeAuthModal,
  } = useAuth()

  const { theme, toggle } = useTheme()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const showUserChip = !isBootstrapping && isAuthenticated

  const openLogin = () => {
    setMenuOpen(false)
    openAuthModal('login')
  }

  const openSignup = () => {
    setMenuOpen(false)
    openAuthModal('signup')
  }

  const handleLogoClick = (e) => {
    if (pathname === '/') {
      e.preventDefault()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      navigate('/')
    }
  }

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur-sm">
        <div className="max-w-[1100px] mx-auto px-5 py-3.5 flex items-center justify-between gap-3">

          <Link to="/" onClick={handleLogoClick} className="no-underline text-inherit min-w-0">
            <div className="flex items-center gap-2.5">
              <Scale className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="m-0 text-lg font-extrabold leading-tight text-foreground">판례 AI 플랫폼</p>
                <p className="m-0 mt-0.5 text-xs text-muted-foreground hidden sm:block">Legal AI Platform</p>
              </div>
            </div>
          </Link>

          <div className="flex items-center gap-2 shrink-0">
            {showUserChip ? (
              <Badge variant="secondary" className="hidden sm:inline-flex">
                {user?.username || '사용자'}
              </Badge>
            ) : (
              <Button variant="outline" size="sm" onClick={openLogin} className="gap-1.5">
                <LogIn size={15} />
                로그인
              </Button>
            )}

            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label={theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환'}
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-label={menuOpen ? '메뉴 닫기' : '메뉴 열기'}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </Button>
          </div>
        </div>
      </header>

      <MenuDrawer
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        isAuthenticated={isAuthenticated}
        user={user}
        onOpenLogin={openLogin}
        onOpenSignup={openSignup}
        onLogout={logout}
      />

      <AuthModal
        mode={authModalMode}
        open={authModalOpen}
        onClose={closeAuthModal}
      />
    </>
  )
}
