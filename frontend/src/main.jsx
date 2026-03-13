import { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './App.jsx'
import { UploadProvider, useUpload } from './context/UploadContext.jsx'
import { AuthProvider } from './features/auth/index.js'
import { useAuth } from './features/auth/context/AuthContext.jsx'

// AuthContext의 logout과 UploadContext의 guard를 연결
function LogoutGuardBridge() {
  const { registerLogoutGuard } = useAuth()
  const { confirmLogout, clearSession } = useUpload()

  useEffect(() => {
    registerLogoutGuard({ confirm: confirmLogout, clear: clearSession })
    return () => registerLogoutGuard(null)
  }, [registerLogoutGuard, confirmLogout, clearSession])

  return null
}

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <AuthProvider>
      <UploadProvider>
        <LogoutGuardBridge />
        <App />
        <Toaster position="top-right" richColors />
      </UploadProvider>
    </AuthProvider>
  </BrowserRouter>
)
