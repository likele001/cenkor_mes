<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { ref } from 'vue'
import { showDialog, showToast } from 'vant'
import { generateSceneDoc } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const locked = ref(false)
const running = ref('')
const planNo = ref('')

const scenarios = [
  { code: 'shift_handover', name: '交接班记录', desc: '汇总本时段报工量、良品/不良与未完成事项' },
  { code: 'pending_audit', name: '待审报工摘要', desc: '汇总积压待审报工，生成催办与审核要点' },
  { code: 'plan_risk', name: '订单交期风险分析', desc: '推演计划交期与剩余工作量，给出处置建议' },
]

async function generate(code: string) {
  if (running.value) return
  const params: Record<string, unknown> = {}
  if (code === 'plan_risk') {
    if (!planNo.value.trim()) {
      showToast('请输入计划/订单编号')
      return
    }
    params.plan_no = planNo.value.trim()
  }
  running.value = code
  try {
    const r = await generateSceneDoc(code, params)
    if (r.ok === false) {
      if ((r as any).locked) {
        locked.value = true
        return
      }
      showToast(r.error || '生成失败')
      return
    }
    await showDialog({ title: '生成结果', message: r.report || r.rule_summary || '暂无内容', confirmButtonText: '知道了' })
  } catch (e: unknown) {
    if (isAccessDenied(e)) {
      locked.value = true
      handleExtensionLocked(e, 'AI 场景文书')
    } else {
      showToast(e instanceof Error ? e.message : '生成失败')
    }
  } finally {
    running.value = ''
  }
}
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">AI 场景文书</div>
      <div class="mt-1 text-[11px] text-zinc-500">基于真实业务数据生成交接/催办/交期文书，只读不改数</div>
      <van-field v-model="planNo" class="mt-2 !px-0" label="计划编号" placeholder="交期风险分析必填" clearable />
    </div>

    <div v-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">「AI 场景文书」未开通 / 未授权</div>
      <div class="mt-2 text-xs text-zinc-400">请在应用市场的扩展应用中开通，并由管理员为当前账号授权后使用。</div>
    </div>

    <div v-for="s in scenarios" :key="s.code" class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-zinc-800">{{ s.name }}</div>
          <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ s.desc }}</div>
        </div>
        <van-button size="small" type="primary" plain :loading="running === s.code" @click="generate(s.code)">
          生成
        </van-button>
      </div>
    </div>
  </div>
</template>
