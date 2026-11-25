import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      // FastAPI backend (uvicorn api.index:app --port 8000). SSE streams pass through unbuffered.
      // API_PROXY_TARGET lets a second dev server point at the demo API (scripts/demo_api.py).
      '/api': { target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
