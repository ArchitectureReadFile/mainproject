import { Route, Routes, useLocation } from 'react-router-dom'
import Footer from './components/layout/Footer.jsx'
import Header from './components/layout/Header.jsx'
import { ProtectedRoute } from './features/auth/index.js'
import AdminPage from './pages/Admin/index.jsx'
import DocumentPage from './pages/Document/index.jsx'
import LandingPage from './pages/Landing/index.jsx'
import MypagePage from './pages/Mypage/index.jsx'
import UploadPage from './pages/Upload/index.jsx'
import WorkspacePage from './pages/Workspace/index.jsx'
import GroupDetailPage from './pages/Workspace/GroupDetailPage.jsx'
import ChatWidget from './features/chat/components/ChatWidget.jsx'

export default function App() {
  const location = useLocation()
  const hideChatWidget = location.pathname === '/'

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<LandingPage />} />

          <Route
            path="/workspace"
            element={
              <ProtectedRoute>
                <WorkspacePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/workspace/:group_id"
            element={
              <ProtectedRoute>
                <GroupDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/workspace/:group_id/upload"
            element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/workspace/:group_id/documents/:doc_id"
            element={
              <ProtectedRoute>
                <DocumentPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/mypage"
            element={
              <ProtectedRoute>
                <MypagePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <AdminPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
      {!hideChatWidget && <ChatWidget />}
      <Footer />
    </div>
  )
}