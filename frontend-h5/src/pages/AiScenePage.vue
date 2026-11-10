<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import {
  deleteSceneDoc, generateSceneDoc, getSceneDoc, listSceneDocs, listSceneScenarios,
  previewSceneDoc, type SceneDocItem, type SceneScenario,
} from '@/api/ai'
import { copyText as copyToClipboard } from '@/utils/clipboard'
import { downloadText } from '@/utils/download'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const running = ref('')
const previewing = ref('')
const scenarios = ref<SceneScenario[]>([])
const values = ref<Record<string, Record<string, string>>>({})

const docsOpen = ref(false)
const docsLoading = ref(false)
const docs = ref<SceneDocItem[]>([])
const docType = ref('')
const docPage = ref(1)
const docTotal = ref(0)
const docLoadingMore = ref(false)

function collectParams(s: SceneScenario): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  for (const f of s.fields || []) {
    const raw = (values.value[s.code]?.[f.key] ?? '').trim()
    if (!raw) continue
    params[f.key] = f.type === 'number' ? Number(raw) : raw
  }
  return params
}

function joinLines(parts: Array<string | undefined>) {
  return parts.filter(Boolean).join('\n\n')
}

async function loadDocs(reset = true) {
  if (reset) docPage.value = 1
  try {
    const r = await listSceneDocs({
      page: docPage.value,
      page_size: 20,
      type: docType.value || undefined,
    })
    const items = r.items || []
    docs.value = reset ? items : [...docs.value, ...items]
    docTotal.value = r.total || 0
  } catch {
    if (reset) docs.value = []
  }
}

async function loadMoreDocs() {
  if (docLoadingMore.value || docs.value.length >= docTotal.value) return
  docLoadingMore.value = true
  docPage.value += 1
  await loadDocs(false)
  docLoadingMore.value = false
}

async function openDocs() {
  docsOpen.value = true
  docsLoading.value = true
  await loadDocs()
  docsLoading.value = false
}

async function load() {
  loading.value = true
  try {
    const r = await listSceneScenarios()
    scenarios.value = r.scenarios || []
    const next: Record<string, Record<string, string>> = {}
    for (const s of scenarios.value) {
      const init: Record<string, string> = {}
      for (const f of s.fields || []) {
        if (f.default !== undefined && f.default !== null) init[f.key] = String(f.default)
      }
      next[s.code] = init
    }
    values.value = next
    locked.value = false
  } catch (e: unknown) {
    scenarios.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function preview(s: SceneScenario) {
  if (previewing.value) return
  previewing.value = s.code
  try {
    const r = await previewSceneDoc(s.code, collectParams(s))
    if (r.ok === false) {
      showToast(r.error || t('ai.previewFailed'))
      return
    }
    const facts = Object.entries(r.facts || {}).map(([k, v]) => `${k}：${String(v)}`).join('\n')
    const text = joinLines([
      r.rule_summary,
      facts ? `${t('ai.facts')}：\n${facts}` : '',
      r.risks?.length ? `${t('ai.risks')}：${r.risks.join('；')}` : '',
    ]) || t('ai.noContent')
    await showDialog({ title: t('ai.previewResult'), message: text, confirmButtonText: t('ai.ok') })
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameScene'))) {
      showToast(e instanceof Error ? e.message : t('ai.previewFailed'))
    }
  } finally {
    previewing.value = ''
  }
}

async function openDoc(id: number) {
  try {
    const r = await getSceneDoc(id)
    if (r.ok === false) {
      showToast(r.error || t('ai.noContent'))
      return
    }
    const text = joinLines([
      r.report || r.summary || r.rule_summary,
      r.risks?.length ? `${t('ai.risks')}：${r.risks.join('；')}` : '',
      r.suggestions?.length ? `${t('ai.suggestions')}：${r.suggestions.join('；')}` : '',
    ]) || t('ai.noContent')
    await showDialog({ title: t('ai.docDetail'), message: text, confirmButtonText: t('ai.ok') })
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameScene'))) {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  }
}

async function copyDoc(id: number) {
  try {
    const r = await getSceneDoc(id)
    const facts = Object.entries(r.facts || {}).map(([k, v]) => `${k}：${String(v)}`).join('\n')
    const text = joinLines([
      r.report || r.summary || r.rule_summary,
      facts ? `${t('ai.facts')}：\n${facts}` : '',
      r.risks?.length ? `${t('ai.risks')}：${r.risks.join('；')}` : '',
      r.suggestions?.length ? `${t('ai.suggestions')}：${r.suggestions.join('；')}` : '',
    ])
    if (!text) {
      showToast(t('ai.noContent'))
      return
    }
    const done = await copyToClipboard(text)
    showToast(done ? t('ai.docCopied') : t('ai.docCopyFailed'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
  }
}

async function exportDocMd(id: number) {
  try {
    const r = await getSceneDoc(id)
    if (r.ok === false) {
      showToast(r.error || t('ai.noContent'))
      return
    }
    const facts = Object.entries(r.facts || {}).map(([k, v]) => `- ${k}: ${String(v)}`).join('\n')
    const parts = [
      `# ${r.title || t('ai.docDetail')}`,
      '',
      facts ? `\n## ${t('ai.facts')}\n${facts}` : '',
      r.risks?.length ? `\n## ${t('ai.risks')}\n${r.risks.map((x) => `- ${x}`).join('\n')}` : '',
      r.suggestions?.length ? `\n## ${t('ai.suggestions')}\n${r.suggestions.map((x) => `- ${x}`).join('\n')}` : '',
      `\n## ${t('ai.helpAnswer')}\n\n${r.report || r.summary || r.rule_summary || ''}`,
    ].filter(Boolean)
    const done = downloadText(`scene-${r.doc_type || 'doc'}-${id}.md`, parts.join('\n'))
    showToast(done ? t('ai.exportDone') : t('ai.exportFailed'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.exportFailed'))
  }
}

async function removeDoc(id: number) {
  try {
    await showConfirmDialog({
      title: t('ai.delete'),
      message: t('ai.deleteDocConfirm'),
      confirmButtonText: t('ai.ok'),
    })
  } catch {
    return
  }
  try {
    await deleteSceneDoc(id)
    await loadDocs()
    showToast(t('ai.docDeleted'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
  }
}

async function generate(s: SceneScenario) {
  if (running.value) return
  const params = collectParams(s)
  // 交期风险分析需要 plan_no 或 plan_id 才能定位计划，缺则提示
  if (s.code === 'plan_risk' && !params.plan_no && !params.plan_id) {
    showToast(t('ai.planNoRequired'))
    return
  }
  running.value = s.code
  try {
    const r = await generateSceneDoc(s.code, params)
    if (r.ok === false) {
      if ((r as { locked?: boolean }).locked) {
        locked.value = true
        return
      }
      showToast(r.error || t('ai.generateFailed'))
      return
    }
    await showDialog({
      title: t('ai.generateResult'),
      message: r.report || r.rule_summary || t('ai.noContent'),
      confirmButtonText: t('ai.ok'),
    })
    void loadDocs()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameScene')) && !isAccessDenied(e)) {
      showToast(e instanceof Error ? e.message : t('ai.generateFailed'))
    } else if (isAccessDenied(e)) {
      locked.value = true
    }
  } finally {
    running.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-start justify-between gap-2 rounded-xl bg-white p-3 shadow-sm">
      <div class="min-w-0 flex-1">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.sceneTitle') }}</div>
        <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.sceneSubtitle') }}</div>
      </div>
      <van-button size="mini" plain @click="openDocs">{{ t('ai.docs') }}</van-button>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameScene') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
    </div>

    <van-empty v-else-if="!scenarios.length" :description="t('ai.noData')" />

    <template v-else>
      <div v-for="s in scenarios" :key="s.code" class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ s.name }}</div>
            <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ s.desc }}</div>
          </div>
          <div class="flex shrink-0 gap-1">
            <van-button size="mini" plain :loading="previewing === s.code" @click="preview(s)">{{ t('ai.preview') }}</van-button>
            <van-button size="mini" type="primary" plain :loading="running === s.code" @click="generate(s)">{{ t('ai.generate') }}</van-button>
          </div>
        </div>
        <div v-if="s.fields && s.fields.length" class="mt-2 space-y-1">
          <div v-for="f in s.fields" :key="f.key" class="flex items-center gap-2">
            <span class="w-24 shrink-0 truncate text-[11px] text-zinc-500">{{ f.label }}</span>
            <select
              v-if="f.type === 'select'"
              v-model="values[s.code][f.key]"
              class="min-w-0 flex-1 rounded border border-zinc-200 px-2 py-1 text-xs"
            >
              <option value="">{{ t('ai.fieldOptional') }}</option>
              <option v-for="o in f.options || []" :key="o" :value="o">{{ o }}</option>
            </select>
            <input
              v-else
              v-model="values[s.code][f.key]"
              :type="f.type === 'number' ? 'number' : 'text'"
              :placeholder="f.placeholder || t('ai.fieldOptional')"
              class="min-w-0 flex-1 rounded border border-zinc-200 px-2 py-1 text-xs"
            />
          </div>
        </div>
      </div>
    </template>

    <van-popup v-model:show="docsOpen" position="bottom" round class="pb-safe" :style="{ height: '60%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.docs') }}<span v-if="docTotal" class="ml-1 text-[11px] text-zinc-400">/ {{ docTotal }}</span></div>
        <van-button size="mini" plain @click="openDocs">{{ t('ai.refresh') }}</van-button>
      </div>
      <div class="border-b border-zinc-100 px-3 py-2">
        <select v-model="docType" class="w-full rounded border border-zinc-200 px-2 py-1 text-xs" @change="loadDocs()">
          <option value="">{{ t('ai.docFilterType') }}</option>
          <option v-for="s in scenarios" :key="s.code" :value="s.code">{{ s.name }}</option>
        </select>
      </div>
      <div class="h-[calc(100%-93px)] overflow-y-auto px-3 py-2">
        <div v-if="docsLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <van-empty v-else-if="!docs.length" :description="t('ai.noDocs')" />
        <template v-else>
          <div class="space-y-2">
            <div v-for="d in docs" :key="d.id" class="rounded-xl bg-zinc-50 p-3" @click="openDoc(d.id)">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm text-zinc-800">{{ d.title }}</div>
                  <div v-if="d.excerpt" class="mt-1 line-clamp-2 text-[11px] text-zinc-500">{{ d.excerpt }}</div>
                  <div class="mt-1 text-[10px] text-zinc-400">{{ d.type_name || d.doc_type }} · {{ d.created_at || '' }}</div>
                </div>
                <div class="flex shrink-0 flex-col gap-1">
                  <van-button size="mini" plain @click.stop="copyDoc(d.id)">{{ t('ai.copy') }}</van-button>
                  <van-button size="mini" plain @click.stop="exportDocMd(d.id)">{{ t('ai.exportMd') }}</van-button>
                  <van-button size="mini" plain type="danger" @click.stop="removeDoc(d.id)">{{ t('ai.delete') }}</van-button>
                </div>
              </div>
            </div>
          </div>
          <div v-if="docs.length < docTotal" class="py-2 text-center">
            <van-button size="mini" plain :loading="docLoadingMore" @click="loadMoreDocs">{{ t('ai.loadMore') }}</van-button>
          </div>
        </template>
      </div>
    </van-popup>
  </div>
</template>
