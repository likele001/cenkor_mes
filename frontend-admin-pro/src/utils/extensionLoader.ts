// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/**
 * 扩展前端加载器（宿主侧唯一入口）。
 *
 * 登录后经宿主 API 拉取已启用扩展清单，将各扩展 frontend/plugin.js 以
 * Blob 形式注入执行；插件通过 window.__registerExtension 回调注册动态
 * 路由、菜单与多语言文案。扩展的安装与授权均在独立应用中心完成，
 * MES 前端只负责“加载与呈现”。
 *
 * 插件脚本运行环境约定：
 * - window.Vue            宿主注入的 Vue 运行时（插件构建时 external 共享）
 * - window.__registerExtension  注册桥，由本模块安装
 */
import { ref, shallowRef, type Component } from 'vue'
import type { Router } from 'vue-router'
import { i18n } from '@/locales'
import { getToken } from '@/utils/token'

/** 插件声明的菜单项（window.__registerExtension 协议） */
export interface ExtensionMenu {
  path: string
  title: string
  icon?: string
  permission?: string
  i18nKey?: string
}

/** 插件声明的动态路由 */
export interface ExtensionRoute {
  path: string
  name?: string
  component: Component
  meta?: Record<string, unknown>
}

/** 插件注册载荷 */
export interface ExtensionRegistration {
  key: string
  menus?: ExtensionMenu[]
  routes?: ExtensionRoute[]
  locales?: Record<string, Record<string, unknown>>
}

declare global {
  interface Window {
    __registerExtension?: (reg: ExtensionRegistration) => void
    Vue?: unknown
  }
}

/** 已注册扩展的菜单项（响应式，AppMenu 消费） */
export const extensionMenus = ref<Array<ExtensionMenu & { key: string }>>([])
/** 已注册扩展的原始载荷（调试用） */
export const extensionRegistrations = shallowRef<ExtensionRegistration[]>([])

/** 插件注册的路由路径集合（deep-link 被重定向后重试判断） */
const extRoutePaths = new Set<string>()
/** 插件动态注册的 vue-router 路由名（重载时据此移除） */
const addedRouteNames = new Set<string>()

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
/** 插件 locales 简写 → 宿主 locale */
const LOCALE_ALIAS: Record<string, string> = { zh: 'zh-CN', en: 'en-US', ko: 'ko-KR' }

let router: Router | null = null
let bridgeInstalled = false
let loadedOnce = false
let loadingPromise: Promise<boolean> | null = null

function installBridge() {
  if (bridgeInstalled) return
  bridgeInstalled = true
  window.__registerExtension = (reg) => {
    if (!reg || typeof reg.key !== 'string' || !reg.key) return
    extensionRegistrations.value = [...extensionRegistrations.value, reg]

    // 动态路由挂载到 AppLayout 下；菜单项的 permission 合并进路由 meta.permissions
    const menuByPath = new Map((reg.menus ?? []).map((m) => [m.path, m]))
    let idx = 0
    for (const r of reg.routes ?? []) {
      if (!router || !r || typeof r.path !== 'string' || !r.path || !r.component) continue
      const permission = menuByPath.get(r.path)?.permission
      const routeName = r.name || `ext-route-${reg.key}-${idx++}`
      router.addRoute('app-layout', {
        path: r.path,
        name: routeName,
        component: r.component,
        meta: { ...(r.meta ?? {}), ...(permission ? { permissions: [permission] } : {}) },
      })
      extRoutePaths.add(r.path)
      addedRouteNames.add(routeName)
    }

    // 菜单收集（AppMenu 渲染为“扩展应用”分组）
    const items = (reg.menus ?? [])
      .filter((m) => m && typeof m.path === 'string' && m.path)
      .map((m) => ({ ...m, key: reg.key }))
    if (items.length) extensionMenus.value = [...extensionMenus.value, ...items]

    // 多语言注入（zh → zh-CN 等）
    const merge = i18n.global.mergeLocaleMessage as unknown as (
      locale: string,
      message: Record<string, unknown>
    ) => void
    for (const [loc, msgs] of Object.entries(reg.locales ?? {})) {
      if (!msgs || typeof msgs !== 'object') continue
      merge(LOCALE_ALIAS[loc] ?? loc, msgs)
    }
  }
}

async function fetchPluginCode(key: string): Promise<string | null> {
  try {
    const token = getToken()
    const resp = await fetch(`${API_BASE}/admin/extensions/${encodeURIComponent(key)}/plugin.js`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) {
      console.warn(`[extensions] 插件获取失败(${resp.status}): ${key}`)
      return null
    }
    return await resp.text()
  } catch (e) {
    console.warn(`[extensions] 插件获取异常: ${key}`, e)
    return null
  }
}

/** 以 Blob URL 注入执行插件脚本（依赖 window.Vue 与注册桥已就绪） */
function injectScript(code: string, key: string): Promise<void> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(new Blob([code], { type: 'application/javascript' }))
    const el = document.createElement('script')
    el.src = url
    el.dataset.extension = key
    const done = () => {
      URL.revokeObjectURL(url)
      el.remove()
      resolve()
    }
    el.onload = done
    el.onerror = () => {
      console.warn(`[extensions] 插件执行失败: ${key}`)
      done()
    }
    document.head.appendChild(el)
  })
}

async function doLoad(): Promise<boolean> {
  loadedOnce = true
  try {
    const token = getToken()
    const resp = await fetch(`${API_BASE}/admin/extensions`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) {
      console.warn(`[extensions] 扩展清单获取失败: ${resp.status}`)
      return false
    }
    const body = (await resp.json()) as { data?: { items?: Array<Record<string, unknown>> } }
    const items = body?.data?.items ?? []
    const withFrontend = items.filter((x) => x.enabled === true && x.has_frontend === true)
    if (!withFrontend.length) return false
    for (const item of withFrontend) {
      const key = String(item.key ?? '')
      if (!key) continue
      const code = await fetchPluginCode(key)
      if (code) await injectScript(code, key)
    }
    return extensionRegistrations.value.length > 0
  } catch (e) {
    console.warn('[extensions] 扩展加载失败', e)
    return false
  }
}

/**
 * 首次加载扩展前端（并发去重；失败后本会话不再重试，刷新页面恢复）。
 * @returns 本次调用是否真正完成了拉取（true 表示可能新增了动态路由）
 */
export function ensureExtensionsLoaded(): Promise<boolean> {
  if (loadedOnce) return Promise.resolve(false)
  if (!loadingPromise) {
    loadingPromise = doLoad().finally(() => {
      loadingPromise = null
    })
  }
  return loadingPromise
}

/** 该路径是否由扩展插件注册（供路由守卫在 deep-link 被重定向后重试） */
export function hasExtensionRoute(path: string): boolean {
  return extRoutePaths.has(path)
}

/** 重置已注入的扩展前端（移除动态路由、清空菜单/注册缓存） */
function resetExtensions() {
  if (router) {
    for (const name of addedRouteNames) {
      if (router.hasRoute(name)) router.removeRoute(name)
    }
  }
  addedRouteNames.clear()
  extRoutePaths.clear()
  extensionMenus.value = []
  extensionRegistrations.value = []
  loadedOnce = false
}

/**
 * 重新加载扩展前端（安装/卸载后调用，无需刷新页面）。
 * 先移除旧注册，再按后端最新启用清单重新拉取并注入 plugin.js。
 */
export function reloadExtensions(): Promise<boolean> {
  resetExtensions()
  return doLoad()
}

/** 应用启动时调用一次：绑定 router 并安装插件注册桥 */
export function setupExtensionLoader(opts: { router: Router }) {
  router = opts.router
  installBridge()
}
