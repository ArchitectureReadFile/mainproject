import { useEffect } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

export default function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isBootstrapping, user, openAuthModal } = useAuth()

  useEffect(() => {
    if (!isBootstrapping && !isAuthenticated) {
      openAuthModal('login')
    }
  }, [isAuthenticated, isBootstrapping, openAuthModal])

  if (isBootstrapping) return null
  if (!isAuthenticated) return null
  if (requireAdmin && user?.role !== 'ADMIN') return null
  return children
}