<template>
  <view v-if="visible" class="mask" @tap="emit('close')">
    <view class="sheet" @tap.stop>
      <view class="head">
        <text class="title">{{ mode === 'create' ? '新增' : '编辑' }}</text>
        <text class="close" @tap="emit('close')">×</text>
      </view>
      <scroll-view scroll-y class="body">
        <view v-for="field in fields" :key="field.key + mode" class="field">
          <text class="label">{{ field.label }}<text v-if="field.required" class="req">*</text></text>

          <switch
            v-if="field.type === 'switch'"
            :checked="Boolean(model[field.key])"
            @change="onSwitch(field.key, $event)"
          />

          <picker
            v-else-if="field.type === 'select'"
            :range="pickerLabels(field)"
            @change="onPicker(field, $event)"
          >
            <view class="input picker">{{ pickerDisplay(field) }}</view>
          </picker>

          <textarea
            v-else-if="field.type === 'textarea'"
            class="input area"
            :value="String(model[field.key] ?? '')"
            :placeholder="field.placeholder || `请输入${field.label}`"
            @input="onInput(field.key, $event)"
          />

          <input
            v-else
            class="input"
            :password="field.type === 'password'"
            :type="field.type === 'number' ? 'digit' : 'text'"
            :value="String(model[field.key] ?? '')"
            :placeholder="field.placeholder || `请输入${field.label}`"
            @input="onInput(field.key, $event)"
          />
        </view>
      </scroll-view>
      <view class="foot">
        <button class="btn ghost" @tap="emit('close')">取消</button>
        <button class="btn primary" :loading="saving" @tap="emit('submit')">保存</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { CrudField } from '@/types/adminCrud'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  fields: CrudField[]
  model: Record<string, unknown>
  optionMap: Record<string, { label: string; value: string | number }[]>
  saving?: boolean
}>()

const emit = defineEmits<{
  close: []
  submit: []
  'update:model': [Record<string, unknown>]
}>()

function onInput(key: string, e: { detail: { value: string } }) {
  emit('update:model', { ...props.model, [key]: e.detail.value })
}

function onSwitch(key: string, e: { detail: { value: boolean } }) {
  emit('update:model', { ...props.model, [key]: e.detail.value })
}

function pickerLabels(field: CrudField) {
  if (field.options?.length) return field.options.map((o) => o.label)
  return (props.optionMap[field.key] || []).map((o) => o.label)
}

function pickerValues(field: CrudField) {
  if (field.options?.length) return field.options.map((o) => o.value)
  return (props.optionMap[field.key] || []).map((o) => o.value)
}

function pickerDisplay(field: CrudField) {
  const val = props.model[field.key]
  const values = pickerValues(field)
  const labels = pickerLabels(field)
  const idx = values.findIndex((v) => v === val)
  if (idx >= 0) return labels[idx]
  return val != null && val !== '' ? String(val) : `请选择${field.label}`
}

function onPicker(field: CrudField, e: { detail: { value: number } }) {
  const values = pickerValues(field)
  const v = values[e.detail.value]
  emit('update:model', { ...props.model, [field.key]: v })
}
</script>

<style scoped lang="scss">
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 10000;
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  max-height: 82vh;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  display: flex;
  flex-direction: column;
}
.head {
  display: flex;
  justify-content: space-between;
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid #f1f5f9;
}
.title { font-size: 32rpx; font-weight: 700; }
.close { font-size: 44rpx; color: #94a3b8; line-height: 1; }
.body { flex: 1; max-height: 60vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 24rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 10rpx; }
.req { color: #ef4444; }
.input {
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 22rpx;
  font-size: 28rpx;
}
.area { min-height: 160rpx; width: 100%; box-sizing: border-box; }
.picker { color: #334155; }
.foot {
  display: flex;
  gap: 16rpx;
  padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid #f1f5f9;
}
.btn {
  flex: 1;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
</style>
