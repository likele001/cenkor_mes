<template>
  <!-- 生产日历 -->
  <el-dialog :model-value="calendarOpen" width="980px" title="生产日历" destroy-on-close @update:model-value="emit('update:calendarOpen', $event)">
    <div v-loading="calendarLoading">
      <div class="mb-3 flex items-center gap-2 flex-wrap">
        <div class="text-xs text-zinc-500">月份</div>
        <el-date-picker :model-value="calendarMonth" type="month" value-format="YYYY-MM" :clearable="false" style="width: 140px" @update:model-value="emit('update:calendarMonth', $event as string)" />
        <div class="text-xs text-zinc-400">默认产能：{{ calendarDefaultCapacity }} {{ capacityUnitLabel }}</div>
      </div>
      <div class="flex flex-col gap-3 lg:grid lg:grid-cols-2">
        <div class="border rounded hidden lg:block">
          <el-table :data="calendarRows" height="520" border @row-click="(row: any) => emit('selectCalendarDay', row.day)">
            <el-table-column prop="day" label="日期" width="120" />
            <el-table-column prop="weekday_label" label="星期" width="80" />
            <el-table-column label="工作" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_workday ? 'success' : 'info'">{{ row.is_workday ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="产能" width="110">
              <template #default="{ row }">
                <span>{{ row.is_workday ? row.capacity_minutes : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="覆盖" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.has_override" type="warning">覆盖</el-tag>
                <span v-else class="text-zinc-400">默认</span>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" />
          </el-table>
        </div>

        <div class="lg:hidden border rounded p-2 max-h-[min(42vh,360px)] overflow-y-auto space-y-2 bg-zinc-50/50">
          <div
            v-for="row in calendarRows"
            :key="row.day"
            class="admin-mobile-row cursor-pointer transition-shadow"
            :class="calendarSelectedDay === row.day ? 'ring-2 ring-[var(--el-color-primary)]' : ''"
            @click="emit('selectCalendarDay', row.day)"
          >
            <div class="admin-mobile-row__head">
              <div>
                <div class="font-medium text-sm">{{ row.day }} · 周{{ row.weekday_label }}</div>
                <div class="text-xs text-zinc-500 mt-0.5">
                  产能 {{ row.is_workday ? row.capacity_minutes : '—' }} 分
                  <span v-if="row.has_override" class="ml-2 text-amber-600">已覆盖</span>
                </div>
              </div>
              <el-tag :type="row.is_workday ? 'success' : 'info'" size="small">{{ row.is_workday ? '工作日' : '休息' }}</el-tag>
            </div>
            <div v-if="row.remark" class="text-xs text-zinc-600 mt-1">{{ row.remark }}</div>
          </div>
        </div>

        <div class="border rounded p-3 lg:min-h-0">
          <div class="font-medium mb-2">日期：{{ calendarSelectedDay || '-' }}</div>
          <div v-if="calendarSelectedDay" class="space-y-3">
            <div class="flex items-center gap-3">
              <div class="text-sm text-zinc-600 w-20 shrink-0">工作日</div>
              <el-switch :model-value="calendarFormIsWorkday" @update:model-value="emit('update:calendarFormIsWorkday', $event as any)" />
            </div>
            <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div class="text-sm text-zinc-600 w-20 shrink-0">产能(分)</div>
              <div class="flex flex-wrap items-center gap-2">
                <el-input-number
                  :model-value="calendarFormCapacity"
                  :min="0"
                  :max="10000"
                  :controls="false"
                  class="!w-36"
                  :disabled="!calendarFormIsWorkday"
                  @update:model-value="emit('update:calendarFormCapacity', $event ?? 0)"
                />
                <div class="text-xs text-zinc-400">留空/0=使用默认</div>
              </div>
            </div>
            <div class="flex flex-col gap-2">
              <div class="text-sm text-zinc-600 w-20">备注</div>
              <el-input :model-value="calendarFormRemark" placeholder="可选" @update:model-value="emit('update:calendarFormRemark', $event as any)" />
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <el-button type="primary" :loading="calendarSaving" @click="emit('saveCalendarDay')">保存</el-button>
              <el-button :loading="calendarResetting" @click="emit('resetCalendarDay')">清除覆盖</el-button>
            </div>
          </div>
          <el-empty v-else description="点击日历中的日期进行设置" />
        </div>
      </div>
    </div>
  </el-dialog>

  <!-- 车间日产能 -->
  <el-dialog :model-value="workshopCapOpen" width="720px" title="车间日产能（分钟/天）" destroy-on-close @update:model-value="emit('update:workshopCapOpen', $event)">
    <div v-loading="workshopCapLoading">
      <div class="mb-3 text-xs text-zinc-500">默认产能：{{ workshopCapDefault }} {{ capacityUnitLabel }}（未覆盖的车间按默认产能）</div>
      <el-table class="hidden lg:block" :data="workshopCapRows" border height="520">
        <el-table-column prop="workshop" label="车间" min-width="220" />
        <el-table-column label="日产能(分)" width="220">
          <template #default="{ row }">
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
            <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
        <div v-for="(row, i) in workshopCapRows" :key="`w-${i}-${row.workshop}`" class="admin-mobile-row">
          <div class="font-medium text-sm">{{ row.workshop }}</div>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <span class="text-xs text-zinc-500 shrink-0">日产能(分)</span>
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
            <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </div>
        </div>
      </div>
      <div class="mt-3 flex justify-end gap-2">
        <el-button :loading="workshopCapSaving" type="primary" @click="emit('saveWorkshopCapacity')">保存</el-button>
      </div>
    </div>
  </el-dialog>

  <!-- 人员日产能 -->
  <el-dialog :model-value="userCapOpen" width="720px" :title="`人员日产能（${capacityUnitLabel}）`" destroy-on-close @update:model-value="emit('update:userCapOpen', $event)">
    <div v-loading="userCapLoading">
      <div class="mb-3 text-xs text-zinc-500">
        默认产能：{{ userCapDefault }} {{ capacityUnitLabel }}；仅显示「员工」角色（与自动派工一致）
      </div>
      <el-table class="hidden lg:block" :data="userCapRows" border height="520">
        <el-table-column prop="name" label="人员" min-width="220" />
        <el-table-column :label="`日产能(${capacityUnitLabel})`" width="220">
          <template #default="{ row }">
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
            <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
        <div v-for="(row, i) in userCapRows" :key="`u-${i}-${row.user_id}`" class="admin-mobile-row">
          <div class="font-medium text-sm">{{ row.name }}</div>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <span class="text-xs text-zinc-500 shrink-0">日产能({{ capacityUnitLabel }})</span>
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
            <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </div>
        </div>
      </div>
      <div class="mt-3 flex justify-end gap-2">
        <el-button :loading="userCapSaving" type="primary" @click="emit('saveUserCapacity')">保存</el-button>
      </div>
    </div>
  </el-dialog>

  <!-- 设备日产能 -->
  <el-dialog :model-value="equipCapOpen" width="720px" title="设备日产能（分钟/天）" destroy-on-close @update:model-value="emit('update:equipCapOpen', $event)">
    <div v-loading="equipCapLoading">
      <div class="mb-3 text-xs text-zinc-500">默认产能：{{ equipCapDefault }} {{ capacityUnitLabel }}（未覆盖的设备按默认产能）</div>
      <el-table class="hidden lg:block" :data="equipCapRows" border height="520">
        <el-table-column prop="name" label="设备" min-width="260" />
        <el-table-column label="日产能(分)" width="220">
          <template #default="{ row }">
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
            <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
        <div v-for="(row, i) in equipCapRows" :key="`e-${i}-${row.equipment_id}`" class="admin-mobile-row">
          <div class="font-medium text-sm">{{ row.name }}</div>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <span class="text-xs text-zinc-500 shrink-0">日产能(分)</span>
            <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
            <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
          </div>
        </div>
      </div>
      <div class="mt-3 flex justify-end gap-2">
        <el-button :loading="equipCapSaving" type="primary" @click="emit('saveEquipmentCapacity')">保存</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  capacityUnitLabel: string
  // Calendar
  calendarOpen: boolean
  calendarLoading: boolean
  calendarMonth: string
  calendarDefaultCapacity: number
  calendarRows: any[]
  calendarSelectedDay: string
  calendarFormIsWorkday: boolean
  calendarFormCapacity: number
  calendarFormRemark: string
  calendarSaving: boolean
  calendarResetting: boolean
  // Workshop capacity
  workshopCapOpen: boolean
  workshopCapLoading: boolean
  workshopCapSaving: boolean
  workshopCapDefault: number
  workshopCapRows: { workshop: string; capacity_minutes: number }[]
  // User capacity
  userCapOpen: boolean
  userCapLoading: boolean
  userCapSaving: boolean
  userCapDefault: number
  userCapRows: { user_id: number; name: string; capacity_minutes: number }[]
  // Equipment capacity
  equipCapOpen: boolean
  equipCapLoading: boolean
  equipCapSaving: boolean
  equipCapDefault: number
  equipCapRows: { equipment_id: number; name: string; capacity_minutes: number }[]
}>()

const emit = defineEmits<{
  (e: 'update:calendarOpen', val: boolean): void
  (e: 'update:workshopCapOpen', val: boolean): void
  (e: 'update:userCapOpen', val: boolean): void
  (e: 'update:equipCapOpen', val: boolean): void
  (e: 'update:calendarFormIsWorkday', val: boolean): void
  (e: 'update:calendarFormCapacity', val: number): void
  (e: 'update:calendarFormRemark', val: string): void
  (e: 'update:calendarMonth', val: string): void
  (e: 'selectCalendarDay', day: string): void
  (e: 'saveCalendarDay'): void
  (e: 'resetCalendarDay'): void
  (e: 'saveWorkshopCapacity'): void
  (e: 'saveUserCapacity'): void
  (e: 'saveEquipmentCapacity'): void
}>()
</script>
