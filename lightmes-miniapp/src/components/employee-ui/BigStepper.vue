<template>
  <view class="stepper">
    <view class="btn" @tap="dec">-</view>
    <input class="val" type="number" :value="String(modelValue)" @input="onInput" />
    <view class="btn" @tap="inc">+</view>
    <view v-if="step10" class="btn sm" @tap="add10">+10</view>
  </view>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{ modelValue: number; min?: number; max?: number; step10?: boolean }>(),
  { min: 0, step10: true },
)
const emit = defineEmits<{ 'update:modelValue': [number] }>()

function clamp(v: number) {
  let n = Math.max(props.min ?? 0, v)
  if (props.max != null) n = Math.min(props.max, n)
  return n
}
function inc() {
  emit('update:modelValue', clamp(props.modelValue + 1))
}
function dec() {
  emit('update:modelValue', clamp(props.modelValue - 1))
}
function add10() {
  emit('update:modelValue', clamp(props.modelValue + 10))
}
function onInput(e: { detail: { value: string } }) {
  emit('update:modelValue', clamp(parseInt(e.detail.value, 10) || 0))
}
</script>

<style scoped lang="scss">
.stepper {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.btn {
  width: 80rpx;
  height: 80rpx;
  background: #e2e8f0;
  border-radius: 12rpx;
  text-align: center;
  line-height: 80rpx;
  font-size: 40rpx;
}
.btn.sm {
  width: auto;
  padding: 0 20rpx;
  font-size: 28rpx;
}
.val {
  flex: 1;
  height: 80rpx;
  text-align: center;
  font-size: 40rpx;
  font-weight: 700;
  background: #f8fafc;
  border-radius: 12rpx;
}
</style>
