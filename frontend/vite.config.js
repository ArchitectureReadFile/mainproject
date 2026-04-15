import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: '@', replacement: path.resolve(__dirname, 'src') }],
  },
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
