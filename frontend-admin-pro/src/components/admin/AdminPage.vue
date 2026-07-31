<template>
  <div class="admin-page">
    <el-card shadow="never" class="admin-page-card">
      <div v-if="title || description || $slots.actions" class="admin-page__head flex items-center justify-between gap-3 flex-wrap">
        <div class="min-w-0">
          <div v-if="title" class="text-[16px] font-semibold text-[var(--el-text-color-primary)]">{{ title }}</div>
          <p v-if="description" class="text-[13px] text-[var(--admin-brand-subtitle)] mt-0.5">{{ description }}</p>
        </div>
        <div v-if="$slots.actions" class="admin-page__actions flex items-center gap-2 flex-wrap">
          <slot name="actions" />
        </div>
      </div>
      <slot />
    </el-card>
    <slot name="extra" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
}>()
</script>

<style scoped>
.admin-page-card :deep(.el-card__body) {
  padding: 16px;
}

@media (min-width: 640px) {
  .admin-page-card :deep(.el-card__body) {
    padding: 20px;
  }
}

.admin-page__head + :slotted(*) {
  margin-top: 0;
}
</style>
