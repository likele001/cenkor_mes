<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { aiChat } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied, showAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const quickQuestions = computed(() => [t('ai.q1'), t('ai.q2'), t('ai.q3'), t('ai.q4')])

const input = ref('')
const sending = ref(false)
const locked = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const listEl = ref<HTMLElement | null>(null)

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function send(text?: string) {
  const msg = (text ?? input.value).trim()
  if (!msg || sending.value || locked.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg })
  sending.value = true
  void scrollBottom()
  try {
    const res = await aiChat({ message: msg })
    messages.value.push({ role: 'assistant', content: res.reply })
  } catch (e: unknown) {
    messages.value.pop()
    if (handleExtensionLocked(e, t('ai.nameAssistant'))) {
      locked.value = true
    } else if (isAccessDenied(e)) {
      locked.value = true
      showAccessDenied()
    } else {
      showToast(e instanceof Error ? e.message : t('ai.unavailable'))
    }
  } finally {
    sending.value = false
    void scrollBottom()
  }
}

function retry() {
  locked.value = false
}
</script>

<template>
  <div class="flex min-h-[70vh] flex-col">
    <div v-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameAssistant') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
      <van-button class="mt-3" size="small" plain type="primary" @click="retry">{{ t('ai.retry') }}</van-button>
    </div>

    <div v-else-if="!messages.length" class="rounded-xl bg-white p-4 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">{{ t('ai.assistantTitle') }}</div>
      <div class="mt-1 text-xs text-zinc-500">{{ t('ai.assistantSubtitle') }}</div>
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
      <div v-if="sending" class="text-xs text-zinc-400">{{ t('ai.thinking') }}</div>
    </div>

    <div class="sticky bottom-0 mt-3 flex gap-2 bg-zinc-100 pt-2">
      <van-field v-model="input" :placeholder="t('ai.inputPlaceholder')" :disabled="sending || locked" @keyup.enter="send()" />
      <van-button type="primary" :loading="sending" :disabled="locked || !input.trim()" @click="send()">{{ t('ai.send') }}</van-button>
    </div>
  </div>
</template>
