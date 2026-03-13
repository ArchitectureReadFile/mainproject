import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import Footer from "./components/layout/Footer.jsx";
import Header from "./components/layout/Header.jsx";
import { UploadProvider, useUpload } from "./context/UploadContext.jsx";
import { ProtectedRoute } from "./features/auth/index.js";
import { useAuth } from "./features/auth/context/AuthContext.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import DocumentDetailPage from "./pages/DocumentDetailPage.jsx";
import MainPage from "./pages/MainPage.jsx";
import PersonalProfile from './pages/MyPage.jsx';
import SearchPage from "./pages/SearchPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import styles from "./styles/App.module.css";

function LogoutGuardBridge() {
  const { registerLogoutGuard } = useAuth();
  const { confirmLogout, clearSession } = useUpload();

  useEffect(() => {
    registerLogoutGuard({ confirm: confirmLogout, clear: clearSession });
    return () => registerLogoutGuard(null);
  }, [registerLogoutGuard, confirmLogout, clearSession]);

  return null;
}

function UploadRoute() {
  return (
    <UploadProvider>
      <LogoutGuardBridge />
      <UploadPage />
    </UploadProvider>
  );
}

export default function App() {
  return (
    <div className={styles.root}>
      <Header />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route
            path="/upload"
            element={(
              <ProtectedRoute>
                <UploadRoute />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/documents"
            element={(
              <ProtectedRoute>
                <SearchPage />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/documents/:id"
            element={(
              <ProtectedRoute>
                <DocumentDetailPage />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/admin"
            element={(
              <ProtectedRoute requireAdmin>
                <AdminPage />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/profile"
            element={(
              <ProtectedRoute>
                <PersonalProfile />
              </ProtectedRoute>
            )}
          />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
