<template>
  <div>
    <div class="mb-2 flex items-center gap-2 flex-wrap">
      <el-radio-group :model-value="capacityUnit" size="small" @change="emit('capacityUnitChange', $event as any)">
        <el-radio-button value="pieces">{{ t('production.plans.capacityPieces') }}</el-radio-button>
        <el-radio-button value="minutes">{{ t('production.plans.capacityMinutes') }}</el-radio-button>
      </el-radio-group>
      <div class="text-xs text-zinc-500">默认日产能（{{ capacityUnitLabel }}）</div>
      <el-input-number :model-value="loadCapacity" :min="1" :max="10000" :controls="false" style="width: 140px" @change="emit('loadCapacityChange', $event ?? 0)" />
      <el-button size="small" :loading="capacitySaving" @click="emit('saveCapacity')">{{ t('production.plans.saveAsDefault') }}</el-button>
      <el-button size="small" @click="emit('openCalendar')">{{ t('production.plans.workCalendar') }}</el-button>
      <el-button size="small" @click="emit('openWorkshopCapacity')">{{ t('production.plans.workshopCapacity') }}</el-button>
      <el-button size="small" @click="emit('openUserCapacity')">{{ t('production.plans.userCapacity') }}</el-button>
      <el-button size="small" @click="emit('openEquipmentCapacity')">{{ t('production.plans.equipmentCapacity') }}</el-button>
      <el-button size="small" type="primary" plain :loading="autoDispatchLoading" @click="emit('runAutoDispatch')">{{ t('production.plans.autoDispatch') }}</el-button>
      <div v-if="capacityUnit === 'pieces'" class="text-xs text-zinc-400">计件：每人/车间每天可完成的合格件数</div>
      <div v-else class="text-xs text-zinc-400">参考：480=8小时</div>
      <div class="hidden lg:block text-xs text-blue-600 w-full">{{ t('gantt.dragHint') }}</div>
    </div>

    <!-- 移动端 -->
    <div class="lg:hidden space-y-3 mt-2" v-loading="planLoadLoading">
      <template v-if="ganttDays.length">
        <div class="text-sm font-medium text-zinc-700">日负荷（点行查看明细）</div>
        <div class="space-y-2">
          <div
            v-for="d in ganttDays"
            :key="`m-load-${d}`"
            class="admin-mobile-row transition-colors"
            :class="
              loadMap.get(d)?.is_workday === false
                ? 'opacity-60'
                : 'active:bg-[var(--el-fill-color-light)] cursor-pointer'
            "
            @click="emit('openLoadDetail', d)"
          >
            <div class="flex justify-between items-center gap-2">
              <span class="font-medium text-el-primary">{{ d }}</span>
              <el-tag v-if="loadMap.get(d)?.is_workday === false" size="small" type="info">休</el-tag>
              <el-tag v-else-if="loadMap.get(d)?.overload" size="small" type="danger">超负荷 {{ fmtLoad(loadMap.get(d)?.count) }}</el-tag>
              <span v-else class="text-sm text-el-regular">{{ fmtLoad(loadMap.get(d)?.count) }}</span>
            </div>
          </div>
        </div>
        <el-collapse class="border border-[var(--el-border-color-light)] rounded-lg overflow-hidden">
          <el-collapse-item v-for="p in items" :key="`m-gantt-${p.id}`" :name="String(p.id)">
            <template #title>
              <div class="flex flex-col items-start gap-0.5 min-w-0 py-0.5">
                <span class="font-medium text-el-primary text-sm truncate max-w-[85vw]">{{ p.code }}</span>
                <span class="text-xs text-zinc-500 truncate max-w-[85vw]">
                  <span v-if="p.order_code">{{ p.order_code }}</span>
                  <span v-if="p.customer_name"> · {{ p.customer_name }}</span>
                </span>
              </div>
            </template>
            <div class="space-y-2 pb-1">
              <dl class="admin-mobile-kv">
                <dt>状态</dt>
                <dd><el-tag :type="statusTagType(p.status)" size="small">{{ statusLabel(p.status) }}</el-tag></dd>
                <dt>数量</dt>
                <dd>{{ p.qty }}</dd>
                <dt>工期</dt>
                <dd class="text-left">{{ p.start_date || '—' }} ~ {{ p.end_date || '—' }}（{{ p.work_days ?? '—' }} 天）</dd>
              </dl>
              <div v-if="barStyle(p)" class="space-y-1">
                <div class="text-xs text-zinc-500">排产占比（相对当前视图）</div>
                <div class="h-2 bg-zinc-100 rounded-full overflow-hidden">
                  <div class="h-full bg-blue-500/90 rounded-full transition-all" :style="{ width: barWidthPercent(p) }" />
                </div>
              </div>
              <div class="admin-mobile-actions">
                <el-button size="small" @click="router.push(`/plans/${p.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
                <el-button size="small" @click="emit('checkKit', p.id)">{{ t('production.plans.kitCheck') }}</el-button>
                <el-button
                  v-if="p.can_release"
                  size="small"
                  type="primary"
                  :loading="releasingId === p.id"
                  @click="emit('releasePlan', p)"
                >
                  确认下发
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </template>
      <el-empty v-else description="计划暂无起止日期，无法展示甘特" />
    </div>

    <!-- PC端 -->
    <div v-if="ganttDays.length" class="hidden lg:block border rounded overflow-x-auto">
      <div class="flex text-xs bg-zinc-50 border-b" :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }">
        <div class="shrink-0 px-2 py-2 font-medium border-r" :style="{ width: `${labelWidth}px` }">{{ t('production.plans.planned') }}</div>
        <div class="flex">
          <div v-for="d in ganttDays" :key="d" class="px-1 py-2 text-center border-r last:border-r-0 text-zinc-600" :style="{ width: `${dayWidth}px` }">
            {{ d.slice(5) }}
          </div>
        </div>
      </div>

      <div class="flex text-[11px] bg-white border-b" :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }">
        <div class="shrink-0 px-2 py-2 font-medium border-r text-zinc-600" :style="{ width: `${labelWidth}px` }">负荷（分钟/天）</div>
        <div class="flex">
          <div
            v-for="d in ganttDays"
            :key="`load-${d}`"
            class="px-1 py-2 text-center border-r last:border-r-0"
            :class="
              loadMap.get(d)?.is_workday === false
                ? 'bg-zinc-50 text-zinc-300'
                : loadMap.get(d)?.overload
                  ? 'bg-red-50 text-red-600 font-medium cursor-pointer'
                  : 'text-zinc-500 cursor-pointer'
            "
            :style="{ width: `${dayWidth}px` }"
            @click="emit('openLoadDetail', d)"
          >
            {{ loadMap.get(d)?.is_workday === false ? '休' : fmtLoad(loadMap.get(d)?.count) }}
          </div>
        </div>
      </div>

      <div v-for="p in items" :key="p.id" class="flex border-b last:border-b-0" :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }">
        <div class="shrink-0 px-2 py-2 border-r text-sm" :style="{ width: `${labelWidth}px` }">
          <div class="font-medium">{{ p.code }}</div>
          <div class="text-xs text-zinc-500 truncate">
            <span v-if="p.order_code">{{ p.order_code }}</span>
            <span v-if="p.customer_name"> · {{ p.customer_name }}</span>
          </div>
        </div>
        <div class="relative" :style="{ width: `${ganttDays.length * dayWidth}px` }">
          <div class="absolute inset-0 flex">
            <div v-for="d in ganttDays" :key="`${p.id}-${d}`" class="border-r last:border-r-0" :style="{ width: `${dayWidth}px` }" />
          </div>
          <div
            v-if="barStyleWithDrag(p)"
            class="absolute top-[10px] h-[14px] rounded bg-blue-500/80 cursor-grab active:cursor-grabbing hover:bg-blue-600/90 transition-colors"
            :class="{ 'ring-2 ring-blue-300': ganttDrag.planId === p.id }"
            :style="barStyleWithDrag(p) as any"
            @pointerdown.stop.prevent="onGanttBarDown($event, p)"
          />
        </div>
      </div>
    </div>
    <el-empty v-else class="hidden lg:block" description="暂无可展示计划" />
    <el-empty v-if="!items.length" class="lg:hidden mt-2" description="暂无可展示计划" />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { ElMessage } from 'element-plus'
import { plansApi, type PlanOut, type PlanLoadItemOut } from '@/api/plans'

const { t } = useI18n()
const { label: statusLabel, type: statusTagType } = useStatus('plan')
const router = useRouter()

const props = defineProps<{
  items: PlanOut[]
  ganttDays: string[]
  loadMap: Map<string, PlanLoadItemOut>
  planLoadLoading: boolean
  capacityUnit: 'pieces' | 'minutes'
  capacityUnitLabel: string
  loadCapacity: number
  capacitySaving: boolean
  autoDispatchLoading: boolean
  releasingId: number | null
  dayWidth: number
  labelWidth: number
}>()

const emit = defineEmits<{
  (e: 'capacityUnitChange', unit: 'pieces' | 'minutes'): void
  (e: 'loadCapacityChange', val: number): void
  (e: 'saveCapacity'): void
  (e: 'openCalendar'): void
  (e: 'openWorkshopCapacity'): void
  (e: 'openUserCapacity'): void
  (e: 'openEquipmentCapacity'): void
  (e: 'runAutoDispatch'): void
  (e: 'openLoadDetail', day: string): void
  (e: 'checkKit', planId: number): void
  (e: 'releasePlan', row: PlanOut): void
  (e: 'reload'): void
}>()



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
  if (props.capacityUnit === 'pieces') return `${Math.round(n)}件`
  return fmtMinutes(n)
}

function barStyle(p: PlanOut) {
  const days = props.ganttDays
  if (!days.length) return null
  const s = p.start_date || p.end_date
  const e = p.end_date || p.start_date
  if (!s || !e) return null
  const startIdx = days.indexOf(s)
  const endIdx = days.indexOf(e)
  if (startIdx < 0 || endIdx < 0) return null
  return { left: `${startIdx * props.dayWidth}px`, width: `${(endIdx - startIdx + 1) * props.dayWidth}px` }
}

const ganttDrag = reactive({
  planId: null as number | null,
  startX: 0,
  offsetPx: 0,
  saving: false,
})

function barStyleWithDrag(p: PlanOut) {
  const base = barStyle(p)
  if (!base) return null
  if (ganttDrag.planId === p.id && ganttDrag.offsetPx) {
    const leftNum = parseFloat(String(base.left)) + ganttDrag.offsetPx
    return { ...base, left: `${leftNum}px`, opacity: 0.9, zIndex: 20 }
  }
  return base
}

function barWidthPercent(p: PlanOut) {
  const days = props.ganttDays
  if (!days.length) return '0%'
  const s = p.start_date || p.end_date
  const e = p.end_date || p.start_date
  if (!s || !e) return '0%'
  const startIdx = days.indexOf(s)
  const endIdx = days.indexOf(e)
  if (startIdx < 0 || endIdx < 0) return '0%'
  const span = endIdx - startIdx + 1
  const pct = (span / days.length) * 100
  return `${Math.min(100, Math.max(2, pct)).toFixed(1)}%`
}

function addDays(dateStr: string, n: number): string {
  const d = new Date(`${dateStr}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function diffDaysInclusive(a: string, b: string): number {
  const da = new Date(`${a}T12:00:00`).getTime()
  const db = new Date(`${b}T12:00:00`).getTime()
  return Math.round((db - da) / 86400000) + 1
}

function onGanttPointerMove(e: PointerEvent) {
  if (ganttDrag.planId == null) return
  ganttDrag.offsetPx = e.clientX - ganttDrag.startX
}

async function onGanttPointerUp() {
  window.removeEventListener('pointermove', onGanttPointerMove)
  window.removeEventListener('pointerup', onGanttPointerUp)
  const planId = ganttDrag.planId
  const offsetPx = ganttDrag.offsetPx
  ganttDrag.planId = null
  ganttDrag.offsetPx = 0
  if (!planId || !offsetPx) return
  const p = props.items.find((x) => x.id === planId)
  if (!p?.start_date || !p?.end_date) return
  const shift = Math.round(offsetPx / props.dayWidth)
  if (shift === 0) return
  const newStart = addDays(p.start_date, shift)
  const newEnd = addDays(p.end_date, shift)
  ganttDrag.saving = true
  try {
    await plansApi.updatePlan(planId, {
      start_date: newStart,
      end_date: newEnd,
      work_days: diffDaysInclusive(newStart, newEnd),
    })
    ElMessage.success(t('gantt.dragSaved'))
    emit('reload')
  } catch {
    ElMessage.error(t('gantt.dragFailed'))
  } finally {
    ganttDrag.saving = false
  }
}

function onGanttBarDown(e: PointerEvent, p: PlanOut) {
  if (ganttDrag.saving || !p.start_date || !p.end_date) return
  ganttDrag.planId = p.id
  ganttDrag.startX = e.clientX
  ganttDrag.offsetPx = 0
  window.addEventListener('pointermove', onGanttPointerMove)
  window.addEventListener('pointerup', onGanttPointerUp)
}

onUnmounted(() => {
  window.removeEventListener('pointermove', onGanttPointerMove)
  window.removeEventListener('pointerup', onGanttPointerUp)
})
</script>
