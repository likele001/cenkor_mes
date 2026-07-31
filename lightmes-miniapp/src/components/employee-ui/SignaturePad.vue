<template>
  <view class="pad-wrap">
    <canvas
      canvas-id="signCanvas"
      class="canvas"
      @touchstart="touchStart"
      @touchmove="touchMove"
      @touchend="touchEnd"
    />
    <view class="actions">
      <button size="mini" @tap="clear">清除</button>
      <button size="mini" type="primary" @tap="exportSign">确认签名</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { getCurrentInstance, onMounted, ref } from 'vue'

const emit = defineEmits<{ done: [string] }>()
const instance = getCurrentInstance()
let ctx: UniApp.CanvasContext | null = null
const drawing = ref(false)

onMounted(() => {
  ctx = uni.createCanvasContext('signCanvas', instance?.proxy)
  if (ctx) {
    ctx.setStrokeStyle('#000')
    ctx.setLineWidth(3)
    ctx.setLineCap('round')
  }
})

function touchStart(e: TouchEvent) {
  drawing.value = true
  const t = e.touches[0]
  ctx?.moveTo(t.x, t.y)
}
function touchMove(e: TouchEvent) {
  if (!drawing.value || !ctx) return
  const t = e.touches[0]
  ctx.lineTo(t.x, t.y)
  ctx.stroke()
  ctx.draw(true)
  ctx.moveTo(t.x, t.y)
}
function touchEnd() {
  drawing.value = false
}
function clear() {
  if (!ctx) return
  ctx.clearRect(0, 0, 600, 300)
  ctx.draw()
}
function exportSign() {
  uni.canvasToTempFilePath({
    canvasId: 'signCanvas',
    success: (res) => emit('done', res.tempFilePath),
    fail: () => uni.showToast({ title: '签名导出失败', icon: 'none' }),
  }, instance?.proxy)
}
</script>

<style scoped lang="scss">
.pad-wrap {
  background: #fff;
  border-radius: 16rpx;
  padding: 16rpx;
}
.canvas {
  width: 100%;
  height: 300rpx;
  background: #fafafa;
  border: 1rpx dashed #cbd5e1;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 16rpx;
  margin-top: 16rpx;
}
</style>
