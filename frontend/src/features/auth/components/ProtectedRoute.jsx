import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children, requireAdmin = false }) {
  const {
    isAuthenticated,
    isBootstrapping,
    user,
    openAuthModal,
  } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!isBootstrapping && !isAuthenticated) {
      openAuthModal("login");
    }
  }, [isAuthenticated, isBootstrapping, openAuthModal]);

  if (isBootstrapping) return null;

  if (!isAuthenticated) {
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  if (requireAdmin && user?.role !== "ADMIN") {
    return <Navigate to="/" replace />;
  }

  return children;
}
