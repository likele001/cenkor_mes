#!/usr/bin/env node
// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/**
 * 扩展前端生命周期自检（插拔闭环测试矩阵第 12 项）。
 *
 * 直接跑真实 `src/utils/extensionLoader.ts`：用 memory history 建一个最小 router，
 * 经 `window.__registerExtension` 桥模拟插件注册，然后断言「卸载后当前路由判定」
 * 与路由/菜单/locale 缓存回收是否干净。
 *
 * 项目没有前端测试框架，这里用 esbuild 现场打包 → node 执行，零额外依赖：
 *   node scripts/check-extension-routes.mjs
 */
import { build } from 'esbuild'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const ENTRY = `
import { createRouter, createMemoryHistory } from 'vue-router'
import {
  setupExtensionLoader, hasExtensionRoute, isExtensionRouteActive,
  unloadExtension, getExtensionRoute, extensionMenus, isExtensionLoaded,
} from '@/utils/extensionLoader'

const fails = []
function check(name, cond) {
  if (!cond) fails.push(name)
  console.log(\`\${cond ? 'OK  ' : 'FAIL'} \${name}\`)
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'app-layout', component: {} },
    { path: '/market', name: 'market', component: {} },
  ],
})
setupExtensionLoader({ router })

// 模拟 plugin.js 执行：插件只通过注册桥声明路由/菜单/locale
globalThis.window.__registerExtension({
  key: 'demo',
  routes: [{ path: '/ext/demo', name: 'ExtDemo', component: {} }],
  menus: [{ path: '/ext/demo', title: '演示', permission: 'ext.demo.view' }],
  locales: { zh: { demo: { title: '演示' } } },
})

check('hasExtensionRoute(/ext/demo)', hasExtensionRoute('/ext/demo') === true)
check('hasExtensionRoute(/nope)', hasExtensionRoute('/nope') === false)
check('getExtensionRoute(demo)', getExtensionRoute('demo') === '/ext/demo')
check('isExtensionLoaded(demo)', isExtensionLoaded('demo') === true)
check('menus 含 demo', extensionMenus.value.some((m) => m.key === 'demo'))
check('router 有 ExtDemo', router.hasRoute('ExtDemo') === true)

await router.push('/ext/demo')
check('在 /ext/demo 时 isExtensionRouteActive(demo)', isExtensionRouteActive('demo') === true)
check('在 /ext/demo 时 isExtensionRouteActive(other)', isExtensionRouteActive('other') === false)

unloadExtension('demo')
check('卸载后 hasExtensionRoute=false', hasExtensionRoute('/ext/demo') === false)
check('卸载后 isExtensionRouteActive=false', isExtensionRouteActive('demo') === false)
check('卸载后 menus 清空', !extensionMenus.value.some((m) => m.key === 'demo'))
check('卸载后 router 移除 ExtDemo', router.hasRoute('ExtDemo') === false)
check('卸载后 isExtensionLoaded=false', isExtensionLoaded('demo') === false)

if (fails.length) {
  console.log(\`\\nFAILED: \${fails.join(', ')}\`)
  process.exitCode = 1
} else {
  console.log('\\nALL PASS')
}
`

const work = await mkdtemp(path.join(tmpdir(), 'ext-routes-'))
try {
  await writeFile(path.join(work, 'entry.ts'), ENTRY, 'utf8')
  await build({
    absWorkingDir: root,
    entryPoints: [path.join(work, 'entry.ts')],
    outfile: path.join(work, 'out.mjs'),
    bundle: true,
    platform: 'node',
    format: 'esm',
    logLevel: 'warning',
    // entry 在系统临时目录：显式指定 node_modules，否则解析不到 vue-router
    nodePaths: [path.join(root, 'node_modules')],
    // 与 vite 的 @ 别名一致；import.meta.env 只用了 VITE_API_BASE
    alias: { '@': path.join(root, 'src') },
    define: { 'import.meta.env.VITE_API_BASE': '"/api"' },
    // extensionLoader 的依赖链在模块求值期就会读 window/localStorage
    banner: {
      js: 'globalThis.window=globalThis;'
        + 'globalThis.localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};',
    },
  })
  await import(pathToFileURL(path.join(work, 'out.mjs')).href)
} finally {
  await rm(work, { recursive: true, force: true })
}
