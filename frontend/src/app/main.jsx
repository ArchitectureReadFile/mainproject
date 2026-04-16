import '../index.css'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './App.jsx'
import { TooltipProvider } from '../shared/ui/tooltip.jsx'
import { AuthProvider } from '../features/auth/index.js'
import { NotificationProvider } from '../features/notification/context/NotificationContext.jsx'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <AuthProvider>
      <NotificationProvider>
        <TooltipProvider>
          <App />
          <Toaster position="top-right" richColors closeButton />
        </TooltipProvider>
      </NotificationProvider>
    </AuthProvider>
  </BrowserRouter>
)
