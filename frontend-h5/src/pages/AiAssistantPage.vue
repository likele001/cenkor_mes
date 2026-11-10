<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showToast } from 'vant'
import {
  aiChat, deleteAssistantConversation, getAssistantConversation,
  listAssistantConversations, renameAssistantConversation, type AssistantConversation,
} from '@/api/ai'
import { handleExtensionLocked, isAccessDenied, showAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const quickQuestions = computed(() => [t('ai.q1'), t('ai.q2'), t('ai.q3'), t('ai.q4')])

const input = ref('')
const sending = ref(false)
const locked = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const listEl = ref<HTMLElement | null>(null)

const convId = ref<number | null>(null)
const conversations = ref<AssistantConversation[]>([])
const historyOpen = ref(false)
const historyLoading = ref(false)
const renamingId = ref<number | null>(null)
const renameText = ref('')
const renaming = ref(false)

const currentTitle = computed(() => {
  if (!convId.value) return t('ai.newChat')
  const hit = conversations.value.find((c) => c.id === convId.value)
  return hit?.title || t('ai.currentConv', { id: convId.value })
})

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function loadConversations() {
  try {
    const r = await listAssistantConversations()
    conversations.value = r.items || []
  } catch {
    conversations.value = []
  }
}

async function openHistory() {
  historyOpen.value = true
  historyLoading.value = true
  await loadConversations()
  historyLoading.value = false
}

async function openConversation(id: number) {
  try {
    const r = await getAssistantConversation(id)
    if (!r.found) {
      await loadConversations()
      return
    }
    messages.value = (r.items || [])
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }))
    convId.value = id
    historyOpen.value = false
    locked.value = false
    void scrollBottom()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAssistant'))) {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  }
}

function newChat() {
  messages.value = []
  convId.value = null
  historyOpen.value = false
  locked.value = false
  renamingId.value = null
}

function startRename(id: number) {
  const hit = conversations.value.find((c) => c.id === id)
  renamingId.value = id
  renameText.value = hit?.title || ''
}

async function renameCurrent() {
  const id = convId.value
  if (!id) return
  historyOpen.value = true
  historyLoading.value = true
  await loadConversations()
  historyLoading.value = false
  startRename(id)
}

async function submitRename(id: number) {
  const title = renameText.value.trim()
  if (!title) {
    showToast(t('ai.renameRequired'))
    return
  }
  renaming.value = true
  try {
    const r = await renameAssistantConversation(id, title)
    if (!r.ok) {
      showToast(r.error || t('ai.renameFailed'))
      return
    }
    renamingId.value = null
    await loadConversations()
    showToast(t('ai.renamed'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.renameFailed'))
  } finally {
    renaming.value = false
  }
}

async function removeConversation(id: number) {
  try {
    await showConfirmDialog({
      title: t('ai.delete'),
      message: t('ai.deleteConfirm'),
      confirmButtonText: t('ai.ok'),
    })
  } catch {
    return
  }
  try {
    await deleteAssistantConversation(id)
    if (convId.value === id) newChat()
    await loadConversations()
    showToast(t('ai.deleted'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
  }
}

async function send(text?: string) {
  const msg = (text ?? input.value).trim()
  if (!msg || sending.value || locked.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg })
  sending.value = true
  void scrollBottom()
  try {
    const res = await aiChat({ message: msg, conversation_id: convId.value })
    convId.value = res.conversation_id
    messages.value.push({
      role: 'assistant',
      content: res.reply || res.hint || t('ai.unavailable'),
    })
    void loadConversations()
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

async function copyText(text: string) {
  const done = () => showToast(t('ai.copied'))
  const legacy = () => {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    done()
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      done()
    } else {
      legacy()
    }
  } catch {
    try {
      legacy()
    } catch {
      showToast(t('ai.copyFailed'))
    }
  }
}

function exportChat() {
  try {
    const lines = [
      `# ${currentTitle.value}`,
      '',
      ...messages.value.map((m) => `**${m.role === 'user' ? t('ai.roleUser') : t('ai.roleAssistant')}**\n\n${m.content}`),
    ]
    const url = URL.createObjectURL(new Blob([lines.join('\n\n')], { type: 'text/markdown;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-chat-${convId.value || 'new'}.md`
    a.click()
    URL.revokeObjectURL(url)
    showToast(t('ai.exported'))
  } catch {
    showToast(t('ai.exportFailed'))
  }
}

onMounted(() => { void loadConversations() })
</script>

<template>
  <div class="flex min-h-[70vh] flex-col">
    <div class="mb-2 flex items-center gap-2 rounded-xl bg-white p-2 shadow-sm">
      <span class="min-w-0 flex-1 truncate text-xs text-zinc-600">{{ currentTitle }}</span>
      <van-button v-if="messages.length" size="mini" plain @click="exportChat">{{ t('ai.exportChat') }}</van-button>
      <van-button v-if="convId" size="mini" plain @click="renameCurrent">{{ t('ai.rename') }}</van-button>
      <van-button size="mini" plain @click="openHistory">{{ t('ai.history') }}</van-button>
      <van-button size="mini" plain type="primary" @click="newChat">{{ t('ai.newChat') }}</van-button>
    </div>

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
        >
          {{ m.content }}
          <div v-if="m.role === 'assistant'" class="mt-1 text-right">
            <van-button size="mini" plain @click.stop="copyText(m.content)">{{ t('ai.copy') }}</van-button>
          </div>
        </div>
      </div>
      <div v-if="sending" class="text-xs text-zinc-400">{{ t('ai.thinking') }}</div>
    </div>

    <div class="sticky bottom-0 mt-3 flex gap-2 bg-zinc-100 pt-2">
      <van-field v-model="input" :placeholder="t('ai.inputPlaceholder')" :disabled="sending || locked" @keyup.enter="send()" />
      <van-button type="primary" :loading="sending" :disabled="locked || !input.trim()" @click="send()">{{ t('ai.send') }}</van-button>
    </div>

    <van-popup v-model:show="historyOpen" position="bottom" round class="pb-safe" :style="{ height: '60%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.history') }}</div>
        <van-button size="mini" plain @click="loadConversations">{{ t('ai.refresh') }}</van-button>
      </div>
      <div class="h-[calc(100%-49px)] overflow-y-auto px-3 py-2">
        <div v-if="historyLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <van-empty v-else-if="!conversations.length" :description="t('ai.noHistory')" />
        <div v-else class="space-y-2">
          <div v-for="c in conversations" :key="c.id" class="rounded-xl bg-zinc-50 p-3" @click="openConversation(c.id)">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-zinc-800">{{ c.title || t('ai.convTitle', { n: c.id }) }}</div>
                <div class="mt-1 text-[11px] text-zinc-400">
                  {{ t('ai.msgCount', { n: c.message_count ?? 0 }) }}<span v-if="c.updated_at"> · {{ c.updated_at }}</span>
                </div>
              </div>
              <div class="flex shrink-0 gap-1">
                <van-button size="mini" plain @click.stop="startRename(c.id)">{{ t('ai.rename') }}</van-button>
                <van-button size="mini" plain type="danger" @click.stop="removeConversation(c.id)">{{ t('ai.delete') }}</van-button>
              </div>
            </div>
            <div v-if="renamingId === c.id" class="mt-2 flex items-center gap-2" @click.stop>
              <van-field v-model="renameText" :placeholder="t('ai.renamePlaceholder')" maxlength="120" />
              <van-button size="mini" type="primary" :loading="renaming" @click.stop="submitRename(c.id)">{{ t('ai.ok') }}</van-button>
              <van-button size="mini" plain @click.stop="renamingId = null">{{ t('ai.close') }}</van-button>
            </div>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>
