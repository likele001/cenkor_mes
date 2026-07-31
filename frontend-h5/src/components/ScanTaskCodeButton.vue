<script setup lang="ts">
import { ref } from 'vue'
import { showToast } from 'vant'
import { parseTaskCodeFromScan } from '@/utils/parseTaskCode'

const emit = defineEmits<{ (e: 'scan', code: string): void }>()

const scanning = ref(false)
let stream: MediaStream | null = null
let timer: ReturnType<typeof setInterval> | null = null

async function stopScan() {
  scanning.value = false
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
}

async function startCameraScan() {
  if (!('BarcodeDetector' in window)) {
    pickImage()
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
  } catch {
    showToast('无法打开相机，请选图识别或去「我的任务」报工')
    pickImage()
    return
  }
  scanning.value = true
  const video = document.getElementById('scan-task-video') as HTMLVideoElement | null
  if (!video) return
  video.srcObject = stream
  await video.play()
  // @ts-expect-error BarcodeDetector 非标准 API
  const detector = new BarcodeDetector({ formats: ['qr_code'] })
  timer = setInterval(async () => {
    if (!scanning.value || !video.videoWidth) return
    try {
      const codes = await detector.detect(video)
      if (codes?.length) {
        const code = parseTaskCodeFromScan(codes[0].rawValue || '')
        if (code) {
          await stopScan()
          emit('scan', code)
        }
      }
    } catch {
      /* ignore frame errors */
    }
  }, 400)
}

function pickImage() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.capture = 'environment'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    if (!('BarcodeDetector' in window)) {
      showToast('当前浏览器不支持识码，请手动输入任务码')
      return
    }
    const img = document.createElement('img')
    const url = URL.createObjectURL(file)
    img.src = url
    await img.decode()
    try {
      // @ts-expect-error BarcodeDetector
      const detector = new BarcodeDetector({ formats: ['qr_code'] })
      const codes = await detector.detect(img)
      const code = parseTaskCodeFromScan(codes[0]?.rawValue || '')
      if (code) emit('scan', code)
      else showToast('未识别到二维码')
    } catch {
      showToast('识码失败')
    } finally {
      URL.revokeObjectURL(url)
    }
  }
  input.click()
}

defineExpose({ stopScan })
</script>

<template>
  <div>
    <van-button type="primary" block icon="scan" @click="startCameraScan">扫一扫任务码</van-button>
    <van-popup v-model:show="scanning" position="bottom" round :style="{ height: '70%' }" @closed="stopScan">
      <div class="p-4 text-center">
        <div class="text-sm text-zinc-600 mb-3">对准任务标签或任务详情中的二维码</div>
        <video id="scan-task-video" class="mx-auto w-full max-w-sm rounded-lg bg-black" playsinline muted />
        <van-button class="mt-4" block @click="stopScan">关闭</van-button>
      </div>
    </van-popup>
  </div>
</template>
