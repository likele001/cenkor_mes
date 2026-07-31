<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/http'
import {
  canUseInPageRecorder,
  getUserMediaFn,
  isSecureCameraContext,
  pickRecorderMime,
  pickVideoFromSystemCamera,
  validateCapturedVideo,
} from '@/utils/camera'

const { t } = useI18n()

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
const modeHint = computed(() => {
  if (canUseInPageRecorder()) return t('common.inPageRecording')
  if (!isSecureCameraContext()) return t('common.httpSystemCamera')
  return t('common.willUseSystemCamera')
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
    ElMessage.error(err)
    return
  }
  const form = new FormData()
  form.append('file', file)
  const res = await http.request<{ id?: number; file_id?: number }>({
    url: '/files/upload?purpose=report_media',
    method: 'POST',
    data: form,
  })
  const id = res?.id ?? res?.file_id
  if (!id) throw new Error(t('common.uploadFailed'))
  const ext = file.name.split('.').pop() || 'mp4'
  items.value = [...items.value, { id: Number(id), name: `${t('common.captureVideo')}${items.value.length + 1}.${ext}` }]
  ElMessage.success(t('common.videoUploaded'))
}

async function recordViaSystemCamera() {
  const file = await pickVideoFromSystemCamera()
  if (!file) return
  try {
    await uploadVideoFile(file)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('common.uploadFailed'))
  }
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
    ElMessage.warning(`${t('common.maxVideos')} ${props.maxCount} ${t('common.videos')}`)
    return
  }
  if (canUseInPageRecorder()) {
    try {
      await openInPageRecorder()
      return
    } catch (e: unknown) {
      const name = e instanceof DOMException ? e.name : ''
      if (name === 'NotAllowedError') {
        ElMessage.warning(t('common.siteOnCameraMic'))
      }
      /* 降级系统相机 */
    }
  }
  if (!isSecureCameraContext()) {
    ElMessage.info(t('common.httpUseSystemCamera'))
  }
  await recordViaSystemCamera()
}

function startRecord() {
  const mime = pickRecorderMime()
  if (!mime || !stream) {
    ElMessage.error(t('common.cannotInPageRecording'))
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
  const file = new File([blob], `audit_${Date.now()}.${ext}`, { type: blob.type || 'video/webm' })
  try {
    await uploadVideoFile(file)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('common.uploadFailed'))
  }
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
    <div class="text-xs text-zinc-500">
      {{ t('common.onSiteVideo') }}：每段≤{{ maxSeconds }}{{ t('common.seconds') }}、≤{{ maxMb }}MB，最多{{ maxCount }}段。{{ modeHint }}
    </div>
    <el-button type="primary" size="small" :disabled="disabled || !canAdd" @click="openRecorder">
      {{ t('common.cameraVideo') }}（{{ items.length }}/{{ maxCount }}）
    </el-button>
    <div class="flex flex-wrap gap-2">
      <el-tag v-for="(u, i) in items" :key="u.id" closable @close="removeAt(i)">{{ u.name }}</el-tag>
    </div>

    <el-dialog v-model="show" :title="t('common.pageRecording')" width="92%" top="8vh" destroy-on-close @closed="cleanupStream">
      <p class="text-sm text-zinc-500 text-center mb-2">{{ t('common.longestSeconds') }} {{ maxSeconds }} {{ t('common.seconds') }} · {{ t('common.recordedSeconds') }} {{ elapsed }} {{ t('common.seconds') }}</p>
      <video ref="previewRef" class="w-full rounded bg-black max-h-[50vh]" playsinline muted />
      <template #footer>
        <el-button v-if="!recording" type="danger" @click="startRecord">{{ t('common.startRecording') }}</el-button>
        <el-button v-else type="warning" @click="stopRecord">{{ t('common.stopAndUpload') }}</el-button>
        <el-button @click="closePanel">{{ t('common.cancel') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
