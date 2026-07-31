<template>
  <div class="push-stats-row grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 cursor-pointer" @click="goToLogs">
    <el-card v-loading="loading" class="stat-card" shadow="hover">
      <div class="text-xs text-zinc-500">{{ t('pushStats.todayTotal') }}</div>
      <div class="text-2xl font-semibold mt-1">{{ stats.today_total ?? 0 }}</div>
      <div class="text-[10px] text-zinc-400 mt-1">
        <span class="mr-2">F: {{ stats.by_channel?.feishu?.total ?? 0 }}</span>
        <span>W: {{ stats.by_channel?.wecom?.total ?? 0 }}</span>
      </div>
    </el-card>
    <el-card v-loading="loading" class="stat-card" shadow="hover">
      <div class="text-xs text-zinc-500">{{ t('pushStats.success') }}</div>
      <div class="text-2xl font-semibold mt-1 text-green-600">{{ stats.today_success ?? 0 }}</div>
    </el-card>
    <el-card v-loading="loading" class="stat-card" shadow="hover">
      <div class="text-xs text-zinc-500">{{ t('pushStats.failed') }}</div>
      <div class="text-2xl font-semibold mt-1 text-red-600">{{ stats.today_failed ?? 0 }}</div>
    </el-card>
    <el-card v-loading="loading" class="stat-card" shadow="hover">
      <div class="text-xs text-zinc-500">{{ t('pushStats.retryRate') }}</div>
      <div class="text-2xl font-semibold mt-1">{{ stats.retry_rate ?? 0 }}%</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { http } from '@/utils/http'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const stats = ref<{
  today_total: number
  today_success: number
  today_failed: number
  today_retry: number
  retry_rate: number
  by_channel: { feishu: { total: number }; wecom: { total: number } }
}>({
  today_total: 0,
  today_success: 0,
  today_failed: 0,
  today_retry: 0,
  retry_rate: 0,
  by_channel: { feishu: { total: 0 }, wecom: { total: 0 } },
} as never)

async function load() {
  loading.value = true
  try {
    const res = await http.request<typeof stats.value>({
      url: '/dashboard/push-stats',
      method: 'GET',
    })
    stats.value = res
  } catch {
    // 静默失败，不影响首页其他内容
  } finally {
    loading.value = false
  }
}

function goToLogs() {
  router.push({ path: '/system/message-center', query: { tab: 'logs' } })
}

onMounted(load)
</script>
