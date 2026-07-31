<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { http } from '@/utils/http'

const { t } = useI18n()

export type AttachmentMeta = {
  id: number
  content_type?: string | null
  original_filename?: string | null
  size?: number
  play_url?: string | null
  url?: string | null
}

const props = defineProps<{
  attachment: AttachmentMeta
  width?: number
  height?: number
}>()

const mediaUrl = ref('')
const loadError = ref(false)

const kind = computed(() => {
  const ct = (props.attachment.content_type || '').toLowerCase()
  const name = (props.attachment.original_filename || '').toLowerCase()
  if (ct.startsWith('video/') || /\.(mp4|mov|webm|3gp|m4v)$/.test(name)) return 'video'
  if (ct.startsWith('image/') || /\.(jpg|jpeg|png|webp|gif)$/.test(name)) return 'image'
  return 'file'
})

const boxStyle = computed(() => ({
  width: `${props.width ?? 160}px`,
  maxWidth: '100%',
}))

function resolvePlayUrl(raw: string) {
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  if (raw.startsWith('/')) return `${origin}${raw}`
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const prefix = base.startsWith('http') ? base.replace(/\/$/, '') : `${origin}${base}`.replace(/\/$/, '')
  return `${prefix}/${raw}`
}

async function load() {
  loadError.value = false
  const direct = props.attachment.play_url || props.attachment.url
  if (direct) {
    mediaUrl.value = resolvePlayUrl(direct)
    return
  }
  try {
    const res = await http.request<{ play_url?: string; url?: string }>({
      url: `/files/${props.attachment.id}`,
      method: 'GET',
      params: { url: 1 },
    })
    const url = res.play_url || res.url
    if (!url) throw new Error('no url')
    mediaUrl.value = resolvePlayUrl(url)
  } catch {
    loadError.value = true
  }
}

watch(() => props.attachment.id, load)
onMounted(load)
onUnmounted(() => {})
</script>

<template>
  <div class="attachment-preview inline-block align-top" :style="boxStyle">
    <video
      v-if="kind === 'video' && mediaUrl"
      :src="mediaUrl"
      controls
      playsinline
      class="rounded border border-zinc-200 w-full max-h-48 bg-black"
    />
    <el-image
      v-else-if="kind === 'image' && mediaUrl"
      :src="mediaUrl"
      :style="{ width: `${width ?? 160}px`, height: `${height ?? 120}px` }"
      fit="cover"
      class="rounded"
      :preview-src-list="[mediaUrl]"
    />
    <div
      v-else-if="loadError"
      class="text-xs text-red-500 p-2 border border-red-100 rounded bg-red-50"
    >
      {{ t('common.attachments') }}#{{ attachment.id }} {{ t('common.loadFailed') }}
    </div>
    <div v-else class="text-xs text-zinc-400 p-2 border rounded">{{ t('common.loading') }} #{{ attachment.id }}…</div>
    <div class="text-[10px] text-zinc-400 mt-1 truncate" :title="attachment.original_filename || ''">
      #{{ attachment.id }}
      <span v-if="attachment.original_filename">{{ attachment.original_filename }}</span>
      <span v-if="attachment.size"> · {{ (attachment.size / 1024).toFixed(0) }}KB</span>
    </div>
  </div>
</template>
