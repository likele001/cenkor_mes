<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索关键词" confirm-type="search" @confirm="reload" />
      <button v-if="canCreate" class="add-btn" size="mini" @tap="openCreate">+ 新增</button>
    </view>

    <MListLayout :items="items" :loading="loading" :empty-text="`暂无${schema.title}数据`" :tap-to-select="!canEdit || !schema.deletePath" @select="onSelect">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ schema.listTitle(item as Record<string, unknown>) }}</text>
        </view>
        <AdminKvGrid
          v-if="schema.listSub?.(item as Record<string, unknown>)"
          :rows="[{ label: '摘要', value: schema.listSub(item as Record<string, unknown>) }]"
        />
      </template>
      <template v-if="canEdit && schema.deletePath" #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="onSelect(item)">编辑</button>
          <button class="adm-card-btn danger" @tap="confirmDelete(item as Record<string, unknown>)">
            {{ schema.deleteLabel || '删除' }}
          </button>
        </view>
      </template>
    </MListLayout>

    <AdminFormPopup
      :visible="formVisible"
      :mode="formMode"
      :fields="visibleFields(formMode)"
      :model="form"
      :option-map="optionMap"
      :saving="saving"
      @close="closeForm"
      @submit="submitForm"
      @update:model="patchForm"
    />
  </view>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import AdminFormPopup from '@/components/admin-ui/AdminFormPopup.vue'
import { useAdminCrudPage } from '@/composables/useAdminCrudPage'

const props = defineProps<{ schemaKey: string }>()

const {
  schema,
  items,
  loading,
  keyword,
  formVisible,
  formMode,
  saving,
  form,
  optionMap,
  canWrite,
  canCreate,
  canEdit,
  visibleFields,
  reload,
  openCreate,
  closeForm,
  submitForm,
  confirmDelete,
  onSelect,
} = useAdminCrudPage(props.schemaKey)

function patchForm(v: Record<string, unknown>) {
  Object.assign(form, v)
}

onMounted(() => {
  uni.setNavigationBarTitle({ title: schema.title })
  reload()
})
onShow(() => reload())
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
  align-items: center;
}
.search {
  flex: 1;
  background: #fff;
  border-radius: 999rpx;
  padding: 16rpx 28rpx;
  font-size: 26rpx;
  box-shadow: 0 2rpx 12rpx rgba(15, 23, 42, 0.04);
}
.add-btn {
  background: linear-gradient(135deg, #6366f1, #4338ca);
  color: #fff;
  border: none;
  border-radius: 999rpx;
  padding: 0 24rpx;
  line-height: 64rpx;
  font-size: 24rpx;
}
.row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
</style>
