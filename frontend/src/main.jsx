import './index.css'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './App.jsx'
import { TooltipProvider } from './components/ui/tooltip.jsx'
import { AuthProvider } from './features/auth/index.js'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <AuthProvider>
      <TooltipProvider>
        <App />
        <Toaster position="top-right" richColors />
      </TooltipProvider>
    </AuthProvider>
  </BrowserRouter>
)