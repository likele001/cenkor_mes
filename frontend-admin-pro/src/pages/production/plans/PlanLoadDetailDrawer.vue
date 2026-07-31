<template>
  <el-drawer :model-value="open" size="720px" :title="`负荷明细：${day || '-'}`" destroy-on-close @update:model-value="emit('update:open', $event)">
    <div v-loading="loading">
      <!-- PC：表格 -->
      <div class="hidden lg:block">
        <el-table v-if="workshops.length" class="mb-3" :data="workshops" border>
          <el-table-column prop="workshop" label="车间" min-width="160" />
          <el-table-column label="负荷" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.minutes) }}</span></template>
          </el-table-column>
          <el-table-column label="产能" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.capacity) }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-table v-if="users.length" class="mb-3" :data="users" border>
          <el-table-column prop="name" label="人员" min-width="160" />
          <el-table-column label="负荷" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.minutes) }}</span></template>
          </el-table-column>
          <el-table-column label="产能" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.capacity) }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-table v-if="equipments.length" class="mb-3" :data="equipments" border>
          <el-table-column prop="name" label="设备" min-width="160" />
          <el-table-column label="负荷" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.minutes) }}</span></template>
          </el-table-column>
          <el-table-column label="产能" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.capacity) }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-table v-if="detailItems.length" :data="detailItems" border>
          <el-table-column prop="code" label="计划编号" width="180" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="日期范围" min-width="220">
            <template #default="{ row }"><span>{{ row.start_date || '-' }} ~ {{ row.end_date || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="负荷贡献" width="140">
            <template #default="{ row }"><span>{{ fmtLoad(row.daily_minutes) }}</span></template>
          </el-table-column>
          <el-table-column label="总工时" width="120">
            <template #default="{ row }"><span>{{ fmtLoad(row.total_minutes) }}</span></template>
          </el-table-column>
          <el-table-column label="采购入库" width="160">
            <template #default="{ row }"><span>{{ row.purchase_received_qty }} / {{ row.purchase_total_qty }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 移动端：折叠 + 卡片 -->
      <el-collapse :model-value="mobileCollapse" class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg">
        <el-collapse-item title="车间负荷" name="ws">
          <div v-if="workshops.length" class="space-y-2">
            <div v-for="(row, i) in workshops" :key="`ws-${i}-${row.workshop}`" class="admin-mobile-row">
              <div class="font-medium text-sm">{{ row.workshop }}</div>
              <dl class="admin-mobile-kv mt-2">
                <dt>负荷</dt><dd>{{ fmtLoad(row.minutes) }}</dd>
                <dt>产能</dt><dd>{{ fmtLoad(row.capacity) }}</dd>
                <dt>状态</dt><dd><el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag></dd>
              </dl>
            </div>
          </div>
          <el-empty v-else description="暂无" :image-size="64" />
        </el-collapse-item>
        <el-collapse-item title="人员负荷" name="user">
          <div v-if="users.length" class="space-y-2">
            <div v-for="(row, i) in users" :key="`u-${i}-${row.name}`" class="admin-mobile-row">
              <div class="font-medium text-sm">{{ row.name }}</div>
              <dl class="admin-mobile-kv mt-2">
                <dt>负荷</dt><dd>{{ fmtLoad(row.minutes) }}</dd>
                <dt>产能</dt><dd>{{ fmtLoad(row.capacity) }}</dd>
                <dt>状态</dt><dd><el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag></dd>
              </dl>
            </div>
          </div>
          <el-empty v-else description="暂无" :image-size="64" />
        </el-collapse-item>
        <el-collapse-item title="设备负荷" name="eq">
          <div v-if="equipments.length" class="space-y-2">
            <div v-for="(row, i) in equipments" :key="`e-${i}-${row.name}`" class="admin-mobile-row">
              <div class="font-medium text-sm">{{ row.name }}</div>
              <dl class="admin-mobile-kv mt-2">
                <dt>负荷</dt><dd>{{ fmtLoad(row.minutes) }}</dd>
                <dt>产能</dt><dd>{{ fmtLoad(row.capacity) }}</dd>
                <dt>状态</dt><dd><el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag></dd>
              </dl>
            </div>
          </div>
          <el-empty v-else description="暂无" :image-size="64" />
        </el-collapse-item>
        <el-collapse-item title="计划贡献" name="plans">
          <div v-if="detailItems.length" class="space-y-2">
            <div v-for="row in detailItems" :key="row.id" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <span class="font-medium text-sm">{{ row.code }}</span>
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </div>
              <dl class="admin-mobile-kv">
                <dt>日期</dt><dd class="text-left">{{ row.start_date || '—' }} ~ {{ row.end_date || '—' }}</dd>
                <dt>负荷贡献</dt><dd>{{ fmtLoad(row.daily_minutes) }}</dd>
                <dt>总工时</dt><dd>{{ fmtLoad(row.total_minutes) }}</dd>
                <dt>采购入库</dt><dd>{{ row.purchase_received_qty }} / {{ row.purchase_total_qty }}</dd>
              </dl>
              <div class="admin-mobile-actions">
                <el-button size="small" type="primary" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无计划明细" :image-size="64" />
        </el-collapse-item>
      </el-collapse>

      <el-empty
        v-if="!loading && !workshops.length && !users.length && !equipments.length && !detailItems.length"
        class="mt-2"
        description="暂无明细"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import type {
  PlanLoadDetailItemOut,
  PlanLoadWorkshopOut,
  PlanLoadUserOut,
  PlanLoadEquipmentOut,
} from '@/api/plans'

const { t } = useI18n()
const router = useRouter()
const { label: statusLabel, type: statusTagType } = useStatus('plan')

defineProps<{
  open: boolean
  loading: boolean
  day: string
  workshops: PlanLoadWorkshopOut[]
  users: PlanLoadUserOut[]
  equipments: PlanLoadEquipmentOut[]
  detailItems: PlanLoadDetailItemOut[]
  capacityUnit: 'pieces' | 'minutes'
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const mobileCollapse = ref(['ws', 'user', 'eq', 'plans'])

function fmtMinutes(v?: number | null) {
  if (v === null || v === undefined) return '-'
  if (!Number.isFinite(v)) return '-'
  const n = Number(v)
  if (n >= 60) return `${(n / 60).toFixed(n >= 600 ? 0 : 1)}h`
  return `${Math.round(n)}m`
}

function fmtLoad(v?: number | null) {
  if (v === null || v === undefined || !Number.isFinite(v)) return '-'
  const n = Number(v)
  // capacityUnit is always 'minutes' in load detail context (minutes-based)
  return fmtMinutes(n)
}


</script>
