import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发态：8121 提供页面并把 /api 代理到 Django（7121）。
// 生产态（compose）：构建产物由前端容器内 nginx 在 8121 提供，同源反代 /api。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 8121,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:7121',
        changeOrigin: true,
      },
    },
  },
})
