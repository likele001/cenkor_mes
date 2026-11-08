#!/usr/bin/env node
// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/**
 * 多语言键门禁（i18n guard）
 *
 * 解决的问题：新增页面只写了 t('a.b.c') 却忘了往语言包补 key，vue-i18n 会
 * 直接把 key 本身渲染到界面上；或者只补了中文，其它语言显示英文/中文兜底。
 * 这类问题类型检查和 vite build 都发现不了，必须在构建前单独拦。
 *
 * 检查项（ERROR 会让命令以 1 退出）：
 *   E1 locale-load         语言包能被编译求值
 *   E2 missing-key         源码静态 t() 引用的 key 在每种语言的运行时集合中存在
 *   E3 pack-gap            每种语言包覆盖 zh-CN 的全部 key（防止「只做一半」）
 *   E4 type-conflict       t() 引用的 key 在语言包里不是对象（否则渲染 [object Object]）
 *   E5 placeholder         同一 key 在各语言中的 {xxx} 占位符集合一致
 *
 * 检查项（WARNING 只提示，不阻塞）：
 *   W1 literal-key         源码里形如 "a.b.c" 的字符串疑似动态 key 但语言包没有
 *   W2 untranslated        某语言的值与英文完全相同（专有名词白名单除外）
 *
 * 用法：
 *   node scripts/check-i18n.mjs                      # 检查当前工作目录对应的前端
 *   node scripts/check-i18n.mjs --root ../frontend-h5
 *   node scripts/check-i18n.mjs --json report.json  # 机器可读报告
 *   node scripts/check-i18n.mjs --max-print 50
 *
 * 依赖：esbuild（vite 的传递依赖，npm ci 后即有），零额外安装。
 * 说明：ko-KR 运行时 = deepMerge(en-US, ko-KR, ko-KR-shell)，脚本按并集近似；
 *       *-shell.ts 只是补充包，不参与键集合对齐要求。
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

/* ------------------------------------------------------------------ *
 * 0. 参数
 * ------------------------------------------------------------------ */
const argv = process.argv.slice(2)

function hasFlag(name) { return argv.includes(name) }
function flagValue(name, fallback = null) {
  const i = argv.indexOf(name)
  if (i < 0) return fallback
  const v = argv[i + 1]
  return v && !v.startsWith('--') ? v : fallback
}

const ROOT = path.resolve(flagValue('--root', process.cwd()))
const LOCALE_DIR = path.join(ROOT, 'src/locales')
const SRC_DIR = path.join(ROOT, 'src')
const MAX_PRINT = Number(flagValue('--max-print', 30))
const JSON_FILE = hasFlag('--json') ? flagValue('--json', null) : undefined
// 白名单与脚本同目录，跟着代码走，调用方无需传参
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const ALLOWLIST_FILE = flagValue('--allowlist', path.join(SCRIPT_DIR, 'i18n-allowlist.json'))
const STRICT_UNTRANSLATED = hasFlag('--strict-untranslated')

const errors = []
const warnings = []
function err(code, key, detail) { errors.push({ code, key, detail }) }
function warn(code, key, detail) { warnings.push({ code, key, detail }) }

/* ------------------------------------------------------------------ *
 * 1. 语言包加载
 * ------------------------------------------------------------------ */
const BASE = 'zh-CN'
const PACK_RE = /^([A-Za-z]{2,3}-[A-Za-z]{2,4})\.ts$/
const SRC_EXT = new Set(['.vue', '.ts', '.tsx', '.js', '.jsx', '.mjs'])

if (!fs.existsSync(LOCALE_DIR)) {
  console.error(`[i18n] 找不到语言包目录: ${LOCALE_DIR}\n       请在前端项目根目录执行，或用 --root 指定。`)
  process.exit(1)
}

let esbuild
let nodeRequire
try {
  nodeRequire = createRequire(path.join(ROOT, 'package.json'))
  esbuild = nodeRequire('esbuild')
} catch (e) {
  console.error(`[i18n] 无法加载 esbuild: ${e.message}\n       请先在 ${ROOT} 执行 npm ci（esbuild 是 vite 的传递依赖）。`)
  process.exit(1)
}

/** 把 TS 语言包编译成 CJS 并求值，得到普通对象（比正则解析嵌套可靠）。 */
async function loadLocale(file) {
  const r = await esbuild.build({
    entryPoints: [file],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    write: false,
    logLevel: 'silent',
  })
  const mod = { exports: {} }
  new Function('module', 'exports', 'require', r.outputFiles[0].text)(mod, mod.exports, nodeRequire)
  return mod.exports.default ?? mod.exports
}

/** 嵌套对象 -> Map<dotKey, 叶子值>；对象节点本身不进 Map，另由 raw 判断类型。 */
function flatten(obj, prefix = '', out = new Map()) {
  for (const [k, v] of Object.entries(obj || {})) {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out)
    else out.set(key, v)
  }
  return out
}

function getRaw(obj, key) {
  return key.split('.').reduce((a, k) => (a == null ? undefined : a[k]), obj)
}

const packs = new Map()   // lang -> { file, flat, raw, top }
const shells = new Map()  // lang -> flat
for (const name of fs.readdirSync(LOCALE_DIR).sort()) {
  if (name.endsWith('-shell.ts')) {
    const lang = name.slice(0, -'-shell.ts'.length)
    try { shells.set(lang, flatten(await loadLocale(path.join(LOCALE_DIR, name)))) }
    catch (e) { err('locale-load', name, e.message) }
    continue
  }
  const m = PACK_RE.exec(name)
  if (!m) continue
  try {
    const raw = await loadLocale(path.join(LOCALE_DIR, name))
    packs.set(m[1], { file: name, raw, flat: flatten(raw), top: new Set(Object.keys(raw)) })
  } catch (e) {
    err('locale-load', name, e.message)
  }
}
if (!packs.has(BASE)) {
  console.error(`[i18n] 缺少基准语言包 ${BASE}.ts（${LOCALE_DIR}）`)
  process.exit(1)
}
if (errors.length) {
  console.error('[i18n] 语言包加载失败，无法继续检查')
  for (const e of errors) console.error(`  ${e.code} ${e.key}: ${e.detail}`)
  process.exit(1)
}

const baseKeys = new Set(packs.get(BASE).flat.keys())
const baseTop = packs.get(BASE).top
const langs = [...packs.keys()].sort()

/** 运行时键集合：ko-KR 会叠加英文基底与 shell；其它语言叠加自己的 shell。 */
function runtimeKeys(lang) {
  const own = packs.get(lang).flat
  const en = packs.get('en-US')?.flat ?? new Map()
  // ko-KR 的英文基底确实参与运行时，用 en-US 而不是 zh-CN 更贴近 deepMerge 语义
  const keys = new Set(lang === 'ko-KR' ? [...en.keys(), ...own.keys()] : own.keys())
  for (const [k] of shells.get(lang) ?? []) keys.add(k)
  return keys
}

/* ------------------------------------------------------------------ *
 * 2. 源码扫描
 * ------------------------------------------------------------------ */
function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === 'node_modules' || ent.name === 'dist' || ent.name.startsWith('.')) continue
    const p = path.join(dir, ent.name)
    if (p === LOCALE_DIR) continue // 语言包自身不参与源码扫描，避免自引用误报
    if (ent.isDirectory()) walk(p, out)
    else if (SRC_EXT.has(path.extname(ent.name))) out.push(p)
  }
  return out
}

// t('a.b') / $t("a.b") / te(...) / tm(...)
const CALL_RE = /(?:\$?\bt|\bte|\btm)\s*\(\s*(['"])([A-Za-z0-9_.\-[\]]+)\1/g
// 状态映射表 / i18nKey 里出现的 "a.b.c" 字符串常量
const LITERAL_RE = /['"]([a-zA-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)['"]/g

/** key -> Set<相对路径:行号> */
const used = new Map()
const literals = new Map()
const files = walk(SRC_DIR)
for (const file of files) {
  const rel = path.relative(ROOT, file)
  const text = fs.readFileSync(file, 'utf8')
  const lines = text.split('\n')
  lines.forEach((line, i) => {
    for (const m of line.matchAll(CALL_RE)) {
      const key = m[2]
      if (!used.has(key)) used.set(key, new Set())
      used.get(key).add(`${rel}:${i + 1}`)
    }
    for (const m of line.matchAll(LITERAL_RE)) {
      const key = m[1]
      if (!baseTop.has(key.split('.')[0])) continue
      if (baseKeys.has(key)) continue
      if (!literals.has(key)) literals.set(key, new Set())
      literals.get(key).add(`${rel}:${i + 1}`)
    }
  })
}
const usedKeys = new Set(used.keys())

/* ------------------------------------------------------------------ *
 * 3. 白名单（动态 key / 品牌名等已知例外）
 * ------------------------------------------------------------------ */
const DEFAULT_PROPER_NOUNS = new Set([
  'system.cloudStorage.fields.access_key',
  'system.cloudStorage.fields.secret_key',
  'system.cloudStorage.providers.qiniu',
  'system.cloudStorage.providers.upyun',
  'system.cloudStorage.providers.aliyun',
  'system.cloudStorage.providers.tencent',
  // 语言切换器按惯例显示各语言的自称，不是漏翻译
  'common.zhCN', 'common.enUS', 'common.koKR',
])
const allowlist = {
  literalKeys: [],
  untranslated: [...DEFAULT_PROPER_NOUNS],
  missingKeys: [],
}
if (ALLOWLIST_FILE && fs.existsSync(ALLOWLIST_FILE)) {
  const custom = JSON.parse(fs.readFileSync(ALLOWLIST_FILE, 'utf8'))
  for (const k of Object.keys(allowlist)) {
    if (Array.isArray(custom[k])) allowlist[k] = [...new Set([...allowlist[k], ...custom[k]])]
  }
}
const allowLiteral = new Set(allowlist.literalKeys)
const allowUntranslated = new Set(allowlist.untranslated)
const allowMissing = new Set(allowlist.missingKeys)

/* ------------------------------------------------------------------ *
 * 4. 检查
 * ------------------------------------------------------------------ */
const enFlat = packs.get('en-US')?.flat ?? new Map()

// E2 + E3 + E4：逐语言检查
for (const lang of langs) {
  const pack = packs.get(lang)
  const rt = runtimeKeys(lang)

  // E2 源码引用的 key 必须在该语言的运行时集合里
  for (const key of usedKeys) {
    if (rt.has(key)) continue
    if (allowMissing.has(`${lang}:${key}`) || allowMissing.has(key)) continue
    err('missing-key', `${lang} :: ${key}`, [...(used.get(key) ?? [])].slice(0, 3).join(', '))
  }

  // E3 语言包必须覆盖基准的全部 key（单向；额外键只作 INFO，历史冗余不阻塞）
  for (const key of baseKeys) {
    if (pack.flat.has(key)) continue
    err('pack-gap', `${lang} :: ${key}`, `zh-CN 有此键，${lang} 缺失（页面会 fallback）`)
  }

  // E4 t() 引用的 key 不能是对象/数组
  for (const key of usedKeys) {
    const v = getRaw(pack.raw, key)
    if (v && typeof v === 'object') {
      err('type-conflict', `${lang} :: ${key}`, `语言包里是 ${Array.isArray(v) ? '数组' : '对象'}，t() 会渲染成 [object Object]`)
    }
  }
}

// E5 占位符一致性：插值参数错位比漏 key 更难排查
const PLACEHOLDER_RE = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g
function placeholders(v) {
  return [...String(v ?? '').matchAll(PLACEHOLDER_RE)].map((m) => m[1]).sort().join(',')
}
for (const key of baseKeys) {
  const expected = placeholders(packs.get(BASE).flat.get(key))
  for (const lang of langs) {
    if (lang === BASE || !packs.get(lang).flat.has(key)) continue
    const got = placeholders(packs.get(lang).flat.get(key))
    if (got !== expected) {
      err('placeholder', `${lang} :: ${key}`, `zh-CN=[${expected}] / ${lang}=[${got}]`)
    }
  }
}

// W1 疑似动态 key 的字面量
for (const [key, locs] of literals) {
  if (allowLiteral.has(key)) continue
  warn('literal-key', key, [...locs].slice(0, 3).join(', '))
}

// W2 值与英文完全相同（专有名词除外）。
// 短标签（ID / SKU / Tokens In / H5 URL / #{id}）本来就应该保持英文，
// 默认只提示「像句子的长文案」；--strict-untranslated 可全量列出供人工审阅。
for (const lang of langs) {
  if (lang === 'en-US') continue
  for (const key of baseKeys) {
    if (!packs.get(lang).flat.has(key)) continue
    const v = String(packs.get(lang).flat.get(key))
    const en = String(enFlat.get(key) ?? '')
    if (v && v === en && !allowUntranslated.has(key)) {
      const words = v.trim().split(/\s+/).length
      if (STRICT_UNTRANSLATED || words >= 4) {
        warn('untranslated', `${lang} :: ${key}`, JSON.stringify(v))
      }
    }
  }
}

/* ------------------------------------------------------------------ *
 * 5. 输出
 * ------------------------------------------------------------------ */
function group(items) {
  const m = new Map()
  for (const it of items) {
    if (!m.has(it.code)) m.set(it.code, [])
    m.get(it.code).push(it)
  }
  return m
}
function printGroup(title, items) {
  for (const [code, list] of group(items)) {
    console.log(`\n${title} ${code}: ${list.length}`)
    for (const it of list.slice(0, MAX_PRINT)) console.log(`  - ${it.key}  ${it.detail}`)
    if (list.length > MAX_PRINT) console.log(`  ... 其余 ${list.length - MAX_PRINT} 条（--max-print 调整）`)
  }
}

console.log(`[i18n] ${ROOT}`)
console.log(`  语言包 : ${langs.map((l) => `${l} ${packs.get(l).flat.size}`).join(' | ')}`
  + (shells.size ? `  (shell: ${[...shells.entries()].map(([l, s]) => `${l} ${s.size}`).join(', ')})` : ''))
console.log(`  基准   : ${BASE} ${baseKeys.size} keys；源码静态引用 ${usedKeys.size} keys / ${files.length} 文件`)

if (errors.length) printGroup('ERROR', errors)
if (warnings.length) printGroup('WARN ', warnings)

const extraKeys = {}
for (const lang of langs) {
  extraKeys[lang] = [...packs.get(lang).flat.keys()].filter((k) => !baseKeys.has(k)).length
}
const orphanKeys = [...baseKeys].filter((k) => !usedKeys.has(k)).length

console.log(`\n[i18n] 结果: ERROR ${errors.length} / WARN ${warnings.length}`
  + `  (冗余键 ${JSON.stringify(extraKeys)}；未被静态引用 ${orphanKeys}，仅供参考)`)

const report = {
  root: ROOT,
  generatedAt: new Date().toISOString(),
  packs: Object.fromEntries(langs.map((l) => [l, packs.get(l).flat.size])),
  shells: Object.fromEntries([...shells].map(([l, s]) => [l, s.size])),
  baseKeys: baseKeys.size,
  usedKeys: usedKeys.size,
  scannedFiles: files.length,
  extraKeys,
  orphanKeys,
  errors,
  warnings,
  ok: errors.length === 0,
}
if (JSON_FILE) {
  fs.writeFileSync(path.resolve(JSON_FILE), JSON.stringify(report, null, 2) + '\n')
  console.log(`[i18n] JSON 报告: ${path.resolve(JSON_FILE)}`)
} else if (hasFlag('--json')) {
  console.log(JSON.stringify(report, null, 2))
}

console.log(errors.length ? '[i18n] ❌ 门禁未通过' : '[i18n] ✅ 通过')
process.exitCode = errors.length ? 1 : 0
