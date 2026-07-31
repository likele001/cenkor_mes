<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getMyOrderProgress, type CustomerOrderProgress } from '@/api/customer'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const data = ref<CustomerOrderProgress | null>(null)
const orderId = computed(() => Number(route.params.id))

function toPercent(v: number | null) {
  if (typeof v !== 'number') return 0
  const p = Math.round(v * 10000) / 100
  if (p < 0) return 0
  if (p > 100) return 100
  return p
}

function statusLabel(s: string) {
  if (s === 'draft') return t('customer.status.draft')
  if (s === 'confirmed') return t('customer.status.confirmed')
  return s || '—'
}

async function load() {
  const id = orderId.value
  if (!id) return
  loading.value = true
  try {
    data.value = await getMyOrderProgress(id)
  } finally {
    loading.value = false
  }
}

watch(orderId, load, { immediate: true })
</script>

<template>
  <div>
    <van-cell-group inset>
      <van-cell :title="t('customer.orderProgress.orderNo')" :value="data?.code || '—'" />
      <van-cell :title="t('customer.orderProgress.status')" :value="statusLabel(data?.status || '')" />
      <van-cell :title="t('customer.orderProgress.dueDate')" :value="data?.due_date || '—'" />
      <van-cell :title="t('customer.orderProgress.quantity')" :value="`${data?.done_qty ?? 0}/${data?.total_qty ?? 0}`" />
    </van-cell-group>

    <div class="mt-3 px-3">
      <van-progress :percentage="toPercent(data?.progress ?? null)" />
    </div>

    <div class="mt-4">
      <van-loading v-if="loading" class="mx-auto" />
    </div>

    <div v-if="data" class="mt-4">
      <div class="px-3 text-[14px] font-semibold text-zinc-700">{{ t('customer.orderProgress.workOrders') }}</div>

      <div v-for="wo in data.work_orders" :key="wo.id" class="mt-2">
        <van-cell-group inset>
          <van-cell :title="wo.sku ? (wo.sku.display_name || wo.sku.name) : t('customer.orderProgress.workOrders')" :value="`${wo.done_qty}/${wo.qty}`">
            <template #label>
              <div class="mt-2">
                <van-progress :percentage="toPercent(wo.progress)" :show-pivot="false" />
              </div>
              <div v-if="wo.tasks?.length" class="mt-3 flex flex-col gap-2">
                <div v-for="task in wo.tasks" :key="task.id" class="rounded bg-zinc-50 px-2 py-2">
                  <div class="flex items-center justify-between gap-2 text-[12px] text-zinc-700">
                    <div class="truncate">{{ task.process ? `${task.seq}. ${task.process.name}` : `${task.seq}. —` }}</div>
                    <div class="shrink-0">{{ task.done_qty }}/{{ task.planned_qty }} {{ task.status }}</div>
                  </div>
                  <div class="mt-2">
                    <van-progress :percentage="toPercent(task.progress)" :show-pivot="false" stroke-width="6" />
                  </div>
                </div>
              </div>
              <div v-else class="mt-2 text-[12px] text-zinc-500">{{ t('customer.orderProgress.noTask') }}</div>
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </div>

    <div class="mt-6 px-4">
      <van-button block @click="router.push({ name: 'customerOrderDetail', params: { id: orderId } })">{{ t('customer.orderProgress.returnOrder') }}</van-button>
    </div>

    <div class="mt-3 px-4">
      <van-button block @click="router.push({ name: 'customerOrder' })">{{ t('customer.orderProgress.returnList') }}</van-button>
    </div>
  </div>
</template>
