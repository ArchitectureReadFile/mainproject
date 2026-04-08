import { useState, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import Footer from './components/layout/Footer.jsx'
import Header from './components/layout/Header.jsx'
import { ProtectedRoute, useAuth } from './features/auth/index.js'
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
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const hideChatWidget = location.pathname === '/' || isMenuOpen
  const { openAuthModal } = useAuth()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('login') === 'success') {
      params.delete('login')
      const newUrl = window.location.pathname + (params.toString() ? `?${params.toString()}` : '')
      window.history.replaceState({}, '', newUrl)
    }

    if (params.get('error')) {
      const errCode = params.get('error')
      if (errCode === 'not_registered') {
        openAuthModal('signup')
      } else {
        openAuthModal('login')
      }
    }
  }, [openAuthModal])

  return (
    <div className="min-h-screen flex flex-col">
      <div className="fixed top-0 left-0 w-full z-50">
        <Header onMenuOpenChange={setIsMenuOpen} />
      </div>
      <main className="flex-1 pt-[72px]">
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
      <div className="snap-start">
        <Footer />
      </div>
    </div>
  )
}