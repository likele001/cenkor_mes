<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { aiChat, deleteAiConversation, listAiConversations, listAiModels } from '@/api/ai'

const question = ref('')
const loading = ref(false)
const convId = ref<number | undefined>()
const messages = ref<Array<{ role: string; content: string }>>([])
const models = ref<Array<{ code: string; display_name: string; is_default: boolean }>>([])
const modelCode = ref('')
const history = ref<Array<{ id: number; title: string | null; updated_at: string }>>([])
const showHistory = ref(false)

async function loadModels() {
  try {
    const res = await listAiModels()
    models.value = res.items || []
    const def = models.value.find((m) => m.is_default)
    if (def) modelCode.value = def.code
    else if (models.value.length) modelCode.value = models.value[0].code
  } catch {
    models.value = []
  }
}

async function loadHistory() {
  try {
    const res = await listAiConversations('boss_qa')
    history.value = res.items || []
  } catch {
    history.value = []
  }
}

async function send() {
  const msg = question.value.trim()
  if (!msg) return
  messages.value.push({ role: 'user', content: msg })
  question.value = ''
  loading.value = true
  try {
    const res = await aiChat({
      message: msg,
      conversation_id: convId.value,
      model_code: modelCode.value || undefined,
    })
    convId.value = res.conversation_id
    messages.value.push({ role: 'assistant', content: res.reply })
    await loadHistory()
  } catch (e: unknown) {
    messages.value.pop()
    showToast(e instanceof Error ? e.message : 'AI 暂不可用')
  } finally {
    loading.value = false
  }
}

function newChat() {
  convId.value = undefined
  messages.value = []
}

async function removeConv(id: number) {
  try {
    await deleteAiConversation(id)
    if (convId.value === id) newChat()
    await loadHistory()
    showToast('已删除')
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(() => {
  loadModels()
  loadHistory()
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-46px)] bg-zinc-50">
    <div class="bg-white px-4 py-2 border-b border-zinc-100 flex items-center gap-2">
      <van-dropdown-menu v-if="models.length" class="flex-1">
        <van-dropdown-item v-model="modelCode" :options="models.map((m) => ({ text: m.display_name, value: m.code }))" />
      </van-dropdown-menu>
      <van-button size="small" plain @click="showHistory = !showHistory">历史</van-button>
      <van-button size="small" plain @click="newChat">新对话</van-button>
    </div>

    <div v-if="showHistory && history.length" class="bg-white border-b border-zinc-100 max-h-40 overflow-y-auto px-4 py-2">
      <div
        v-for="h in history"
        :key="h.id"
        class="flex items-center justify-between py-2 border-b border-zinc-50 text-sm"
      >
        <span class="truncate flex-1" @click="convId = h.id; showHistory = false">{{ h.title || `对话 #${h.id}` }}</span>
        <van-button size="mini" type="danger" plain @click="removeConv(h.id)">删</van-button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-3">
      <div v-for="(m, i) in messages" :key="i" :class="m.role === 'user' ? 'text-right' : ''">
        <div
          class="inline-block max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap"
          :class="m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-white text-zinc-800 shadow-sm'"
        >
          {{ m.content }}
        </div>
      </div>
      <div v-if="!messages.length" class="text-center text-sm text-zinc-400 py-8">例如：今天待审报工多少？</div>
    </div>

    <div class="p-4 bg-white border-t border-zinc-100">
      <van-field v-model="question" type="textarea" rows="2" placeholder="输入问题…" />
      <van-button block type="primary" class="mt-2" :loading="loading" @click="send">发送</van-button>
    </div>
  </div>
</template>

<style scoped>
:deep(.van-dropdown-menu__bar) {
  box-shadow: none;
  height: 36px;
}
</style>
