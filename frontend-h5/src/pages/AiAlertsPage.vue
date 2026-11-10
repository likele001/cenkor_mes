<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import { handleAlert, listAiAlerts, runAiAlerts, type AlertItem } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const loading = ref(true)
const locked = ref(false)
const scanning = ref(false)
const items = ref<AlertItem[]>([])

const SEV_TEXT: Record<string, string> = { critical: '严重', warning: '一般', info: '提示', high: '严重', mid: '一般', low: '提示' }
const SEV_TYPE: Record<string, 'danger' | 'warning' | 'primary'> = { critical: 'danger', high: 'danger', warning: 'warning', mid: 'warning', info: 'primary', low: 'primary' }

function sevText(s?: string) {
  return SEV_TEXT[s || ''] || '提示'
}
function sevType(s?: string) {
  return SEV_TYPE[s || ''] || 'primary'
}

async function load() {
  loading.value = true
  try {
    const res = await listAiAlerts()
    items.value = res.items || []
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

async function scan() {
  scanning.value = true
  try {
    const r = await runAiAlerts()
    showToast(`扫描完成，新增/更新 ${r.events ?? 0} 条`)
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, 'AI 异常预警')) {
      showToast(e instanceof Error ? e.message : '扫描失败')
    }
  } finally {
    scanning.value = false
  }
}

async function openAlert(a: AlertItem) {
  const lines = [a.detail, a.root_cause ? `根因：${a.root_cause}` : '', a.suggestion ? `建议：${a.suggestion}` : '']
    .filter(Boolean)
    .join('\n\n')
  await showDialog({ title: a.title, message: lines || '暂无详情', confirmButtonText: '知道了' })
}

async function resolveAlert(a: AlertItem) {
  try {
    await showConfirmDialog({ title: '标记已处理', message: `确认将「${a.title}」标记为已处理？` })
  } catch {
    return
  }
  try {
    await handleAlert(a.id, 'resolved')
    showToast('已标记处理')
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, 'AI 异常预警')) {
      showToast(e instanceof Error ? e.message : '操作失败')
    }
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between rounded-xl bg-white p-3 shadow-sm">
      <div>
        <div class="text-sm font-medium text-zinc-800">AI 数据预警</div>
        <div class="mt-1 text-[11px] text-zinc-500">报工/进度/交期/齐套/设备/质量六维主动体检</div>
      </div>
      <van-button size="small" type="primary" plain :loading="scanning" :disabled="locked" @click="scan">扫描</van-button>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">加载中…</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">「AI 异常预警」未开通 / 未授权</div>
      <div class="mt-2 text-xs text-zinc-400">请在应用市场的扩展应用中开通，并由管理员为当前账号授权后使用。</div>
    </div>

    <van-empty v-else-if="!items.length" description="暂无预警" />

    <div v-else class="space-y-2">
      <div v-for="a in items" :key="a.id" class="rounded-xl bg-white p-3 shadow-sm" @click="openAlert(a)">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <van-tag :type="sevType(a.level)" plain>{{ sevText(a.level) }}</van-tag>
              <span class="truncate text-sm font-medium text-zinc-800">{{ a.title }}</span>
            </div>
            <div v-if="a.detail" class="mt-1 line-clamp-2 text-xs text-zinc-500">{{ a.detail }}</div>
            <div class="mt-1 text-[11px] text-zinc-400">
              {{ a.dim_label || '' }}<span v-if="a.entity_name"> · {{ a.entity_name }}</span>
              <span v-if="a.last_seen_at"> · {{ a.last_seen_at }}</span>
            </div>
          </div>
          <van-tag plain type="default">{{ a.status_label || a.status || '待处理' }}</van-tag>
        </div>
        <div v-if="a.status !== 'resolved'" class="mt-2 text-right">
          <van-button size="mini" plain @click.stop="resolveAlert(a)">标记已处理</van-button>
        </div>
      </div>
    </div>
  </div>
</template>
