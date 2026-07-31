<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { UploaderFileListItem } from 'vant'
import { uploadFile, type UploadRespData } from '@/api/files'

export type UploadedFile = {
  url: string
  name?: string
  file_id?: number
  mime_type?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: UploadedFile[]
    accept?: string
    maxCount?: number
    disabled?: boolean
  }>(),
  {
    accept: 'image/*,video/*',
    maxCount: 9,
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: UploadedFile[]): void
}>()

type UItem = UploaderFileListItem & { name?: string }

const fileList = ref<UItem[]>(
  (props.modelValue || []).map((f) => ({
    url: f.url,
    name: f.name || '',
  })),
)

watch(
  () => props.modelValue,
  (v) => {
    fileList.value = (v || []).map((f) => ({ url: f.url, name: f.name || '' }))
  },
  { deep: true },
)

const uploaded = computed<UploadedFile[]>(() =>
  fileList.value
    .filter((x) => Boolean(x.url))
    .map((x) => ({
      url: x.url || '',
      name: (x as any).name || (x as any).file?.name || '',
    })),
)

function syncOut(extra?: Partial<Record<string, UploadRespData>>) {
  if (!extra) {
    emit('update:modelValue', uploaded.value)
    return
  }
  const next: UploadedFile[] = uploaded.value.map((x) => {
    const e = extra[x.url]
    return e
      ? { url: x.url, name: x.name, file_id: e.file_id, mime_type: e.mime_type }
      : x
  })
  emit('update:modelValue', next)
}

async function afterRead(item: any) {
  const items = Array.isArray(item) ? item : [item]
  const extra: Partial<Record<string, UploadRespData>> = {}
  for (const it of items) {
    const f: File | undefined = it?.file
    if (!f) continue
    it.status = 'uploading'
    it.message = '上传中'
    try {
      const res = await uploadFile(f)
      const url = res?.url || ''
      if (!url) throw new Error('上传失败')
      it.status = 'done'
      it.message = ''
      it.url = url
      extra[url] = res
    } catch {
      it.status = 'failed'
      it.message = '上传失败'
    }
  }
  syncOut(extra)
}

function beforeDelete(_: any, detail: { index: number }) {
  fileList.value.splice(detail.index, 1)
  syncOut()
  return true
}
</script>

<template>
  <van-uploader
    v-model="fileList"
    :accept="accept"
    :max-count="maxCount"
    :disabled="disabled"
    :after-read="afterRead"
    :before-delete="beforeDelete"
    preview-size="80"
  />
</template>
