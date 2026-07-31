<template>
  <el-dialog :model-value="open" :title="title" width="720px" destroy-on-close @update:model-value="emit('update:open', $event)">
    <el-tabs :model-value="tab" @update:model-value="emit('update:tab', $event as any)">
      <el-tab-pane label="LLM 建议" name="llm">
        <div v-loading="aiLoading" class="text-sm whitespace-pre-wrap text-zinc-700">{{ text }}</div>
        <ul v-if="list.length" class="mt-3 list-disc pl-5 text-sm text-zinc-600">
          <li v-for="(t, i) in list" :key="i">{{ t }}</li>
        </ul>
      </el-tab-pane>
      <el-tab-pane label="OR-Tools 约束" name="optimizer">
        <div v-loading="optimizeLoading" class="text-sm text-zinc-700">
          <p v-if="lastOptimize?.suggest_start_date">
            方案（{{ lastOptimize.solver || 'rule' }}）：
            {{ lastOptimize.suggest_start_date }} ~ {{ lastOptimize.suggest_end_date }}，
            工期 {{ lastOptimize.suggest_work_days }} 天，总工时 {{ lastOptimize.total_minutes }} 分
          </p>
          <ul v-if="lastOptimize?.notes?.length" class="mt-2 list-disc pl-5">
            <li v-for="(n, i) in lastOptimize.notes" :key="i">{{ n }}</li>
          </ul>
          <p v-else-if="!optimizeLoading" class="text-zinc-400">暂无优化结果</p>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template v-if="mode === 'schedule'" #footer>
      <el-button @click="emit('update:open', false)">关闭</el-button>
      <el-button type="primary" :loading="applying" @click="emit('applyLlm')">采纳 LLM 并执行</el-button>
      <el-button type="success" plain :loading="applying" :disabled="!lastOptimize?.ok" @click="emit('applyOptimizer')">
        采纳 OR-Tools 并执行
      </el-button>
      <el-button @click="router.push(`/plans/${planId}/edit`)">去编辑页</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { PlanOptimizeOut } from '@/api/ai'

const router = useRouter()

defineProps<{
  open: boolean
  title: string
  tab: 'llm' | 'optimizer'
  mode: 'schedule' | 'risk'
  aiLoading: boolean
  optimizeLoading: boolean
  applying: boolean
  text: string
  list: string[]
  planId: number | null
  lastOptimize: PlanOptimizeOut | null
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'update:tab', val: 'llm' | 'optimizer'): void
  (e: 'applyLlm'): void
  (e: 'applyOptimizer'): void
}>()
</script>
