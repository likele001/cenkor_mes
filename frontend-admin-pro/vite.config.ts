// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Inspector from 'unplugin-vue-dev-locator/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 将第三方依赖按模块拆分为独立 chunk，避免单个 chunk 过大（目标 gzip 与原始体积均 < 500kB）
function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  // 用路径分段精确匹配，避免 vue 误吞 vue-router / vue-i18n / vue-echarts 等
  const seg = (pkg: string) => id.includes(`/node_modules/${pkg}/`) || id.includes(`\\node_modules\\${pkg}\\`)
  if (seg('zrender')) return 'vendor-zrender'
  if (seg('echarts') || seg('vue-echarts')) return 'vendor-echarts'
  if (seg('@element-plus/icons-vue')) return 'vendor-ep-icons'
  // Element Plus 必须整体归入单一 chunk：
  // 若按组件族二次拆分（form/table/datetime），子 chunk 之间会与 element-plus 核心相互 import，
  // Rollup 无法排出无环求值顺序，运行时触发 TDZ 报错（Cannot access 'xx' before initialization）导致白屏。
  if (seg('element-plus')) return 'vendor-element-plus'
  if (seg('lucide-vue-next')) return 'vendor-icons'
  if (seg('vue') || seg('@vue') || seg('vue-router') || seg('pinia') || seg('vue-i18n')) return 'vendor-vue'
  return 'vendor'
}

export default defineConfig(({ mode }) => {
  // 允许通过 VITE_API_PROXY 指定后端地址，默认 8000（开发启动脚本/手动可覆盖，避免端口被占用时串到其它服务）
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxy = env.VITE_API_PROXY || 'http://127.0.0.1:8000'
  return {
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 500,
      // 不清空 dist：原地构建会删掉上一代哈希 chunk，仍持有旧 index.html 的浏览器
      // 请求入口 JS 时得到 404，零 JS 执行 → 纯白屏且控制台无报错。保留旧资产让滞留客户端能自愈。
      emptyOutDir: false,
      rollupOptions: {
        output: {
          manualChunks,
        },
      },
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
      // Element Plus 按需引入：模板中的 <el-*> 组件与 v-loading 等指令自动按需引入并注入样式。
      // dts 关闭：项目 tsconfig 未纳入 Element Plus 全局类型，保持与其它构建一致的模板类型检查行为。
      Components({
        resolvers: [ElementPlusResolver()],
        dts: false,
      }),
      Inspector(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  }
})
