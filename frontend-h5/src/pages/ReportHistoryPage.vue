<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getMyReportUnits, type ReportUnitItem } from '@/api/reportUnits'

const loading = ref(false)
const items = ref<ReportUnitItem[]>([])

function statusText(s: string) {
  const m: Record<string, string> = {
    draft: '待报',
    submitted: '待初审',
    leader_approved: '待终审',
    qc_approved: '已通过',
    rejected: '已驳回',
  }
  return m[s] || s
}

function resultText(r: string | null) {
  if (r === 'good') return '合格'
  if (r === 'bad') return '不良'
  return '—'
}

async function load() {
  loading.value = true
  try {
    const res = await getMyReportUnits({ limit: 100 })
    items.value = (res.items || []).filter((x) => x.status !== 'draft')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-3">
    <van-list v-model:loading="loading" :finished="true">
      <div v-for="row in items" :key="row.id" class="mb-3 rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ row.task_code || `任务#${row.task_id}` }}</span>
          <van-tag size="medium">{{ statusText(row.status) }}</van-tag>
        </div>
        <div class="mt-2 text-sm text-zinc-500 space-y-1">
          <div>件次：第 {{ row.unit_seq }} 件 · {{ resultText(row.result_type) }}</div>
          <div>提交：{{ row.submitted_at?.slice(0, 16).replace('T', ' ') || row.created_at?.slice(0, 16) }}</div>
          <div v-if="row.remark">备注：{{ row.remark }}</div>
        </div>
      </div>
      <van-empty v-if="!loading && !items.length" description="暂无报工记录" />
    </van-list>
  </div>
</template>
