import { Route, Routes } from "react-router-dom";
import Footer from "./components/layout/Footer.jsx";
import Header from "./components/layout/Header.jsx";
import { ProtectedRoute } from "./features/auth/index.js";
import AdminPage from "./pages/AdminPage.jsx";
import DocumentDetailPage from "./pages/DocumentDetailPage.jsx";
import MainPage from "./pages/MainPage.jsx";
import PersonalProfile from './pages/MyPage.jsx';
import SearchPage from "./pages/SearchPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import styles from "./styles/App.module.css";

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
                <UploadPage />
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
