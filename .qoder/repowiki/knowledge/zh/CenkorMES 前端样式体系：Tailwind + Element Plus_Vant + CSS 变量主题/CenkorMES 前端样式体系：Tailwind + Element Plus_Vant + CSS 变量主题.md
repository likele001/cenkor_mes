---
kind: frontend_style
name: CenkorMES 前端样式体系：Tailwind + Element Plus/Vant + CSS 变量主题
category: frontend_style
scope:
    - '**'
source_files:
    - frontend-admin-pro/src/style.css
    - frontend-admin-pro/tailwind.config.js
    - frontend-admin-pro/src/composables/useAdminTheme.ts
    - frontend-h5/src/styles/tokens.css
    - frontend-h5/tailwind.config.js
    - frontend-h5/src/composables/useTheme.ts
    - lightmes-miniapp/src/uni.scss
---

## 1. 总体方案

仓库包含三个独立的前端应用，各自维护一套样式系统，但共享同一品牌色（蓝色）与暗色模式语义：

- **frontend-admin-pro**（管理后台 SPA）：Vue 3 + Vite + Tailwind CSS v3 + Element Plus。
- **frontend-h5**（移动端 H5 SPA）：Vue 3 + Vite + Tailwind CSS v3 + Vant。
- **lightmes-miniapp**（uni-app 小程序）：uni.scss SCSS 设计令牌，无 Tailwind。

构建工具统一为 Vite，CSS 预处理通过 PostCSS + Autoprefixer；管理端额外使用 `tailwind-merge` 合并动态 class。ESLint 仅校验 TS/JS/Vue，不直接约束 CSS 写法。

## 2. 关键文件

| 应用 | 样式入口 / 配置 | 说明 |
|---|---|---|
| admin-pro | `src/style.css` | 全局 CSS 变量、Element Plus 覆盖、暗色模式、TV 大屏主题、窄屏适配 |
| admin-pro | `tailwind.config.js` | Tailwind 扩展：`admin.*`、`tv.*` 颜色族、阴影、`darkMode: "class"` |
| admin-pro | `src/composables/useAdminTheme.ts` | 暗色模式 composable，读写 `localStorage('cenkormes-admin-theme')`，切换 `<html>` 的 `light/dark` 类 |
| h5 | `src/styles/tokens.css` | H5 设计令牌（`--lm-*` CSS 变量），定义主色、圆角、间距、字号、字体 |
| h5 | `tailwind.config.js` | 最小化 Tailwind 配置，仅启用 `darkMode: "class"` |
| h5 | `src/composables/useTheme.ts` | H5 暗色模式 composable，key 为 `theme` |
| miniapp | `src/uni.scss` | uni.scss SCSS 设计系统：品牌蓝梯度、slate 灰阶、语义色、半径、阴影、字号、字重、间距、过渡 |

## 3. 架构与约定

### 3.1 设计令牌（Design Tokens）

每个应用用独立的 token 命名空间隔离主题变量：

- **admin-pro**：以 `--admin-*` 和 `--el-*`（Element Plus 变量）为主，如 `--admin-page-bg`、`--admin-sider-bg`、`--el-color-primary`、`--el-border-radius-base`。
- **h5**：以 `--lm-*` 前缀集中声明，包括 `--lm-primary`、`--lm-cta`、`--lm-radius-*`、`--lm-space-*`、`--lm-font-*`。
- **miniapp**：SCSS 变量 `$brand-*`、`$slate-*`、`$success/$warn/$danger/$info`、`$radius-*`、`$shadow-*`、`$text-*`、`$space-*`。

这些变量是跨组件复用的唯一色彩/尺寸来源，组件内不应硬编码十六进制值。

### 3.2 暗色模式策略

三个应用均采用 **CSS class 驱动** 的暗色模式：

- `tailwind.config.js` 中统一设置 `darkMode: "class"`。
- `useAdminTheme.ts` / `useTheme.ts` 在挂载时读取 `localStorage` 或 `prefers-color-scheme`，将 `light` 或 `dark` 类添加到 `<html>` 根元素。
- 暗色规则集中在 `html.dark { ... }` 块中重写 `--admin-*`、`--el-*` 等变量，而非复制组件样式。

### 3.3 组件库与覆盖方式

- **admin-pro** 基于 Element Plus，通过 `src/style.css` 中的 `.el-table`、`.el-card`、`.el-button`、`.el-menu` 等全局选择器覆盖默认样式，并注入 `--el-*` CSS 变量以统一圆角、边框色、文本色。
- **h5** 基于 Vant，未引入 Element Plus，主要依赖 Tailwind utility class 与 `tokens.css` 中的 `--lm-*` 变量。
- **miniapp** 基于 uni-app 原生组件，样式全部走 SCSS 变量。

### 3.4 响应式策略

- **Tailwind 断点**：admin-pro 同时使用 Tailwind 的 `lg:`（1024px）与自定义 `@media (max-width: 1023px)` 针对窄屏列表做增强（表格横向滚动、表单纵向排列、弹窗全宽、分页换行）。
- **安全区适配**：在 `1023px` 以下媒体查询中使用 `env(safe-area-inset-*)` 处理刘海屏底部安全区。
- **H5 与小程序**：遵循各自平台惯例（Vant 栅格 / uni-app rpx），未在仓库中发现统一的响应式 mixin。

### 3.5 TV 大屏独立主题

admin-pro 内置一套 `tv-*` 颜色族（`--tv-bg`、`--tv-card`、`--tv-text` 等）并通过 `.tv-screen` 容器隔离，使其不受 `html.dark` 影响，用于经营看板大屏场景。

## 4. 约定与约束

- **命名空间隔离**：各应用的 CSS 变量使用前缀区分（`--admin-*`、`--lm-*`、SCSS `$brand-*`），避免跨应用变量污染。
- **暗色模式开关**：必须通过 `<html class="dark">` 触发，composable 负责同步 `localStorage` 与 `document.documentElement.classList`。
- **颜色来源**：禁止在组件模板中硬编码颜色值，应使用 Tailwind 扩展色（`admin.*`、`tv.*`）或 CSS 变量（`var(--el-*)`、`var(--lm-*)`、`var(--admin-*)`）。
- **Element Plus 覆盖**：所有对 Element Plus 组件的样式修改集中在 `src/style.css`，使用 CSS 变量优先于直接覆盖类名。
- **Tailwind 扫描范围**：两个 Web 应用的 `tailwind.config.js` 均限定 `content: ["./index.html", "./src/**/*.{js,ts,vue}"]`，确保只扫描源码。
- **构建产物**：打包后由 Nginx 分发（见 `docker/nginx/frontend-admin-pro.conf`、`frontend-h5.conf`），样式随 Vite 输出到 `dist/assets/*.css`。

作者指南明确要求“忽略前端组件的 UI 样式文件”，因此本卡片仅记录样式体系与主题机制，不展开业务页面组件细节。