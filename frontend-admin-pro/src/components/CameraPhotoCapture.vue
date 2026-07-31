<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/http'

const { t } = useI18n()

export type MediaItem = { id: number; name: string }

const props = withDefaults(
  defineProps<{
    maxCount?: number
    disabled?: boolean
    label?: string
  }>(),
  { maxCount: 5, disabled: false, label: '' },
)

const items = defineModel<MediaItem[]>({ default: () => [] })
const canAdd = computed(() => items.value.length < props.maxCount)
const resolvedLabel = computed(() => props.label || t('common.capturePhoto'))

function shootPhoto() {
  if (props.disabled || !canAdd.value) {
    ElMessage.warning(`${t('common.maxPhotos')} ${props.maxCount} ${t('common.photos')}`)
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.setAttribute('capture', 'environment')
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await http.request<{ id?: number; file_id?: number }>({
        url: '/files/upload?purpose=report_media',
        method: 'POST',
        data: form,
      })
      const id = res?.id ?? res?.file_id
      if (!id) throw new Error(t('common.uploadFailed'))
      items.value = [...items.value, { id: Number(id), name: file.name || `${t('common.capturePhoto')}${items.value.length + 1}` }]
      ElMessage.success(t('common.photoUploaded'))
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : t('common.uploadFailed'))
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
    <el-button type="primary" size="small" :disabled="disabled || !canAdd" @click="shootPhoto">
      {{ resolvedLabel }}（{{ items.length }}/{{ maxCount }}）
    </el-button>
    <div class="flex flex-wrap gap-2">
      <el-tag v-for="(u, i) in items" :key="u.id" closable @close="removeAt(i)">{{ u.name }}</el-tag>
    </div>
  </div>
</template>
