<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { getMySalarySlip, rejectMySalarySlip, signMySalarySlip, type H5SalarySlip } from '@/api/tasks'
import { uploadFile } from '@/api/files'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const slip = ref<H5SalarySlip | null>(null)

const signOpen = ref(false)
const signing = ref(false)
const rejectOpen = ref(false)
const rejecting = ref(false)
const rejectReason = ref('')
const canvasRef = ref<HTMLCanvasElement | null>(null)
const ctxRef = ref<CanvasRenderingContext2D | null>(null)
const drawing = ref(false)
const hasStroke = ref(false)
const lastPoint = ref<{ x: number; y: number } | null>(null)

const signatureUrl = computed(() => {
  if (!slip.value?.signature_attachment_id) return ''
  return `/api/files/${slip.value.signature_attachment_id}`
})

function formatMoney(v: number): string {
  return v.toFixed(2)
}

async function refresh() {
  loading.value = true
  try {
    const month = (route.query.month as string) || undefined
    slip.value = await getMySalarySlip(month ? { month } : undefined)
  } finally {
    loading.value = false
  }
}

function openSign() {
  if (slip.value?.is_signed) {
    showToast('本月工资条已签名')
    return
  }
  if (slip.value?.confirm_status === 'rejected') {
    showToast('工资条已拒签，请联系管理员处理后再签名')
    return
  }
  signOpen.value = true
  nextTick(() => initCanvas())
}

function openReject() {
  if (slip.value?.is_signed) {
    showToast('本月工资条已签名')
    return
  }
  if (slip.value?.confirm_status === 'rejected') {
    showToast('工资条已拒签')
    return
  }
  rejectReason.value = ''
  rejectOpen.value = true
}

function initCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(rect.width * dpr)
  canvas.height = Math.floor(rect.height * dpr)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  ctx.strokeStyle = '#111827'
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, rect.width, rect.height)
  ctxRef.value = ctx
  drawing.value = false
  hasStroke.value = false
  lastPoint.value = null
}

function clearSign() {
  initCanvas()
}

function getPoint(e: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  const rect = canvas.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onPointerDown(e: PointerEvent) {
  const canvas = canvasRef.value
  const ctx = ctxRef.value
  if (!canvas || !ctx) return
  canvas.setPointerCapture(e.pointerId)
  drawing.value = true
  hasStroke.value = true
  const p = getPoint(e)
  lastPoint.value = p
  ctx.beginPath()
  ctx.moveTo(p.x, p.y)
}

function onPointerMove(e: PointerEvent) {
  const ctx = ctxRef.value
  if (!drawing.value || !ctx) return
  const p = getPoint(e)
  const last = lastPoint.value
  if (!last) return
  ctx.lineTo(p.x, p.y)
  ctx.stroke()
  lastPoint.value = p
}

function onPointerUp(e: PointerEvent) {
  const canvas = canvasRef.value
  const ctx = ctxRef.value
  if (!canvas || !ctx) return
  drawing.value = false
  lastPoint.value = null
  canvas.releasePointerCapture(e.pointerId)
}

async function canvasToPngFile(): Promise<File> {
  const canvas = canvasRef.value
  if (!canvas) throw new Error('canvas not ready')
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('toBlob failed'))), 'image/png')
  })
  return new File([blob], `salary_slip_${slip.value?.month || 'sign'}.png`, { type: 'image/png' })
}

async function submitSign() {
  if (signing.value) return
  if (!hasStroke.value) {
    showToast('请先签名')
    return
  }
  signing.value = true
  showLoadingToast({ message: '提交中...', duration: 0 })
  try {
    const file = await canvasToPngFile()
    const up = (await uploadFile(file)) as any
    const attachmentId = up?.id ?? up?.file_id
    if (!attachmentId) throw new Error('upload failed')
    await signMySalarySlip({ attachment_id: Number(attachmentId), month: slip.value?.month })
    showToast('签名成功')
    signOpen.value = false
    await refresh()
  } catch {
    showToast('签名失败')
  } finally {
    closeToast()
    signing.value = false
  }
}

async function submitReject() {
  if (rejecting.value) return
  const reason = rejectReason.value.trim()
  if (!reason) {
    showToast('请填写拒签原因')
    return
  }
  rejecting.value = true
  showLoadingToast({ message: '提交中...', duration: 0 })
  try {
    await rejectMySalarySlip({ reason, month: slip.value?.month })
    showToast('已提交拒签')
    rejectOpen.value = false
    await refresh()
  } catch {
    showToast('提交失败')
  } finally {
    closeToast()
    rejecting.value = false
  }
}

function goDetails() {
  router.push({ path: '/wages', query: { month: slip.value?.month } })
}

onMounted(refresh)
watch(
  () => route.query.month,
  () => refresh(),
)
</script>

<template>
  <div>
    <van-skeleton v-if="loading && !slip" title :row="6" />

    <div v-else-if="slip">
      <van-cell-group inset>
        <van-cell title="月份" :value="slip.month" />
        <van-cell title="合计金额" :value="`¥${formatMoney(slip.net_amount)}`" />
        <van-cell title="计件金额" :value="`¥${formatMoney(slip.item_amount)}`" />
        <van-cell title="补贴" :value="`¥${formatMoney(slip.bonus_amount)}`" />
        <van-cell title="扣款" :value="`¥${formatMoney(slip.deduction_amount)}`" />
        <van-cell title="明细列表" is-link @click="goDetails" />
        <van-cell
          title="确认状态"
          :value="slip.confirm_status === 'rejected' ? '已拒签' : slip.is_signed ? '已签名' : '待确认'"
        />
        <van-cell v-if="slip.confirm_status === 'rejected' && slip.reject_reason" title="拒签原因" :value="slip.reject_reason" />
      </van-cell-group>

      <div v-if="slip.is_signed && signatureUrl" class="mt-4 px-4">
        <div class="mb-2 text-sm font-medium text-zinc-600">签名</div>
        <van-image :src="signatureUrl" width="100%" height="120" fit="contain" radius="8" />
        <div v-if="slip.signed_at" class="mt-2 text-xs text-zinc-400">签名时间：{{ slip.signed_at }}</div>
      </div>

      <div v-else class="mt-4 px-4">
        <van-button v-if="slip.confirm_status !== 'rejected'" block type="primary" @click="openSign">手写签名确认</van-button>
        <van-button v-if="slip.confirm_status !== 'rejected'" class="mt-2" block type="danger" plain @click="openReject">拒签</van-button>
        <van-cell v-if="slip.confirm_status === 'rejected'" class="mt-2" title="提示" value="已拒签，请联系管理员处理后再签名" />
      </div>
    </div>

    <van-popup v-model:show="signOpen" position="bottom" round class="pb-safe">
      <div class="p-4">
        <div class="text-base font-medium text-zinc-900">手写签名</div>
        <div class="mt-1 text-xs text-zinc-400">请在下方区域签名确认工资条</div>
        <div class="mt-3">
          <canvas
            ref="canvasRef"
            class="h-52 w-full rounded-lg border border-zinc-200 bg-white touch-none"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
          />
        </div>
        <div class="mt-4 grid grid-cols-3 gap-2">
          <van-button plain @click="clearSign">清空</van-button>
          <van-button plain @click="signOpen = false">取消</van-button>
          <van-button type="primary" :loading="signing" @click="submitSign">提交</van-button>
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="rejectOpen" position="bottom" round class="pb-safe">
      <div class="p-4">
        <div class="text-base font-medium text-zinc-900">拒签工资条</div>
        <div class="mt-1 text-xs text-zinc-400">请填写拒签原因，提交后等待管理员处理</div>
        <div class="mt-3">
          <van-field v-model="rejectReason" type="textarea" rows="3" autosize placeholder="请输入拒签原因" />
        </div>
        <div class="mt-4 grid grid-cols-2 gap-2">
          <van-button plain @click="rejectOpen = false">取消</van-button>
          <van-button type="danger" :loading="rejecting" @click="submitReject">提交</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>
