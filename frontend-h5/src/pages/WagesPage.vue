<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMySalary, getMySalarySummary, type H5SalaryItem, type H5SalarySummary } from '@/api/tasks'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const summary = ref<H5SalarySummary[]>([])
const items = ref<H5SalaryItem[]>([])

// 当前选中的月份
const currentMonth = ref('')
// 可选月份范围（当前月往前12个月）
const monthOptions = ref<{ text: string; value: string }[]>([])

const yearToDateAmount = computed(() => {
  // 汇总所有月份的工资（当前页面的 summary 默认只返回当月）
  // 如果有多个月份的汇总则加起来
  return summary.value.reduce((a, s) => a + s.total_amount, 0)
})

const yearToDateQty = computed(() => {
  return summary.value.reduce((a, s) => a + s.total_qty, 0)
})

function formatMoney(v: number): string {
  return v.toFixed(2)
}

function buildMonthOptions() {
  const now = new Date()
  const opts: { text: string; value: string }[] = []
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    opts.push({ text: `${y}年${m}月`, value: `${y}-${m}` })
  }
  monthOptions.value = opts
}

async function refresh() {
  loading.value = true
  try {
    const monthFromQuery = (route.query.month as string) || ''
    if (monthFromQuery) {
      currentMonth.value = monthFromQuery
    } else {
      const now = new Date()
      currentMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    }

    const [s, i] = await Promise.all([
      getMySalarySummary({ month: currentMonth.value }),
      getMySalary({ month: currentMonth.value }),
    ])
    summary.value = s?.items || []
    items.value = i?.items || []
  } finally {
    loading.value = false
  }
}

function onPrevMonth() {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m - 2, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  router.replace({ query: { month: currentMonth.value } })
}

function onNextMonth() {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m, 1)
  const now = new Date()
  const next = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  // 不能超过当前月
  const nowStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  if (next > nowStr) return
  currentMonth.value = next
  router.replace({ query: { month: currentMonth.value } })
}

const monthSheetShow = ref(false)

const monthSheetActions = computed(() => monthOptions.value.map((o) => ({ name: o.text })))

function openMonthPicker() {
  monthSheetShow.value = true
}

function onMonthSheetSelect(action: { name?: string }) {
  monthSheetShow.value = false
  const opt = monthOptions.value.find((o) => o.text === action.name)
  if (opt) {
    currentMonth.value = opt.value
    router.replace({ query: { month: currentMonth.value } })
  }
}

onMounted(() => {
  buildMonthOptions()
  refresh()
})

watch(
  () => route.query.month,
  () => refresh(),
)
</script>

<template>
  <div>
    <!-- 工资条入口 -->
    <div class="rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 p-4 text-white">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-sm opacity-80">我的工资</div>
          <div class="mt-1 text-xs opacity-70">查看每月工资明细与电子工资条</div>
        </div>
        <van-button size="small" plain round color="white" @click="router.push('/salary/slip')">
          电子工资条
        </van-button>
      </div>
    </div>

    <!-- 月份选择 -->
    <div class="mx-4 -mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-center justify-between">
        <van-button size="small" plain round @click="onPrevMonth">‹ 上月</van-button>
        <div class="flex cursor-pointer items-center gap-1 text-base font-semibold" @click="openMonthPicker">
          {{ currentMonth.replace('-', '年') }}月
          <van-icon name="arrow-down" class="text-xs text-zinc-400" />
        </div>
        <van-button size="small" plain round @click="onNextMonth">下月 ›</van-button>
      </div>
    </div>

    <!-- 月度统计卡片 -->
    <div class="mx-4 mt-3 grid grid-cols-3 gap-3">
      <div class="rounded-xl bg-white p-3 text-center shadow-sm">
        <div class="text-xs text-zinc-500">本月工资</div>
        <div class="mt-1 text-lg font-bold text-orange-500">
          ¥{{ summary.length ? formatMoney(summary.reduce((a, s) => a + s.total_amount, 0)) : '0.00' }}
        </div>
      </div>
      <div class="rounded-xl bg-white p-3 text-center shadow-sm">
        <div class="text-xs text-zinc-500">本月产量</div>
        <div class="mt-1 text-lg font-bold text-zinc-900">
          {{ summary.length ? summary.reduce((a, s) => a + s.total_qty, 0) : 0 }}
        </div>
      </div>
      <div class="rounded-xl bg-white p-3 text-center shadow-sm">
        <div class="text-xs text-zinc-500">{{ currentMonth?.replace('-', '/') }}</div>
        <div class="mt-1 text-lg font-bold text-blue-500">
          {{ items.length }} 条
        </div>
      </div>
    </div>

    <!-- 工资明细列表 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-medium text-zinc-700">工资明细</span>
        <span class="text-xs text-zinc-400">{{ items.length }} 项</span>
      </div>
      <van-cell-group v-if="items.length" inset>
        <van-cell v-for="s in items" :key="s.id">
          <template #title>
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium">工序 #{{ s.process_id }}</span>
              <span class="text-xs text-zinc-400">{{ s.month }}</span>
            </div>
          </template>
          <template #label>
            <div class="mt-0.5 flex flex-wrap gap-2 text-xs text-zinc-400">
              <span>单价 ¥{{ formatMoney(s.unit_price) }}</span>
              <span>合格 {{ s.good_qty }} 件</span>
              <span>{{ s.created_at?.slice(0, 10) || '' }}</span>
            </div>
          </template>
          <template #value>
            <div class="text-sm font-semibold text-orange-500">¥{{ formatMoney(s.amount) }}</div>
          </template>
        </van-cell>
      </van-cell-group>
      <van-empty v-else-if="!loading" description="该月暂无工资数据" />
    </div>

    <van-action-sheet
      v-model:show="monthSheetShow"
      title="选择月份"
      cancel-text="取消"
      :actions="monthSheetActions"
      @select="onMonthSheetSelect"
      @cancel="monthSheetShow = false"
    />

    <div class="h-8" />
  </div>
</template>
