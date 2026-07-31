<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索名称/编码" @confirm="loadList" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新增</button>
    </view>

    <MListLayout :items="filtered" :loading="loading" empty-text="暂无质检模板">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name }}</text>
          <view class="adm-list-tags">
            <text class="adm-list-badge tone-active">{{ item.items?.length || 0 }}项</text>
          </view>
        </view>
        <AdminKvGrid :rows="[
          { label: '编码', value: item.code },
          { label: '工序ID', value: item.process_id ? '#' + item.process_id : '全局' },
          { label: '描述', value: item.description || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
          <button class="adm-card-btn danger" @tap="confirmDisable(item)">停用</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ formMode === 'create' ? '新增质检模板' : '编辑质检模板' }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">编码*</text>
            <input v-model="form.code" class="input" placeholder="如：QC-WELD-001" />
          </view>
          <view class="field">
            <text class="label">名称*</text>
            <input v-model="form.name" class="input" placeholder="如：焊接工序检查项" />
          </view>
          <view class="field">
            <text class="label">工序ID</text>
            <input v-model.number="form.process_id" class="input" type="number" placeholder="0=全局" />
          </view>
          <view class="field">
            <text class="label">描述</text>
            <textarea v-model="form.description" class="textarea" placeholder="可选" />
          </view>

          <view class="divider">检查项明细</view>
          <view v-for="(it, i) in form.items" :key="i" class="check-item">
            <view class="check-item-row">
              <text class="check-seq">{{ i + 1 }}</text>
              <input v-model="it.item_name" class="input flex-1" placeholder="检查项名称" />
              <picker :range="Object.values(ITEM_TYPE_LABELS)" @change="e => it.item_type = Object.keys(ITEM_TYPE_LABELS)[e.detail.value]">
                <view class="input picker type-picker">{{ ITEM_TYPE_LABELS[it.item_type] }}</view>
              </picker>
              <button class="btn-mini danger" @tap="removeItem(i)">删</button>
            </view>
            <view class="check-item-ext" v-if="it.item_type === 'measure'">
              <input v-model="it.standard_value" class="input small" placeholder="标准值" />
              <input v-model="it.upper_limit" class="input small" placeholder="上限" />
              <input v-model="it.lower_limit" class="input small" placeholder="下限" />
              <input v-model="it.unit" class="input small" placeholder="单位" />
            </view>
            <view class="check-item-ext" v-else-if="it.item_type === 'pass_fail'">
              <input v-model="it.standard_value" class="input small" placeholder="标准说明(可选)" />
            </view>
            <view class="check-item-opt">
              <label class="check-opt">
                <checkbox :checked="it.is_required" @tap="it.is_required = !it.is_required" />
                <text>必审</text>
              </label>
            </view>
          </view>
          <button class="btn-add-item" @tap="addItem">+ 添加检查项</button>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost" @tap="formVisible = false">取消</button>
          <button class="btn primary" :loading="saving" @tap="submitForm">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { qualityApi, ITEM_TYPE_LABELS, type TemplateOut, type TemplateItem } from '@/api/admin/quality'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<TemplateOut[]>([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(t => t.name.toLowerCase().includes(kw) || t.code.toLowerCase().includes(kw))
})

async function loadList() {
  if (!requirePermission('report.audit')) return
  loading.value = true
  try {
    const r = await qualityApi.listTemplates()
    items.value = r.items
  } catch { items.value = [] }
  finally { loading.value = false }
}

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  code: '', name: '', description: '', process_id: 0,
  items: [] as TemplateItem[],
})

function resetForm() {
  form.code = ''; form.name = ''; form.description = ''; form.process_id = 0; form.items = []
}

function addItem() {
  form.items.push({
    seq: form.items.length + 1, item_name: '', item_type: 'pass_fail',
    standard_value: null, upper_limit: null, lower_limit: null, unit: null,
    is_required: true, remark: null,
  })
}

function removeItem(i: number) {
  form.items.splice(i, 1)
}

function openCreate() {
  resetForm(); formMode.value = 'create'; editingId.value = null; addItem(); formVisible.value = true
}

function openEdit(t: TemplateOut) {
  formMode.value = 'edit'; editingId.value = t.id
  form.code = t.code; form.name = t.name; form.description = t.description || ''
  form.process_id = t.process_id || 0
  form.items = t.items.map(it => ({ ...it }))
  formVisible.value = true
}

async function submitForm() {
  if (!form.code.trim()) { uni.showToast({ title: '请输入编码', icon: 'none' }); return }
  if (!form.name.trim()) { uni.showToast({ title: '请输入名称', icon: 'none' }); return }
  saving.value = true
  try {
    const payload = {
      code: form.code.trim(), name: form.name.trim(),
      description: form.description.trim() || undefined,
      process_id: form.process_id || undefined,
      items: form.items.map((it, i) => ({ ...it, seq: i + 1 })),
    }
    if (formMode.value === 'create') {
      await qualityApi.createTemplate(payload)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await qualityApi.updateTemplate(editingId.value, payload)
      uni.showToast({ title: '保存成功', icon: 'success' })
    }
    formVisible.value = false; await loadList()
  } catch { /* handled */ }
  finally { saving.value = false }
}

function confirmDisable(t: TemplateOut) {
  uni.showModal({
    title: '停用模板', content: `确定停用「${t.name}」？`,
    success: async (res) => {
      if (!res.confirm) return
      try { await qualityApi.deleteTemplate(t.id); uni.showToast({ title: '已停用', icon: 'success' }); await loadList() }
      catch { /* handled */ }
    },
  })
}

onShow(loadList)
</script>

<style scoped>
.divider { font-size: 28rpx; font-weight: 700; color: #1e293b; padding: 20rpx 0 12rpx; }
.check-item { background: #f8fafc; border-radius: 12rpx; padding: 16rpx; margin-bottom: 12rpx; }
.check-item-row { display: flex; align-items: center; gap: 8rpx; }
.check-seq { width: 36rpx; height: 36rpx; border-radius: 999rpx; background: #2563eb; color: #fff; text-align: center; line-height: 36rpx; font-size: 22rpx; flex-shrink: 0; }
.flex-1 { flex: 1; min-width: 0; }
.type-picker { width: 160rpx; }
.check-item-ext { display: flex; gap: 8rpx; margin-top: 12rpx; }
.check-item-ext .input.small { width: 120rpx; }
.check-item-opt { margin-top: 12rpx; }
.check-opt { display: flex; align-items: center; gap: 8rpx; font-size: 24rpx; color: #64748b; }
.btn-add-item { width: 100%; padding: 20rpx; border: 1rpx dashed #cbd5e1; border-radius: 12rpx; background: #fff; text-align: center; font-size: 26rpx; color: #2563eb; margin-top: 8rpx; }
.btn-mini { padding: 8rpx 16rpx; border-radius: 8rpx; font-size: 22rpx; border: none; }
.btn-mini.danger { background: #fee2e2; color: #b91c1c; }
</style>
