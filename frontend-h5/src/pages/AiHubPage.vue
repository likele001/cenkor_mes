<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const entries = [
  { path: '/ai-assistant', icon: '🤖', color: 'text-indigo-500', title: '工厂助手', desc: '对话式查询产量、订单、齐套、设备与毛利' },
  { path: '/ai-alerts', icon: '⚠️', color: 'text-orange-500', title: '数据预警', desc: '六维主动体检，异常自动跟踪处置' },
  { path: '/ai-employees', icon: '💬', color: 'text-green-500', title: 'AI 员工', desc: '一键委托只读巡检，生成工作简报' },
  { path: '/ai-insight', icon: '📊', color: 'text-cyan-500', title: '深度洞察', desc: '质量/SPC/设备/交期/成本趋势分析' },
  { path: '/ai-scene', icon: '📝', color: 'text-amber-500', title: '场景文书', desc: '交接班记录、待审报工摘要、交期风险' },
  { path: '/help', icon: '💡', color: 'text-blue-500', title: '智能帮助', desc: '检索系统文档，解答操作问题' },
]
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-gradient-to-r from-violet-500 to-indigo-600 p-4 text-white shadow-sm">
      <div class="text-lg font-semibold">智能中心</div>
      <div class="mt-1 text-xs opacity-90">AI 能力均为付费扩展，未开通时会提示前往应用市场开通；飞书通知为核心免费能力。</div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div
        v-for="e in entries"
        :key="e.path"
        class="rounded-xl bg-white p-4 shadow-sm active:bg-zinc-50"
        @click="router.push(e.path)"
      >
        <div :class="['text-2xl', e.color]">{{ e.icon }}</div>
        <div class="mt-2 text-sm font-medium text-zinc-800">{{ e.title }}</div>
        <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ e.desc }}</div>
      </div>
    </div>
  </div>
</template>
