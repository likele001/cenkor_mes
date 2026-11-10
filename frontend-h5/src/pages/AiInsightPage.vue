<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showDialog, showToast } from 'vant'
import { analyzeInsight, listAiInsight, type AiInsightItem } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const loading = ref(true)
const locked = ref(false)
const items = ref<AiInsightItem[]>([])
const generatedAt = ref('')
const analyzing = ref('')

async function load() {
  loading.value = true
  try {
    const r = await listAiInsight()
    items.value = r.items || []
    generatedAt.value = r.generated_at || ''
    locked.value = false
  } catch (e: unknown) {
    items.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else {
      showToast(e instanceof Error ? e.message : '加载失败')
    }
  } finally {
    loading.value = false
  }
}

async function analyze(it: AiInsightItem) {
  analyzing.value = it.axis
  try {
    const r = await analyzeInsight(it.axis)
    await showDialog({
      title: it.name,
      message: r.report || r.rule_summary || r.error || '暂无分析结果',
      confirmButtonText: '知道了',
    })
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, 'AI 深度洞察')) {
      showToast(e instanceof Error ? e.message : '分析失败')
    }
  } finally {
    analyzing.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">AI 深度洞察</div>
      <div class="mt-1 text-[11px] text-zinc-500">五路只读速览：采购、库存、质量、交付、效率</div>
      <div v-if="generatedAt" class="mt-1 text-[11px] text-zinc-400">数据时间：{{ generatedAt }}</div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">加载中…</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">「AI 深度洞察」未开通 / 未授权</div>
      <div class="mt-2 text-xs text-zinc-400">请在应用市场的扩展应用中开通，并由管理员为当前账号授权后使用。</div>
    </div>

    <van-empty v-else-if="!items.length" description="暂无数据" />

    <div v-else class="space-y-2">
      <div v-for="it in items" :key="it.axis" class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ it.name }}</div>
            <div class="mt-1 text-xs leading-relaxed text-zinc-600">
              {{ it.headline || (it.error ? `取数失败：${it.error}` : '暂无数据') }}
            </div>
          </div>
          <van-button size="small" type="primary" plain :loading="analyzing === it.axis" @click="analyze(it)">
            深度分析
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>
