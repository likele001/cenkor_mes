<script setup lang="ts">
import { ref } from 'vue'
import { showToast } from 'vant'
import { aiHelp } from '@/api/ai'

const question = ref('')
const loading = ref(false)
const answer = ref('')
const sources = ref<Array<{ source: string; title: string }>>([])

async function ask() {
  const q = question.value.trim()
  if (!q) return
  loading.value = true
  answer.value = ''
  sources.value = []
  try {
    const res = await aiHelp(q)
    answer.value = res.answer
    sources.value = res.sources || []
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '帮助暂不可用')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="rounded-xl bg-white p-4 shadow-sm">
      <div class="text-base font-semibold text-zinc-800">智能帮助</div>
      <div class="mt-1 text-xs text-zinc-500">检索系统文档，解答 辰科MES 操作问题</div>
      <van-field
        v-model="question"
        type="textarea"
        rows="3"
        class="mt-3"
        placeholder="例如：如何扫码报工？工资怎么算？"
      />
      <van-button block type="primary" class="mt-3" :loading="loading" @click="ask">提问</van-button>
    </div>

    <div v-if="answer" class="rounded-xl bg-white p-4 shadow-sm">
      <div class="text-sm font-medium text-zinc-700 mb-2">回答</div>
      <div class="text-sm text-zinc-600 whitespace-pre-wrap">{{ answer }}</div>
      <div v-if="sources.length" class="mt-3 pt-3 border-t border-zinc-100">
        <div class="text-xs text-zinc-500 mb-1">参考文档</div>
        <div v-for="(s, i) in sources" :key="i" class="text-xs text-zinc-400">· {{ s.source }} — {{ s.title }}</div>
      </div>
    </div>
  </div>
</template>
