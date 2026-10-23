// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/**
 * 扩展前端加载器（宿主侧唯一入口）。
 *
 * 登录后经宿主 API 拉取已启用扩展清单，将各扩展 frontend/plugin.js 以
 * Blob 形式注入执行；插件通过 window.__registerExtension 回调注册动态
 * 路由、菜单与多语言文案。安装/卸载后由市场页调用 reloadExtensions()，
 * 按 key 精确卸载旧注册，无需刷新页面。
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

/** 单次重载结果：哪些扩展装上、哪些失败（UI 可提示「需刷新」） */
export interface ExtensionLoadResult {
  loaded: string[]
  failed: string[]
}

declare global {
  interface Window {
    __registerExtension?: (reg: ExtensionRegistration) => void
    Vue?: unknown
  }
}

interface KeyState {
  routes: Array<{ name: string; path: string }>
  menus: Array<ExtensionMenu & { key: string }>
  locales: Array<{ locale: string; namespaces: string[] }>
}

/** 已注册扩展的菜单项（响应式，AppMenu 消费） */
export const extensionMenus = ref<Array<ExtensionMenu & { key: string }>>([])
/** 已注册扩展的原始载荷（调试用） */
export const extensionRegistrations = shallowRef<ExtensionRegistration[]>([])

/** 每个扩展注册过的路由/菜单/locale 命名空间，卸载时按 key 精确回收 */
const keyStates = new Map<string, KeyState>()
/** 插件注册的路由路径集合（deep-link 被重定向后重试判断） */
const extRoutePaths = new Set<string>()

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
/** 插件 locales 简写 → 宿主 locale */
const LOCALE_ALIAS: Record<string, string> = { zh: 'zh-CN', en: 'en-US', ko: 'ko-KR' }

let router: Router | null = null
let bridgeInstalled = false
let loadedOnce = false
let loadingPromise: Promise<ExtensionLoadResult> | null = null

function mergeLocales(reg: ExtensionRegistration): KeyState['locales'] {
  const merge = i18n.global.mergeLocaleMessage as unknown as (
    locale: string,
    message: Record<string, unknown>,
  ) => void
  const tracked: KeyState['locales'] = []
  for (const [loc, msgs] of Object.entries(reg.locales ?? {})) {
    if (!msgs || typeof msgs !== 'object') continue
    const locale = LOCALE_ALIAS[loc] ?? loc
    merge(locale, msgs)
    tracked.push({ locale, namespaces: Object.keys(msgs) })
  }
  return tracked
}

/** 清掉某扩展注入的顶层 locale 命名空间（不能整包重置，避免清掉宿主文案） */
function dropLocales(state: KeyState) {
  const getLocaleMessage = i18n.global.getLocaleMessage as unknown as (
    locale: string,
  ) => Record<string, unknown>
  const setLocaleMessage = i18n.global.setLocaleMessage as unknown as (
    locale: string,
    message: Record<string, unknown>,
  ) => void
  for (const { locale, namespaces } of state.locales) {
    const messages = { ...getLocaleMessage(locale) }
    for (const ns of namespaces) delete messages[ns]
    setLocaleMessage(locale, messages)
  }
}

function installBridge() {
  if (bridgeInstalled) return
  bridgeInstalled = true
  window.__registerExtension = (reg) => {
    if (!reg || typeof reg.key !== 'string' || !reg.key) return
    // 同一 key 重复注册（热重载）：先回收旧注册，避免路由/菜单双份
    if (keyStates.has(reg.key)) unloadExtension(reg.key)
    extensionRegistrations.value = [...extensionRegistrations.value, reg]

    // 动态路由挂载到 AppLayout 下；菜单项的 permission 合并进路由 meta.permissions
    const menuByPath = new Map((reg.menus ?? []).map((m) => [m.path, m]))
    const routes: KeyState['routes'] = []
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
      routes.push({ name: routeName, path: r.path })
    }

    // 菜单收集（AppMenu 渲染为“扩展应用”分组）
    const items = (reg.menus ?? [])
      .filter((m) => m && typeof m.path === 'string' && m.path)
      .map((m) => ({ ...m, key: reg.key }))
    if (items.length) extensionMenus.value = [...extensionMenus.value, ...items]

    keyStates.set(reg.key, { routes, menus: items, locales: mergeLocales(reg) })
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
function injectScript(code: string, key: string): Promise<boolean> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(new Blob([code], { type: 'application/javascript' }))
    const el = document.createElement('script')
    el.src = url
    el.dataset.extension = key
    const done = (ok: boolean) => {
      URL.revokeObjectURL(url)
      el.remove()
      resolve(ok)
    }
    el.onload = () => done(true)
    el.onerror = () => {
      console.warn(`[extensions] 插件执行失败: ${key}`)
      done(false)
    }
    document.head.appendChild(el)
  })
}

async function doLoad(): Promise<ExtensionLoadResult> {
  loadedOnce = true
  const result: ExtensionLoadResult = { loaded: [], failed: [] }
  try {
    const token = getToken()
    const resp = await fetch(`${API_BASE}/admin/extensions`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) {
      console.warn(`[extensions] 扩展清单获取失败: ${resp.status}`)
      return result
    }
    const body = (await resp.json()) as { data?: { items?: Array<Record<string, unknown>> } }
    const items = body?.data?.items ?? []
    const withFrontend = items.filter((x) => x.enabled === true && x.has_frontend === true)
    for (const item of withFrontend) {
      const key = String(item.key ?? '')
      if (!key) continue
      const code = await fetchPluginCode(key)
      if (!code) {
        result.failed.push(key)
        continue
      }
      const ok = await injectScript(code, key)
      if (ok && keyStates.has(key)) result.loaded.push(key)
      else result.failed.push(key)
    }
    return result
  } catch (e) {
    console.warn('[extensions] 扩展加载失败', e)
    return result
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
    }) as unknown as Promise<ExtensionLoadResult>
  }
  return (loadingPromise as Promise<ExtensionLoadResult>).then((r) => r.loaded.length > 0)
}

/** 按 key 卸载扩展前端：动态路由、菜单、locale 命名空间、注册缓存一并回收 */
export function unloadExtension(key: string): boolean {
  const state = keyStates.get(key)
  if (!state) return false
  if (router) {
    for (const { name } of state.routes) {
      if (router.hasRoute(name)) router.removeRoute(name)
    }
  }
  for (const { path } of state.routes) extRoutePaths.delete(path)
  extensionMenus.value = extensionMenus.value.filter((m) => m.key !== key)
  extensionRegistrations.value = extensionRegistrations.value.filter((r) => r.key !== key)
  dropLocales(state)
  keyStates.delete(key)
  return true
}

/** 该路径是否由扩展插件注册（供路由守卫在 deep-link 被重定向后重试） */
export function hasExtensionRoute(path: string): boolean {
  return extRoutePaths.has(path)
}

/** 当前停留的路由是否属于该扩展（卸载后据此跳走） */
export function isExtensionRouteActive(key: string): boolean {
  const state = keyStates.get(key)
  const current = router?.currentRoute.value
  if (!state || !current) return false
  return state.routes.some((r) => r.name === current.name || r.path === current.path)
}

/** 重置已注入的扩展前端（移除动态路由、清空菜单/注册缓存） */
function resetExtensions() {
  for (const key of Array.from(keyStates.keys())) unloadExtension(key)
  extensionMenus.value = []
  extensionRegistrations.value = []
  extRoutePaths.clear()
  loadedOnce = false
}

/**
 * 重新加载扩展前端（安装/更新/卸载/启停后调用，无需刷新页面）。
 * 先移除旧注册，再按后端最新启用清单重新拉取并注入 plugin.js。
 */
export async function reloadExtensions(): Promise<ExtensionLoadResult> {
  resetExtensions()
  return doLoad()
}

/** 应用启动时调用一次：绑定 router 并安装插件注册桥 */
export function setupExtensionLoader(opts: { router: Router }) {
  router = opts.router
  installBridge()
}

/** 查询指定扩展是否已加载（有前端且已注册） */
export function isExtensionLoaded(key: string): boolean {
  return keyStates.has(key)
}

/** 获取指定扩展的第一个路由路径（用于跳转到扩展页面） */
export function getExtensionRoute(key: string): string | null {
  return keyStates.get(key)?.routes[0]?.path ?? null
}
