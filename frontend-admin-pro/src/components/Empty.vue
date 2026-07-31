<template>
  <AdminEmpty v-bind="$attrs">
    <template v-if="$slots.action" #action>
      <slot name="action" />
    </template>
  </AdminEmpty>
</template>

<script setup lang="ts">
import AdminEmpty from '@/components/admin/AdminEmpty.vue'
</script>
