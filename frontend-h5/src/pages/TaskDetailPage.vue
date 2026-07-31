<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import type { TagType } from 'vant/es/tag/types'
import { getTaskDetail, getTaskQr, type H5Task, type TaskQrOut } from '@/api/tasks'
import { svgToDataUrl } from '@/utils/qr'
import { tenantH5Path } from '@/utils/tenant'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const task = ref<H5Task | null>(null)
const taskQr = ref<TaskQrOut | null>(null)
const taskQrImg = computed(() => (taskQr.value?.svg ? svgToDataUrl(taskQr.value.svg) : ''))

const taskCode = computed(() => String(route.params.id || ''))

function statusLabel(s: string | undefined) {
  if (s === 'pending') return '待开始'
  if (s === 'working') return '进行中'
  if (s === 'done') return '已完成'
  return s || '—'
}

function statusTagType(s: string | undefined): TagType {
  if (s === 'pending') return 'primary'
  if (s === 'working') return 'warning'
  if (s === 'done') return 'success'
  return 'default'
}

async function load() {
  const code = taskCode.value.trim()
  if (!code) return
  loading.value = true
  try {
    const [detail, qr] = await Promise.all([getTaskDetail(code), getTaskQr(code).catch(() => null)])
    task.value = detail
    taskQr.value = qr
  } finally {
    loading.value = false
  }
}

function goReport() {
  const code = taskCode.value.trim()
  if (!code) return
  const path = task.value?.use_unit_report === false ? '/report' : '/report-unit'
  router.push({ path: tenantH5Path(path), query: { task_code: code } })
}

function copyCode() {
  const code = taskCode.value.trim()
  if (!code) return
  navigator.clipboard?.writeText(code)
  showToast('已复制任务码')
}

watch(taskCode, load, { immediate: true })
</script>

<template>
  <div>
    <!-- 任务头部 -->
    <div class="rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 p-4 text-white">
      <div class="flex items-center justify-between">
        <div class="text-sm opacity-80">任务码</div>
        <van-tag :type="statusTagType(task?.status)" plain size="medium" @click="copyCode">
          {{ statusLabel(task?.status) }}
        </van-tag>
      </div>
      <div class="mt-1 flex items-center gap-2">
        <code class="rounded bg-white/20 px-2 py-0.5 font-mono text-lg">{{ taskCode }}</code>
        <svg class="h-4 w-4 cursor-pointer opacity-70" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" @click="copyCode">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      </div>
    </div>

    <!-- 报工二维码（派工后员工扫此码） -->
    <div v-if="taskQrImg" class="mx-4 -mt-3 rounded-xl bg-white p-4 shadow-sm text-center">
      <div class="text-sm font-medium text-zinc-700">我的报工码</div>
      <div class="text-xs text-zinc-500 mt-1">班长也可打印「任务标签」贴现场；您也可直接点下方「开始报工」</div>
      <img :src="taskQrImg" alt="报工二维码" class="mt-3 mx-auto w-44 h-44 block" />
      <div class="mt-2 font-mono text-xs text-zinc-500 break-all">{{ taskCode }}</div>
    </div>

    <!-- 基本信息 -->
    <div class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
        <div>
          <div class="text-xs text-zinc-400">工序</div>
          <div class="mt-0.5 font-medium">{{ task?.process?.name || task?.process?.code || '—' }}</div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">工序编码</div>
          <div class="mt-0.5 font-medium">{{ task?.process?.code || '—' }}</div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">我的派工</div>
          <div class="mt-0.5 font-medium">
            分配 {{ task?.assigned_qty ?? '—' }} / 已报 {{ task?.reported_qty ?? 0 }} / 待报 {{ task?.remaining_qty ?? 0 }}
          </div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">工序顺序</div>
          <div class="mt-0.5 font-medium">第 {{ task?.seq ?? '—' }} 道</div>
        </div>
      </div>
    </div>

    <!-- 设备信息 -->
    <div v-if="task?.equipment" class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="text-xs font-medium text-zinc-500">设备信息</div>
      <div class="mt-2 grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
        <div>
          <div class="text-xs text-zinc-400">设备名称</div>
          <div>{{ task.equipment.name }}</div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">设备编码</div>
          <div>{{ task.equipment.code }}</div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">车间</div>
          <div>{{ task.equipment.workshop || '—' }}</div>
        </div>
        <div>
          <div class="text-xs text-zinc-400">设备状态</div>
          <div>{{ task.equipment.status || '—' }}</div>
        </div>
      </div>
    </div>

    <!-- 工单/订单信息 -->
    <div v-if="task?.work_order" class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="text-xs font-medium text-zinc-500">工单信息</div>
      <div class="mt-2 space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-zinc-400">工单号</span>
          <span>#{{ task.work_order.id }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-zinc-400">关联订单</span>
          <span>#{{ task.work_order.order_id }}</span>
        </div>
        <div v-if="task.work_order.sku" class="flex justify-between">
          <span class="text-zinc-400">产品型号</span>
          <span>{{ task.work_order.sku.code }} {{ task.work_order.sku.name }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-zinc-400">工单数量</span>
          <span>{{ task.work_order.qty }} 件</span>
        </div>
      </div>
    </div>

    <!-- 时间信息 -->
    <div class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="text-xs font-medium text-zinc-500">时间信息</div>
      <div class="mt-2 space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-zinc-400">派工时间</span>
          <span>{{ task?.assigned_at?.slice(0, 16).replace('T', ' ') || '—' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-zinc-400">创建时间</span>
          <span>{{ task?.created_at?.slice(0, 16).replace('T', ' ') || '—' }}</span>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="mt-5 space-y-3 px-2">
      <van-button
        block
        type="primary"
        size="large"
        :disabled="task?.status === 'done'"
        @click="goReport"
      >
        {{ task?.status === 'done' ? '任务已完成' : '开始报工' }}
      </van-button>
      <van-button block size="large" @click="router.push('/tasks')">返回列表</van-button>
    </div>

    <div class="h-6" />
  </div>
</template>
