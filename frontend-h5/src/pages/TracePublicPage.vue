<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { showToast } from 'vant'
import { getPublicTrace, publicTraceMediaUrl, type PublicTraceDetail } from '@/api/publicTrace'

const route = useRoute()
const loading = ref(false)
const detail = ref<PublicTraceDetail | null>(null)

const traceCode = computed(() => {
  const q = route.query.id || route.query.code
  return typeof q === 'string' ? q.trim() : ''
})

const tenantCode = computed(() => {
  const q = route.query.tenant
  return typeof q === 'string' ? q.trim() : ''
})

async function load() {
  if (!traceCode.value) return
  loading.value = true
  detail.value = null
  try {
    detail.value = await getPublicTrace(traceCode.value, tenantCode.value || undefined)
  } catch {
    showToast('未找到追溯信息')
  } finally {
    loading.value = false
  }
}

function mediaSrc(m: { id: number; url?: string | null }) {
  return publicTraceMediaUrl(m.id, traceCode.value, m.url)
}

function fmtTime(v: string | null | undefined) {
  if (!v) return '—'
  return String(v).slice(0, 19).replace('T', ' ')
}

onMounted(load)
watch(traceCode, load)
</script>

<template>
  <div class="trace-page min-h-screen bg-gradient-to-b from-indigo-50 to-white pb-10">
    <div class="trace-hero px-4 py-8 text-center text-white">
      <h1 class="text-2xl font-bold">产品追溯信息</h1>
      <p class="mt-2 text-sm opacity-90">扫描二维码，轻松获取产品全生命周期信息</p>
    </div>

    <div class="mx-4 -mt-6">
      <van-loading v-if="loading" class="py-16" vertical>正在加载产品信息...</van-loading>

      <template v-else-if="detail">
        <div class="rounded-2xl bg-white p-4 shadow-lg">
          <div class="font-mono text-lg font-bold text-indigo-700 break-all">{{ detail.product_code }}</div>
          <div v-if="detail.piece_no" class="mt-1 text-sm text-zinc-500">第 {{ detail.piece_no }} 套</div>

          <van-divider />

          <div class="space-y-3 text-sm">
            <div class="flex"><span class="w-20 text-zinc-500">产品</span><span>{{ detail.product_name || '—' }}</span></div>
            <div class="flex"><span class="w-20 text-zinc-500">型号</span><span>{{ detail.sku_code }} {{ detail.sku_name }}</span></div>
            <div class="flex"><span class="w-20 text-zinc-500">订单</span><span>{{ detail.order_name || detail.order_code || '—' }}</span></div>
            <div v-if="detail.customer_name" class="flex"><span class="w-20 text-zinc-500">客户</span><span>{{ detail.customer_name }}</span></div>
          </div>
        </div>

        <div v-if="detail.flow_steps?.length" class="mt-4 rounded-2xl bg-white p-4 shadow">
          <h2 class="mb-3 font-semibold text-zinc-800">生产工序记录</h2>
          <van-steps direction="vertical" :active="detail.flow_steps.length - 1">
            <van-step v-for="(step, idx) in detail.flow_steps" :key="idx">
              <div class="font-medium">{{ step.process_name || '工序' }}</div>
              <div class="text-xs text-zinc-500">{{ fmtTime(step.time) }} · {{ step.operator }}</div>
            </van-step>
          </van-steps>
        </div>

        <div v-if="detail.media?.length" class="mt-4 rounded-2xl bg-white p-4 shadow">
          <h2 class="mb-3 font-semibold text-zinc-800">质检影像</h2>
          <div class="grid grid-cols-2 gap-2">
            <template v-for="m in detail.media" :key="m.id">
              <img v-if="m.kind === 'image'" :src="mediaSrc(m)" class="rounded-lg w-full aspect-square object-cover" alt="" />
              <video v-else :src="mediaSrc(m)" class="rounded-lg w-full aspect-square object-cover" controls />
            </template>
          </div>
        </div>
      </template>

      <van-empty v-else-if="!loading && !traceCode" description="请扫描产品追溯码" />
      <van-empty v-else-if="!loading" description="未找到追溯信息" />
    </div>

    <p class="mt-8 text-center text-xs text-zinc-400">透明可追溯，品质有保障</p>
  </div>
</template>

<style scoped>
.trace-hero {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
</style>
