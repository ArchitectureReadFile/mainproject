import { FolderOpen, Home, LogOut, Shield, Upload, User, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import styles from "./MenuDrawer.module.css";

function MenuItem({ to, icon, label, active, onClick }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`${styles.item} ${active ? styles.itemActive : ""}`}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}

export default function MenuDrawer({
  open,
  onClose,
  isAuthenticated,
  user,
  onOpenLogin,
  _onOpenSignup,
  onLogout,
}) {
  const location = useLocation();

  if (!open) return null;

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />

      <aside className={styles.drawer}>
        {/* 헤더 */}
        <div className={styles.header}>
          <h3>메뉴</h3>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="닫기">
            <X size={20} />
          </button>
        </div>

        {/* 프로필 */}
        <section className={styles.section}>
            <MenuItem
                to="/profile"
                icon={<User size={18} />}
                label={isAuthenticated ? user?.username || "프로필" : "프로필"}
                active={location.pathname.startsWith("/profile")}
                onClick={isAuthenticated ? onClose : onOpenLogin}
            />
        </section>

        {/* 판례 관리 */}
        <section className={styles.section}>
          <p className={styles.label}>판례 관리</p>

          <MenuItem
            to="/upload"
            icon={<Upload size={18} />}
            label="업로드"
            active={location.pathname.startsWith("/upload")}
            onClick={onClose}
          />

          <MenuItem
            to="/documents"
            icon={<FolderOpen size={18} />}
            label="목록보기"
            active={location.pathname.startsWith("/documents")}
            onClick={onClose}
          />
        </section>

        {/* 홈 */}
        <section className={styles.section}>
          <MenuItem
            to="/"
            icon={<Home size={18} />}
            label="홈"
            active={location.pathname === "/"}
            onClick={onClose}
          />
        </section>

        {/* 관리자 페이지 (관리자 권한이 있는 사용자에게만 표시) */}
        {isAuthenticated && user?.role === "ADMIN" && (
          <section className={styles.section}>
            <p className={styles.label}>관리자</p>
            <MenuItem
              to="/admin"
              icon={<Shield size={18} />}
              label="관리자 페이지"
              active={location.pathname.startsWith("/admin")}
              onClick={onClose}
            />
          </section>
        )}

        {/* 로그아웃 */}
        {isAuthenticated && (
        <section className={styles.section}>
            <button
            type="button"
            className={`${styles.item} ${styles.itemDanger}`}
            onClick={async () => {
                const loggedOut = await onLogout();
                if (loggedOut !== false) onClose();
            }}
            >
            <LogOut size={18} />
            <span>로그아웃</span>
            </button>
        </section>
        )}
      </aside>
    </>
  );
}
