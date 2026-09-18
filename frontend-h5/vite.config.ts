// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Inspector from 'unplugin-vue-dev-locator/vite'

export default defineConfig(({ mode }) => {
  // 允许通过 VITE_API_PROXY 指定后端地址，默认 8000（开发启动脚本/手动可覆盖，避免端口被占用时串到其它服务）
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxy = env.VITE_API_PROXY || 'http://127.0.0.1:8000'
  return {
    build: {
      sourcemap: false,
      // 宝塔 dist/.user.ini 防删保护，避免 emptyDir 构建失败
      emptyOutDir: false,
    },
    server: {
      proxy: {
        '/api': {
          target: apiProxy,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      vue(),
      Inspector(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  }
})