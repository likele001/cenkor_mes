<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { tenantH5Path } from '@/utils/tenant'

const router = useRouter()
const taskCode = ref('')

function go() {
  if (!taskCode.value.trim()) return
  router.push({ path: tenantH5Path('/report-unit'), query: { task_code: taskCode.value.trim() } })
}
</script>

<template>
  <div class="mx-4 mt-4 rounded-xl bg-white p-4 shadow-sm">
    <div class="text-base font-medium text-zinc-800">主动报工</div>
    <div class="mt-1 text-sm text-zinc-500">输入任务码后进入逐件报工</div>
    <van-field v-model="taskCode" class="mt-3" label="任务码" placeholder="扫描或粘贴任务码" />
    <van-button block type="primary" class="mt-4" @click="go">开始逐件报工</van-button>
  </div>
</template>
