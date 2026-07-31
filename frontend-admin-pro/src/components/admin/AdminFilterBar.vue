<template>
  <div class="admin-filter-bar flex items-center justify-between gap-3 flex-wrap">
    <div v-if="$slots.default" class="flex items-center gap-2 flex-wrap min-w-0">
      <slot />
    </div>
    <div class="flex items-center gap-2 flex-wrap ml-auto">
      <slot name="extra" />
      <el-button v-if="showSearch" size="small" type="primary" @click="$emit('search')">
        {{ t('common.search') }}
      </el-button>
      <el-button v-if="showReset" size="small" @click="$emit('reset')">
        {{ t('common.reset') }}
      </el-button>
      <el-button v-if="showExport" size="small" @click="$emit('export')">
        {{ t('common.export') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

withDefaults(
  defineProps<{
    showSearch?: boolean
    showReset?: boolean
    showExport?: boolean
  }>(),
  {
    showSearch: false,
    showReset: false,
    showExport: false,
  }
)

defineEmits<{
  search: []
  reset: []
  export: []
}>()
</script>
