<template>
  <AdminPage :title="t('dashboard.kanbanDetail.title')">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="flex items-center gap-2">
          <el-button @click="router.back()">{{ t('dashboard.kanbanDetail.back') }}</el-button>
          <div class="text-[16px] font-semibold">{{ t('dashboard.kanbanDetail.title') }}</div>
        </div>
        <el-button @click="reload" :loading="loading">{{ t('dashboard.kanbanDetail.refresh') }}</el-button>
      </div>

      <div class="mt-4" v-loading="loading">
        <template v-if="data">
          <el-descriptions :column="3" border>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.orderNo')">{{ data.code }}</el-descriptions-item>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.customer')">{{ data.customer ? partyOptionLabel(data.customer) : '-' }}</el-descriptions-item>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.status')">{{ statusLabel(data.status) }}</el-descriptions-item>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.deliveryDate')">{{ data.due_date || '-' }}</el-descriptions-item>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.totalQty')">{{ data.total_qty }}</el-descriptions-item>
            <el-descriptions-item :label="t('dashboard.kanbanDetail.doneQty')">{{ data.done_qty }}</el-descriptions-item>
          </el-descriptions>

          <div class="mt-4">
            <el-progress :percentage="toPercent(data.progress)" :stroke-width="14" :text-inside="true" :format="() => percentLabel(data.progress)" />
          </div>

          <div class="mt-6 text-[14px] font-semibold">{{ t('dashboard.kanbanDetail.processProgressOverview') }}</div>
          <div class="mt-3 flex flex-wrap gap-4">
            <div v-for="p in processProgress" :key="p.processId" class="flex flex-col items-center w-[100px]">
              <el-progress type="circle" :percentage="toPercent(p.progress)" :width="80" :stroke-width="6">
                <span class="text-xs font-semibold">{{ toPercent(p.progress) }}%</span>
              </el-progress>
              <div class="mt-2 text-xs text-center leading-tight">{{ p.processName }}</div>
              <div class="text-[11px] text-zinc-500">{{ p.doneQty }}/{{ p.totalQty }}</div>
            </div>
            <div v-if="!processProgress.length" class="text-sm text-zinc-400 py-2">{{ t('dashboard.kanbanDetail.noProcessData') }}</div>
          </div>

          <div class="mt-6 text-[14px] font-semibold">{{ t('dashboard.kanbanDetail.orderDetail') }}</div>
          <el-table class="hidden lg:block mt-3 w-full" :data="data.items" border>
            <el-table-column prop="line_no" :label="t('dashboard.kanbanDetail.lineNo')" width="90" />
            <el-table-column :label="t('dashboard.kanbanDetail.sku')" min-width="260">
              <template #default="{ row }">{{ row.sku ? skuRowLabel({ sku: row.sku }) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="qty" :label="t('dashboard.kanbanDetail.quantity')" width="120" />
            <el-table-column prop="remark" :label="t('dashboard.kanbanDetail.remark')" min-width="260" />
          </el-table>
          <div class="lg:hidden space-y-3 mt-3">
            <div v-for="row in data.items" :key="row.line_no" class="admin-mobile-row">
              <div class="text-xs text-el-placeholder">{{ t('dashboard.kanbanDetail.line') }} {{ row.line_no }}</div>
              <div class="font-medium text-sm">{{ row.sku ? skuRowLabel({ sku: row.sku }) : '-' }}</div>
              <dl class="admin-mobile-kv mt-2">
                <dt>{{ t('dashboard.kanbanDetail.quantity') }}</dt>
                <dd>{{ row.qty }}</dd>
                <dt>{{ t('dashboard.kanbanDetail.remark') }}</dt>
                <dd class="text-left">{{ row.remark || '—' }}</dd>
              </dl>
            </div>
          </div>

          <div class="mt-6 text-[14px] font-semibold">{{ t('dashboard.kanbanDetail.workOrderProgress') }}</div>
          <el-table class="hidden lg:block mt-3 w-full" :data="data.work_orders" border row-key="id">
            <el-table-column type="expand">
              <template #default="{ row }">
                <el-table :data="row.tasks" border>
                  <el-table-column prop="seq" :label="t('dashboard.kanbanDetail.seq')" width="90" />
                  <el-table-column prop="task_code" :label="t('dashboard.kanbanDetail.taskCode')" width="220" />
                  <el-table-column :label="t('dashboard.kanbanDetail.process')" min-width="220">
                    <template #default="{ row: t }">{{ t.process ? processRowLabel({ process: t.process }) : '-' }}</template>
                  </el-table-column>
                  <el-table-column prop="planned_qty" :label="t('dashboard.kanbanDetail.planned')" width="110" />
                  <el-table-column prop="done_qty" :label="t('dashboard.kanbanDetail.completed')" width="110" />
                  <el-table-column :label="t('dashboard.kanbanDetail.progress')" min-width="240">
                    <template #default="{ row: t }">
                      <el-progress :percentage="toPercent(t.progress)" :stroke-width="10" :text-inside="true" :format="() => percentLabel(t.progress)" />
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" :label="t('dashboard.kanbanDetail.status')" width="130" />
                </el-table>
              </template>
            </el-table-column>
            <el-table-column prop="id" :label="t('dashboard.kanbanDetail.workOrderId')" width="110" />
            <el-table-column :label="t('dashboard.kanbanDetail.sku')" min-width="260">
              <template #default="{ row }">{{ row.sku ? skuRowLabel({ sku: row.sku }) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="qty" :label="t('dashboard.kanbanDetail.quantity')" width="110" />
            <el-table-column prop="done_qty" :label="t('dashboard.kanbanDetail.completed')" width="110" />
            <el-table-column :label="t('dashboard.kanbanDetail.progress')" min-width="260">
              <template #default="{ row }">
                <el-progress :percentage="toPercent(row.progress)" :stroke-width="10" :text-inside="true" :format="() => percentLabel(row.progress)" />
              </template>
            </el-table-column>
            <el-table-column prop="status" :label="t('dashboard.kanbanDetail.status')" width="130" />
          </el-table>
          <div class="lg:hidden space-y-3 mt-3">
            <div v-for="wo in data.work_orders" :key="wo.id" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <div class="min-w-0">
                  <div class="font-semibold text-sm">{{ t('dashboard.kanbanDetail.workOrder') }} #{{ wo.id }}</div>
                  <div class="text-xs text-el-placeholder">{{ wo.sku ? skuRowLabel({ sku: wo.sku }) : '-' }}</div>
                </div>
                <el-tag size="small">{{ wo.status }}</el-tag>
              </div>
              <div class="text-xs text-el-regular mb-2">{{ t('dashboard.kanbanDetail.quantity') }} {{ wo.done_qty }}/{{ wo.qty }}</div>
              <el-progress :percentage="toPercent(wo.progress)" :stroke-width="12" :text-inside="true" :format="() => percentLabel(wo.progress)" />
              <div v-if="wo.tasks?.length" class="mt-3 space-y-2 border-t border-[var(--el-border-color-lighter)] pt-3">
                <div v-for="task in wo.tasks" :key="String(task.task_code) + '-' + task.seq" class="rounded-lg bg-[#fafafa] p-2 text-sm">
                  <div class="font-mono text-xs text-el-regular">{{ task.task_code }}</div>
                  <div class="text-xs">{{ task.process ? `${task.process.name}` : '—' }} · {{ t('dashboard.kanbanDetail.planned') }} {{ task.planned_qty }} {{ t('dashboard.kanbanDetail.completed') }} {{ task.done_qty }}</div>
                  <el-progress class="mt-1" :percentage="toPercent(task.progress)" :stroke-width="8" :text-inside="true" :format="() => percentLabel(task.progress)" />
                  <el-tag size="small" class="mt-1">{{ task.status }}</el-tag>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { kanbanApi, type KanbanOrderDetailOut } from '@/api/kanban'
import { partyOptionLabel, processRowLabel, skuRowLabel } from '@/utils/display'

const { t } = useI18n()
const { label: statusLabel } = useStatus('order')
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const data = ref<KanbanOrderDetailOut | null>(null)

type ProcessProgress = {
  processId: number
  processName: string
  totalQty: number
  doneQty: number
  progress: number | null
}

const processProgress = computed<ProcessProgress[]>(() => {
  const d = data.value
  if (!d?.work_orders) return []
  const map = new Map<number, ProcessProgress>()
  for (const wo of d.work_orders) {
    for (const t of wo.tasks || []) {
      if (!t.process) continue
      const pid = t.process.id
      const existing = map.get(pid)
      if (existing) {
        existing.totalQty += t.planned_qty
        existing.doneQty += t.done_qty
      } else {
        map.set(pid, {
          processId: pid,
          processName: t.process.name,
          totalQty: t.planned_qty,
          doneQty: t.done_qty,
          progress: null,
        })
      }
    }
  }
  const result = Array.from(map.values())
  for (const p of result) {
    p.progress = p.totalQty > 0 ? p.doneQty / p.totalQty : null
  }
  return result.sort((a, b) => {
    const aMin = Math.min(...(d?.work_orders ?? []).flatMap(wo =>
      (wo.tasks ?? []).filter(t => t.process?.id === a.processId).map(t => t.seq)
    ), Infinity)
    const bMin = Math.min(...(d?.work_orders ?? []).flatMap(wo =>
      (wo.tasks ?? []).filter(t => t.process?.id === b.processId).map(t => t.seq)
    ), Infinity)
    return aMin - bMin
  })
})



function toPercent(v: number | null) {
  if (typeof v !== 'number') return 0
  const p = Math.round(v * 10000) / 100
  if (p < 0) return 0
  if (p > 100) return 100
  return p
}

function percentLabel(v: number | null) {
  if (typeof v !== 'number') return '-'
  return `${toPercent(v)}%`
}

async function reload() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    data.value = await kanbanApi.getOrder(id)
  } finally {
    loading.value = false
  }
}

onMounted(() => reload())
</script>

