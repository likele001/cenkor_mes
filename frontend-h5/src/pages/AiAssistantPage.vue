<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { showToast } from 'vant'
import { aiChat } from '@/api/ai'
import { handleExtensionLocked } from '@/utils/extension-gate'

const quickQuestions = ['今天产量和良率怎么样？', '有哪些待审核订单？', '设备保养逾期或点检风险？', '本月毛利率情况？']

const input = ref('')
const sending = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const listEl = ref<HTMLElement | null>(null)

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function send(text?: string) {
  const msg = (text ?? input.value).trim()
  if (!msg || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg })
  sending.value = true
  void scrollBottom()
  try {
    const res = await aiChat({ message: msg })
    messages.value.push({ role: 'assistant', content: res.reply })
  } catch (e: unknown) {
    messages.value.pop()
    if (!handleExtensionLocked(e, 'AI 助手（工厂助手）')) {
      showToast(e instanceof Error ? e.message : 'AI 暂不可用')
    }
  } finally {
    sending.value = false
    void scrollBottom()
  }
}
</script>

<template>
  <div class="flex min-h-[70vh] flex-col">
    <div v-if="!messages.length" class="rounded-xl bg-white p-4 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">工厂助手</div>
      <div class="mt-1 text-xs text-zinc-500">全厂智能助手：产量、订单、齐套、CRM、采购、设备、毛利率与预警</div>
      <div class="mt-3 flex flex-wrap gap-2">
        <van-tag
          v-for="q in quickQuestions"
          :key="q"
          plain
          type="primary"
          size="large"
          class="cursor-pointer"
          @click="send(q)"
        >
          {{ q }}
        </van-tag>
      </div>
    </div>

    <div v-else ref="listEl" class="flex-1 space-y-3 overflow-y-auto pb-2">
      <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
        <div
          class="max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm leading-relaxed shadow-sm"
          :class="m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-white text-zinc-700'"
        >{{ m.content }}</div>
      </div>
      <div v-if="sending" class="text-xs text-zinc-400">AI 正在思考…</div>
    </div>

    <div class="sticky bottom-0 mt-3 flex gap-2 bg-zinc-100 pt-2">
      <van-field v-model="input" placeholder="输入问题…" :disabled="sending" @keyup.enter="send()" />
      <van-button type="primary" :loading="sending" :disabled="!input.trim()" @click="send()">发送</van-button>
    </div>
  </div>
</template>
