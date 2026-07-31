<script setup lang="ts">
import { computed, ref } from 'vue'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { uploadReportMedia } from '@/api/files'

export type MediaItem = { id: number; name: string }

const props = withDefaults(
  defineProps<{
    maxCount?: number
    disabled?: boolean
    label?: string
  }>(),
  { maxCount: 5, disabled: false, label: '拍摄照片' },
)

const items = defineModel<MediaItem[]>({ default: () => [] })

const canAdd = computed(() => items.value.length < props.maxCount)

function shootPhoto() {
  if (props.disabled || !canAdd.value) {
    showToast(`最多拍摄 ${props.maxCount} 张`)
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.setAttribute('capture', 'environment')
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    const toast = showLoadingToast({ message: '上传中...', duration: 0 })
    try {
      const res = await uploadReportMedia(file)
      const id = res?.id ?? res?.file_id
      if (!id) throw new Error('上传失败')
      items.value = [...items.value, { id: Number(id), name: file.name || `照片${items.value.length + 1}` }]
      showToast('照片已上传')
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : '上传失败')
    } finally {
      closeToast()
    }
  }
  input.click()
}

function removeAt(i: number) {
  items.value = items.value.filter((_, idx) => idx !== i)
}
</script>

<template>
  <div class="space-y-2">
    <div class="text-xs text-zinc-500">请用手机摄像头现场拍摄，不支持从相册选大图</div>
    <van-button size="small" type="primary" icon="photograph" :disabled="disabled || !canAdd" @click="shootPhoto">
      {{ label }}（{{ items.length }}/{{ maxCount }}）
    </van-button>
    <div v-if="items.length" class="flex flex-wrap gap-2">
      <van-tag v-for="(u, i) in items" :key="u.id" closeable @close="removeAt(i)">{{ u.name }}</van-tag>
    </div>
  </div>
</template>
