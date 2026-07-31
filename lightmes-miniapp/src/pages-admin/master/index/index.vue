<template>
  <view class="adm-page">
    <AdminMenuSection
      v-if="masterItems.length"
      title="主数据"
      subtitle="与 PC 主数据菜单一致"
      :items="masterItems"
      @navigate="navigate"
    />
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AdminMenuSection from '@/components/admin-ui/AdminMenuSection.vue'
import { useAdminMenu } from '@/constants/adminMenu'

const { menuGroups, navigate } = useAdminMenu()
const masterItems = computed(() => menuGroups.value.find((g) => g.key === 'master')?.items ?? [])
</script>
