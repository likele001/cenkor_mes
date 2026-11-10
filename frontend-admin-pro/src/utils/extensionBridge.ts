// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/**
 * 扩展插件宿主运行时桥（宿主核心，不属于任何商业扩展）。
 *
 * 插件脚本经 Blob 注入执行，无法 import 宿主模块，只能从 window 取能力：
 *   window.Vue          Vue 运行时 + 插件用到的 Element Plus 组件
 *   window.__extRequest 带登录态的 JSON 请求，返回 { data }
 *   window.__extHttp    axios 风格适配器（历史插件用 .data.data）
 *   window.__extToast   轻提示
 *   window.ElMessage / window.axios  历史插件直连兜底
 *
 * 接口契约：HTTP 200 + body.code（成功 200）。业务失败必须 reject，
 * 不能把错误体当成功数据吞掉——否则页面只会显示「共 0 条」而无任何提示。
 *
 * 标签解析：插件常以 h("el-table-column") 之类的字符串写标签，而 Vue 的 h()
 * 只把字符串当原生元素（不做组件名解析）。元素型 vnode 的 slots 对象会在
 * normalizeChildren 里被无参调用 slot()，形如 ({ row }) => ... 的列插槽因此抛
 * Cannot destructure property 'row' of 'undefined'，见下方 extH。
 */
import * as Vue from 'vue'
import axios from 'axios'
import {
  ElAlert, ElButton, ElDatePicker, ElDescriptions, ElDescriptionsItem,
  ElDialog, ElDrawer, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage,
  ElOption, ElPagination, ElRadioButton, ElRadioGroup, ElSelect, ElSwitch,
  ElTabPane, ElTable, ElTableColumn, ElTabs, ElTag,
} from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/descriptions/style/css'
import 'element-plus/es/components/descriptions-item/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/drawer/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/input-number/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/pagination/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/switch/style/css'
import 'element-plus/es/components/tab-pane/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/table-column/style/css'
import 'element-plus/es/components/tabs/style/css'
import 'element-plus/es/components/tag/style/css'
import { clearToken, getToken } from '@/utils/token'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/** 插件硬编码 /api/... 路径，部署到自定义 API_BASE 时做前缀替换 */
function resolveUrl(url: string): string {
  if (API_BASE !== '/api' && url.startsWith('/api/')) return API_BASE + url.slice(4)
  if (API_BASE !== '/api' && url.startsWith('/api?')) return API_BASE + url.slice(4)
  return url
}

interface ExtRequestOptions {
  method?: string
  body?: unknown
  data?: unknown
  params?: Record<string, unknown>
  headers?: Record<string, string>
  url?: string
}

type ExtError = Error & { response?: { status: number; data: unknown }; bizCode?: number }

function withQuery(url: string, params?: Record<string, unknown>): string {
  if (!params || typeof params !== 'object') return url
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue
    if (Array.isArray(v)) v.forEach((item) => usp.append(k, String(item)))
    else usp.set(k, String(v))
  }
  const qs = usp.toString()
  return qs ? url + (url.includes('?') ? '&' : '?') + qs : url
}

/** 统一请求出口：带 token、解包 body.code、把失败转成带 response 的 Error */
async function rawRequest(url: string, opt: ExtRequestOptions = {}) {
  const method = (opt.method || 'GET').toUpperCase()
  const target = withQuery(resolveUrl(url), opt.params)
  const headers: Record<string, string> = { ...(opt.headers || {}) }
  const token = getToken()
  if (token && !headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${token}`
  }

  let body: string | FormData | undefined
  const payload = opt.body ?? opt.data
  if (payload !== undefined && payload !== null && method !== 'GET' && method !== 'HEAD') {
    if (payload instanceof FormData) {
      body = payload
    } else if (typeof payload === 'string') {
      body = payload
      if (!headers['Content-Type'] && !headers['content-type']) headers['Content-Type'] = 'application/json'
    } else {
      body = JSON.stringify(payload)
      if (!headers['Content-Type'] && !headers['content-type']) headers['Content-Type'] = 'application/json'
    }
  }

  const resp = await fetch(target, { method, headers, body, credentials: 'same-origin' })
  const ctype = String(resp.headers.get('content-type') || '')
  let json: unknown = null
  if (ctype.includes('json')) {
    json = await resp.json().catch(() => null)
  } else {
    const text = await resp.text().catch(() => '')
    try { json = JSON.parse(text) } catch { json = text }
  }

  const obj = (json && typeof json === 'object') ? json as Record<string, unknown> : null
  if (!resp.ok) {
    const err = new Error(String(obj?.msg ?? obj?.detail ?? `请求失败 ${resp.status}`)) as ExtError
    err.response = { status: resp.status, data: json }
    throw err
  }
  if (obj && typeof obj.code === 'number' && obj.code !== 200) {
    const err = new Error(String(obj.msg || `业务错误 ${obj.code}`)) as ExtError
    err.response = { status: 200, data: json }
    err.bizCode = obj.code
    if (obj.code === 401) {
      clearToken()
      location.href = '/login'
    }
    throw err
  }
  return { json, status: resp.status }
}

/**
 * __extRequest：主协议返回 { data: 业务数据 }。
 * 少数历史插件直接取业务字段（d.items / d.call_types），这里以「不可枚举」
 * 属性一并暴露，既不破坏解构写法，也不会污染 JSON.stringify 的详情输出。
 */
async function extRequest(url: string, opt: ExtRequestOptions = {}) {
  const { json } = await rawRequest(url, opt)
  const obj = (json && typeof json === 'object') ? json as Record<string, unknown> : null
  const biz = obj && 'data' in obj ? obj.data : json
  const out: Record<string, unknown> = {
    data: biz,
    code: obj?.code ?? 200,
    msg: obj?.msg ?? '',
  }
  if (biz && typeof biz === 'object' && !Array.isArray(biz)) {
    for (const [k, v] of Object.entries(biz as Record<string, unknown>)) {
      if (!(k in out)) {
        Object.defineProperty(out, k, { value: v, enumerable: false, configurable: true, writable: true })
      }
    }
  }
  return out
}

/** __extHttp：axios 风格，返回 { data: 完整响应体 }，插件常用 r.data.data.xxx */
async function extHttp(opts: ExtRequestOptions) {
  const { json, status } = await rawRequest(opts.url || '', opts)
  return { data: json, status, statusText: '', headers: {}, config: opts }
}

type ToastType = 'success' | 'warning' | 'error' | 'info'
function extToast(message: string, type: string = 'info') {
  const allowed: ToastType[] = ['success', 'warning', 'error', 'info']
  const t: ToastType = allowed.includes(type as ToastType) ? type as ToastType : 'info'
  ElMessage({ message: String(message), type: t })
}

/** 插件可用 h("el-xxx") 字符串标签 → 真实组件；未注册的标签保持原生元素并告警一次 */
const EXT_TAGS: Record<string, Vue.Component> = {
  'el-alert': ElAlert,
  'el-button': ElButton,
  'el-date-picker': ElDatePicker,
  'el-descriptions': ElDescriptions,
  'el-descriptions-item': ElDescriptionsItem,
  'el-dialog': ElDialog,
  'el-drawer': ElDrawer,
  'el-form': ElForm,
  'el-form-item': ElFormItem,
  'el-input': ElInput,
  'el-input-number': ElInputNumber,
  'el-option': ElOption,
  'el-pagination': ElPagination,
  'el-radio-button': ElRadioButton,
  'el-radio-group': ElRadioGroup,
  'el-select': ElSelect,
  'el-switch': ElSwitch,
  'el-tab-pane': ElTabPane,
  'el-table': ElTable,
  'el-table-column': ElTableColumn,
  'el-tabs': ElTabs,
  'el-tag': ElTag,
}

const warnedTags = new Set<string>()
function resolveExtTag(type: unknown) {
  if (typeof type !== 'string' || !type.startsWith('el-')) return type
  const component = EXT_TAGS[type]
  if (component) return component
  if (!warnedTags.has(type)) {
    warnedTags.add(type)
    console.warn(`[extensions] 宿主桥未暴露组件 ${type}，请在 extensionBridge.ts 注册后重新打包`)
  }
  return type
}

/** 替插件兜住「字符串当组件」的写法：字符串标签按 EXT_TAGS 解析，其余原样交给 Vue.h */
const extH = ((type: any, props?: any, children?: any) =>
  Vue.h(resolveExtTag(type) as Vue.Component, props, children)) as typeof Vue.h

/** 插件通过 window.Vue 取 h/ref/... 与 Element Plus 组件 */
const sharedVue = {
  ...Vue,
  h: extH,
  ElAlert, ElButton, ElDatePicker, ElDescriptions, ElDescriptionsItem,
  ElDialog, ElDrawer, ElForm, ElFormItem, ElInput, ElInputNumber,
  ElOption, ElPagination, ElRadioButton, ElRadioGroup, ElSelect, ElSwitch,
  ElTabPane, ElTable, ElTableColumn, ElTabs, ElTag,
}

/** 在 app.mount 之前调用；插件注入发生在登录后的 ensureExtensionsLoaded() */
export function installExtensionBridge(): void {
  Object.assign(window, {
    Vue: sharedVue,
    __extRequest: extRequest,
    __extHttp: extHttp,
    __extToast: extToast,
    ElMessage,
    axios,
  })
}
