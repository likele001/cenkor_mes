// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import 'vite/client'

// 为纯 TypeScript 语言服务（未加载 Vue 插件时）提供 *.vue 模块的类型声明，
// 否则 `import App from './App.vue'` 会报 ts(2307) 找不到模块类型。
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
