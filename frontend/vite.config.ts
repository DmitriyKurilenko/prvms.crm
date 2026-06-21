import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  appType: 'spa',
  server: {
    host: '0.0.0.0',
    port: 5173
  },
  // `vite preview` используется e2e-прогоном (Playwright): отдаёт собранный SPA и
  // проксирует API/WS на бэкенд внутри compose-сети, чтобы всё было same-origin
  // (без CORS и проблем с SameSite-cookie). Цель прокси задаётся E2E_API_PROXY.
  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy: {
      '/api': { target: process.env.E2E_API_PROXY || 'http://web:8000', changeOrigin: true },
      '/ws': {
        target: (process.env.E2E_API_PROXY || 'http://web:8000').replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true
      }
    }
  }
})
