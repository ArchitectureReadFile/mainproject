import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { loginApi, logoutApi, meApi, signupApi } from "../api/authApi.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]                     = useState(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [logoutGuard, setLogoutGuard] = useState(null);
  const [authModalMode, setAuthModalMode] = useState("login");

  const openAuthModal = useCallback((mode = "login") => {
    setAuthModalMode(mode);
    setAuthModalOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => {
    setAuthModalOpen(false);
  }, []);

  // 앱 초기 로드 시 로그인 상태 복원
  useEffect(() => {
    let mounted = true;
    meApi()
      .then((me)  => { if (mounted) setUser(me); })
      .catch(()   => { if (mounted) setUser(null); })
      .finally(() => { if (mounted) setIsBootstrapping(false); });
    return () => { mounted = false; };
  }, []);

  const login = useCallback(async ({ email, password }) => {
    await loginApi(email.trim(), password);
    const me = await meApi();
    if (!me || typeof me !== "object") throw new Error("인증 응답 형식이 올바르지 않습니다.");
    setUser(me);
  }, []);

  const signup = useCallback(async ({ username, email, password }) => {
    await signupApi(username.trim(), email.trim(), password);
    window.location.href = "/";
  }, []);

  const registerLogoutGuard = useCallback((guard) => {
    setLogoutGuard(guard ?? null)  // 함수를 래핑 없이 직접 저장 (useState initializer 회피)
  }, [])

  const logout = useCallback(async () => {
    if (logoutGuard) {
      if (!logoutGuard.confirm()) return false  // 사용자가 취소 → false 반환
      logoutGuard.clear()                       // sessionStorage + upload state 초기화
    }
    try {
      await logoutApi();
    } catch (e) {
      // 서버 로그아웃 실패해도 클라이언트는 로그아웃 완료로 처리
      // (쿠키는 만료되며, 서버 세션도 벵원 불가하므로 실질적 해익 없음)
      console.error("Logout error:", e);
    }
    setUser(null);
    window.location.href = "/";
    return true;
  }, [logoutGuard]);

  const value = useMemo(
    () => ({
      user,
      setUser,
      isAuthenticated: !isBootstrapping && Boolean(user),
      isBootstrapping,
      login,
      signup,
      logout,
      registerLogoutGuard,
      authModalOpen,
      authModalMode,
      openAuthModal,
      closeAuthModal,
    }),
    [
      user,
      setUser,
      isBootstrapping,
      login,
      signup,
      logout,
      registerLogoutGuard,
      authModalOpen,
      authModalMode,
      openAuthModal,
      closeAuthModal,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
