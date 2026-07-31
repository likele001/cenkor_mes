<template>
  <div class="flex flex-col h-screen bg-gray-50">
    <!-- Header -->
    <van-nav-bar left-arrow @click-left="$router.back()">
      <template #title>
        <div class="flex items-center gap-2">
          <van-image v-if="employee?.avatar_url" :src="employee.avatar_url" round width="28" height="28" />
          <div v-else class="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs">
            {{ employee?.name?.charAt(0) || '?' }}
          </div>
          <span class="text-sm font-medium">{{ employee?.name || t('aiEmployee.chat') }}</span>
        </div>
      </template>
      <template #right>
        <van-popover :actions="menuActions" @select="onMenuSelect" placement="bottom-end">
          <template #reference>
            <van-icon name="more-o" size="18" />
          </template>
        </van-popover>
      </template>
    </van-nav-bar>

    <!-- Messages -->
    <div ref="scrollRef" class="flex-1 overflow-y-auto px-3 py-4 space-y-3">
      <!-- Welcome message -->
      <div v-if="employee?.welcome_message && messages.length === 0" class="flex justify-start">
        <div class="max-w-[80%] bg-white rounded-xl rounded-tl-sm px-4 py-3 text-sm text-gray-700 shadow-sm">
          {{ employee.welcome_message }}
        </div>
      </div>
      <!-- Message bubbles -->
      <div v-for="(msg, i) in messages" :key="i" :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
        <div
          :class="msg.role === 'user'
            ? 'max-w-[80%] bg-blue-500 text-white rounded-xl rounded-tr-sm px-4 py-2.5 text-sm'
            : 'max-w-[80%] bg-white text-gray-800 rounded-xl rounded-tl-sm px-4 py-2.5 text-sm shadow-sm'"
        >
          <div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
          <!-- Tool call indicator -->
          <div v-if="msg.tool_indicator" class="mt-1.5 text-xs opacity-70 flex items-center gap-1">
            <van-icon name="search" size="12" />
            {{ msg.tool_indicator }}
          </div>
        </div>
      </div>
      <!-- Typing indicator -->
      <div v-if="sending" class="flex justify-start">
        <div class="bg-white rounded-xl rounded-tl-sm px-4 py-3 text-sm text-gray-500 shadow-sm">
          <span class="typing-dots">
            <span>.</span><span>.</span><span>.</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="border-t bg-white px-3 py-2 flex items-end gap-2">
      <van-field
        v-model="inputText"
        type="textarea"
        :placeholder="t('aiEmployee.inputPlaceholder')"
        rows="1"
        autosize
        class="flex-1 !py-1"
        @keyup.enter.exact="sendMessage"
      />
      <van-button
        type="primary"
        size="small"
        :disabled="sending || !inputText.trim()"
        @click="sendMessage"
        round
      >
        {{ t('common.send') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import {
  listAiEmployees,
  aiEmployeeChat,
  listAiEmployeeConversations,
  deleteAiEmployeeConversation,
  type AiEmployeeItem,
} from '@/api/aiEmployee'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const employeeId = Number(route.params.id)

const employee = ref<AiEmployeeItem | null>(null)
const messages = ref<Array<{ role: string; content: string; tool_indicator?: string }>>([])
const inputText = ref('')
const sending = ref(false)
const conversationId = ref<number | undefined>(undefined)
const scrollRef = ref<HTMLElement | null>(null)

const menuActions = computed(() => {
  const items = [{ text: t('aiEmployee.newChat'), icon: 'replay' }]
  if (conversationId.value) {
    items.push({ text: t('aiEmployee.deleteChat'), icon: 'delete-o' })
  }
  return items
})

onMounted(async () => {
  try {
    const res = await listAiEmployees()
    const list: AiEmployeeItem[] = (res as any)?.items || res || []
    employee.value = list.find((e) => e.id === employeeId) || null
  } catch { /* ignore */ }
  scrollToBottom()
})

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  sending.value = true
  scrollToBottom()

  try {
    const res = await aiEmployeeChat(employeeId, {
      message: text,
      conversation_id: conversationId.value,
    })
    const data = res as any
    if (data?.conversation_id) conversationId.value = data.conversation_id
    if (data?.tool_calls_used?.length) {
      messages.value.push({
        role: 'assistant',
        content: data.reply || '',
        tool_indicator: `Used: ${data.tool_calls_used.join(', ')}`,
      })
    } else {
      messages.value.push({ role: 'assistant', content: data?.reply || '' })
    }
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: e?.message || t('aiEmployee.error') })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

async function onMenuSelect(action: { text: string }) {
  if (action.text === t('aiEmployee.newChat')) {
    conversationId.value = undefined
    messages.value = []
  } else if (action.text === t('aiEmployee.deleteChat') && conversationId.value) {
    try {
      await deleteAiEmployeeConversation(conversationId.value)
    } catch { /* ignore */ }
    conversationId.value = undefined
    messages.value = []
    showToast(t('aiEmployee.deleted'))
  }
}
</script>

<style scoped>
.typing-dots span {
  animation: blink 1.4s infinite both;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}
</style>
