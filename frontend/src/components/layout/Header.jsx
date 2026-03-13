import { LogIn, Menu, Scale, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthModal, useAuth } from "../../features/auth/index.js";
import styles from "../../styles/Header.module.css";
import MenuDrawer from "./MenuDrawer.jsx";

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
  } = useAuth();

  const [menuOpen, setMenuOpen] = useState(false);
  const showUserChip = !isBootstrapping && isAuthenticated;

  const openLogin = () => {
    setMenuOpen(false);
    openAuthModal("login");
  };

  const openSignup = () => {
    setMenuOpen(false);
    openAuthModal("signup");
  };

  return (
    <>
      <header className={styles.header}>
        <div className={styles.container}>
          <Link to="/" className={styles.logoLink}>
            <div className={styles.logoWrap}>
              <Scale className={styles.logoIcon} />
              <div>
                <p className={styles.logoTitle}>판례 요약 시스템</p>
                <p className={styles.logoSub}>Legal Case Summarization</p>
              </div>
            </div>
          </Link>

          <div className={styles.right}>
            {showUserChip ? (
              <span className={styles.userChip}>{user?.username || "사용자"}</span>
            ) : (
              <button type="button" className={styles.outlineBtn} onClick={openLogin}>
                <LogIn size={16} />
                로그인
              </button>
            )}

            <button
              type="button"
              className={styles.menuBtn}
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-label={menuOpen ? "메뉴 닫기" : "메뉴 열기"}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
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
  );
}
