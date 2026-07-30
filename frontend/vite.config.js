import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 将前端 /api 请求代理到后端 FastAPI（默认 http://localhost:8000）
    // 后端业务路由本身已带 /api 前缀（如 /api/evaluate），因此无需 rewrite
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
