<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { showToast } from 'vant'
import { listAiAlerts, runAiAlerts, type AlertItem } from '@/api/ai'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const scanning = ref(false)
const items = ref<AlertItem[]>([])

const canAi = computed(() => auth.hasPermission('ai.use'))

async function load() {
  loading.value = true
  try {
    const res = await listAiAlerts()
    items.value = res.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function scan() {
  scanning.value = true
  try {
    const res = await runAiAlerts()
    showToast(`扫描 ${res.events ?? 0} 条`)
    await load()
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '扫描失败')
  } finally {
    scanning.value = false
  }
}

function levelLabel(level: string) {
  if (level === 'danger') return '严重'
  return '预警'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between rounded-xl bg-white p-4 shadow-sm">
      <div>
        <div class="text-sm font-semibold text-zinc-800">AI 数据预警</div>
        <div class="mt-0.5 text-xs text-zinc-500">共 {{ items.length }} 条</div>
      </div>
      <van-button v-if="canAi" size="small" type="primary" plain :loading="scanning" @click="scan">立即扫描</van-button>
    </div>

    <van-loading v-if="loading" class="py-8 text-center" />

    <div v-else-if="!items.length" class="rounded-xl bg-white p-8 text-center text-sm text-zinc-400 shadow-sm">
      暂无预警
    </div>

    <div v-else class="space-y-2">
      <div v-for="a in items" :key="a.id" class="rounded-xl bg-white p-4 shadow-sm">
        <div class="flex items-start gap-2">
          <van-tag :type="a.level === 'danger' ? 'danger' : 'warning'" plain>{{ levelLabel(a.level) }}</van-tag>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ a.title }}</div>
            <div v-if="a.summary" class="mt-1 text-xs leading-relaxed text-zinc-500">{{ a.summary }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
