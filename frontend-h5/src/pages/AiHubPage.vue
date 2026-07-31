<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const canAi = computed(() => auth.hasPermission('ai.use'))
const canAiAlert = computed(() => auth.hasPermission('ai.alert.view'))
const canAiEmployee = computed(() => auth.hasPermission('ai_employee.use'))

const links = computed(() => {
  const items = [
    { title: '智能帮助', desc: '检索文档，解答操作问题', icon: '💡', path: '/help', tone: 'blue', show: true },
    { title: '工厂助手', desc: '问产量、待审报工、订单进度', icon: '🤖', path: '/ai-assistant', tone: 'violet', show: canAi.value },
    { title: '数据预警', desc: '查看 AI 扫描的异常提醒', icon: '⚠️', path: '/ai-alerts', tone: 'orange', show: canAiAlert.value },
    { title: 'AI 员工', desc: '与配置好的 AI 员工对话', icon: '👤', path: '/ai-employees', tone: 'green', show: canAiEmployee.value },
  ]
  return items.filter((x) => x.show)
})

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-xl bg-gradient-to-r from-violet-500 to-indigo-600 p-4 text-white">
      <div class="text-lg font-semibold">智能中心</div>
      <div class="mt-1 text-xs opacity-90">帮助 · 助手 · 预警，一站式 AI 入口</div>
    </div>

    <div v-if="!links.length" class="rounded-xl bg-white p-6 text-center text-sm text-zinc-500 shadow-sm">
      当前账号暂无 AI 相关权限
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="item in links"
        :key="item.path"
        class="flex cursor-pointer items-center gap-3 rounded-xl bg-white p-4 shadow-sm"
        @click="go(item.path)"
      >
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl"
          :class="{
            'bg-blue-50': item.tone === 'blue',
            'bg-violet-50': item.tone === 'violet',
            'bg-orange-50': item.tone === 'orange',
            'bg-green-50': item.tone === 'green',
          }"
        >
          {{ item.icon }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold text-zinc-800">{{ item.title }}</div>
          <div class="mt-0.5 text-xs text-zinc-500">{{ item.desc }}</div>
        </div>
        <span class="text-zinc-300">›</span>
      </div>
    </div>
  </div>
</template>
