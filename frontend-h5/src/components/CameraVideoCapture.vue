<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { uploadReportMedia } from '@/api/files'
import {
  canUseInPageRecorder,
  getUserMediaFn,
  isSecureCameraContext,
  pickRecorderMime,
  pickVideoFromSystemCamera,
  validateCapturedVideo,
} from '@/utils/camera'

export type MediaItem = { id: number; name: string }

const props = withDefaults(
  defineProps<{
    maxSeconds?: number
    maxMb?: number
    maxCount?: number
    disabled?: boolean
  }>(),
  { maxSeconds: 15, maxMb: 8, maxCount: 3, disabled: false },
)

const items = defineModel<MediaItem[]>({ default: () => [] })

const show = ref(false)
const recording = ref(false)
const previewRef = ref<HTMLVideoElement | null>(null)
const elapsed = ref(0)

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let chunks: Blob[] = []
let stopTimer: ReturnType<typeof setTimeout> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null

const canAdd = computed(() => items.value.length < props.maxCount)
const hint = computed(() => {
  const base = `现场摄像，每段≤${props.maxSeconds}秒、≤${props.maxMb}MB，最多${props.maxCount}段`
  if (!isSecureCameraContext()) return `${base}（HTTP 将调起系统相机）`
  return base
})

function cleanupStream() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  if (previewRef.value) previewRef.value.srcObject = null
}

function closePanel() {
  if (recording.value) stopRecord()
  cleanupStream()
  show.value = false
}

async function uploadVideoFile(file: File) {
  const err = await validateCapturedVideo(file, props.maxSeconds, props.maxMb)
  if (err) {
    showToast(err)
    return
  }
  const toast = showLoadingToast({ message: '上传中...', duration: 0 })
  try {
    const res = await uploadReportMedia(file)
    const id = res?.id ?? res?.file_id
    if (!id) throw new Error('上传失败')
    const ext = file.name.split('.').pop() || 'mp4'
    items.value = [...items.value, { id: Number(id), name: `视频${items.value.length + 1}.${ext}` }]
    showToast('视频已上传')
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '上传失败')
  } finally {
    closeToast()
  }
}

async function recordViaSystemCamera() {
  const file = await pickVideoFromSystemCamera()
  if (!file) return
  await uploadVideoFile(file)
}

async function openInPageRecorder() {
  const gum = getUserMediaFn()
  if (!gum) throw new Error('no-gum')
  stream = await gum({
    video: { facingMode: { ideal: 'environment' } },
    audio: true,
  })
  show.value = true
  await nextTick()
  if (previewRef.value) {
    previewRef.value.srcObject = stream
    await previewRef.value.play().catch(() => undefined)
  }
}

async function openRecorder() {
  if (props.disabled) return
  if (!canAdd.value) {
    showToast(`最多拍摄 ${props.maxCount} 段视频`)
    return
  }
  if (canUseInPageRecorder()) {
    try {
      await openInPageRecorder()
      return
    } catch (e: unknown) {
      const name = e instanceof DOMException ? e.name : ''
      if (name === 'NotAllowedError') showToast('请允许摄像头/麦克风权限')
    }
  }
  if (!isSecureCameraContext()) {
    showToast('将打开系统相机录像（建议站点使用 HTTPS）')
  }
  await recordViaSystemCamera()
}

function startRecord() {
  const mime = pickRecorderMime()
  if (!mime || !stream) {
    showToast('改用系统相机拍摄')
    void recordViaSystemCamera()
    return
  }
  chunks = []
  recorder = new MediaRecorder(stream, { mimeType: mime })
  recorder.ondataavailable = (e) => {
    if (e.data?.size) chunks.push(e.data)
  }
  recorder.onstop = () => void onRecorded(mime)
  recorder.start(250)
  recording.value = true
  elapsed.value = 0
  tickTimer = setInterval(() => {
    elapsed.value += 1
  }, 1000)
  stopTimer = setTimeout(() => stopRecord(), props.maxSeconds * 1000)
}

function stopRecord() {
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = null
  if (tickTimer) clearInterval(tickTimer)
  tickTimer = null
  if (recorder && recording.value) {
    try {
      recorder.stop()
    } catch {
      /* ignore */
    }
    recording.value = false
  }
}

async function onRecorded(mime: string) {
  closePanel()
  const blob = new Blob(chunks, { type: mime.split(';')[0] || 'video/webm' })
  const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
  const file = new File([blob], `report_${Date.now()}.${ext}`, { type: blob.type || 'video/webm' })
  await uploadVideoFile(file)
}

function removeAt(i: number) {
  items.value = items.value.filter((_, idx) => idx !== i)
}

onUnmounted(() => {
  if (recording.value) stopRecord()
  cleanupStream()
})
</script>

<template>
  <div class="space-y-2">
    <div class="text-xs text-zinc-500">{{ hint }}</div>
    <van-button
      size="small"
      type="primary"
      icon="video-o"
      :disabled="disabled || !canAdd"
      @click="openRecorder"
    >
      拍摄视频（{{ items.length }}/{{ maxCount }}）
    </van-button>
    <div v-if="items.length" class="flex flex-wrap gap-2">
      <van-tag v-for="(u, i) in items" :key="u.id" closeable @close="removeAt(i)">{{ u.name }}</van-tag>
    </div>

    <van-popup v-model:show="show" position="bottom" round :style="{ height: '70%' }" @closed="cleanupStream">
      <div class="p-4 flex flex-col h-full">
        <div class="text-center font-medium">页内录制</div>
        <div class="text-center text-sm text-zinc-500 mt-1">最长 {{ maxSeconds }} 秒 · 已录 {{ elapsed }} 秒</div>
        <video
          ref="previewRef"
          class="mt-3 w-full flex-1 bg-black rounded-lg object-cover max-h-[50vh]"
          playsinline
          muted
        />
        <div class="mt-4 flex gap-3 justify-center">
          <van-button v-if="!recording" type="danger" round @click="startRecord">开始录制</van-button>
          <van-button v-else type="warning" round @click="stopRecord">结束并上传</van-button>
          <van-button round @click="closePanel">取消</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>
