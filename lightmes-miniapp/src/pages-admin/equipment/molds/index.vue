<template>
  <view class="adm-page">
    <view class="toolbar">
      <view class="filter-row">
        <picker :range="typeOpts" @change="onTypeFilter">
          <text class="filter-tag">{{ typeOpts[typeIdx] || '全部类型' }}</text>
        </picker>
        <picker :range="statusOpts" @change="onStatusFilter">
          <text class="filter-tag">{{ statusOpts[statusIdx] || '全部状态' }}</text>
        </picker>
      </view>
      <input v-model="keyword" class="search" placeholder="搜索名称/编码" @confirm="loadList" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新增</button>
    </view>

    <MListLayout :items="filtered" :loading="loading" empty-text="暂无模具">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name }}</text>
          <view class="adm-list-tags">
            <text class="adm-list-badge" :class="'tone-' + lifeTag(lifePercent(item))">
              {{ lifePercent(item) }}%
            </text>
            <text class="adm-list-badge" :class="statusTone(item.status)">
              {{ MOLD_STATUS_LABELS[item.status] || item.status }}
            </text>
          </view>
        </view>
        <AdminKvGrid :rows="kvRows(item)" />
        <view class="adm-progress-wrap" v-if="item.expected_lifespan">
          <view class="adm-progress-meta">
            <text>模次寿命</text>
            <text>{{ item.current_shots }} / {{ item.expected_lifespan }}</text>
          </view>
          <view class="adm-progress-bar">
            <view class="adm-progress-fill" :style="{ width: lifePercent(item) + '%' }" />
          </view>
        </view>
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
          <button class="adm-card-btn primary" @tap="toMaintenance(item)">维保</button>
          <button class="adm-card-btn teal" @tap="toBindings(item)">工序</button>
          <button class="adm-card-btn danger" @tap="confirmDelete(item)">删除</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ formMode === 'create' ? '新增模具' : '编辑模具' }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">名称*</text>
            <input v-model="form.name" class="input" placeholder="例如：模具A" />
          </view>
          <view class="field">
            <text class="label">类型</text>
            <picker :range="Object.values(MOLD_TYPES)" @change="e => form.mold_type = Object.keys(MOLD_TYPES)[e.detail.value]">
              <view class="input picker">{{ MOLD_TYPES[form.mold_type] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">车间</text>
            <input v-model="form.workshop" class="input" placeholder="例如：注塑车间" />
          </view>
          <view class="field">
            <text class="label">型号/规格</text>
            <input v-model="form.model" class="input" placeholder="可选" />
          </view>
          <view class="field">
            <text class="label">预期寿命(次)</text>
            <input v-model.number="form.expected_lifespan" class="input" type="number" placeholder="0" />
          </view>
          <view class="field">
            <text class="label">维保间隔(次)</text>
            <input v-model.number="form.maintenance_interval_shots" class="input" type="number" placeholder="0" />
          </view>
          <view class="field">
            <text class="label">购买日期</text>
            <picker mode="date" @change="e => form.purchase_date = e.detail.value">
              <view class="input picker">{{ form.purchase_date || '请选择' }}</view>
            </picker>
          </view>
          <view class="field" v-if="formMode === 'edit'">
            <text class="label">状态</text>
            <picker :range="Object.values(MOLD_STATUS_LABELS)" @change="e => form.status = Object.keys(MOLD_STATUS_LABELS)[e.detail.value]">
              <view class="input picker">{{ MOLD_STATUS_LABELS[form.status] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">备注</text>
            <textarea v-model="form.remark" class="textarea" placeholder="可选" />
          </view>
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
import { moldApi, MOLD_TYPES, MOLD_STATUS_LABELS, lifePercent, lifeTag, type MoldOut } from '@/api/admin/mold'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<MoldOut[]>([])
const loading = ref(false)
const keyword = ref('')
const typeIdx = ref(0)
const statusIdx = ref(0)
const typeOpts = ['全部类型', ...Object.values(MOLD_TYPES)]
const statusOpts = ['全部状态', ...Object.values(MOLD_STATUS_LABELS)]
const typeKeys = ['', ...Object.keys(MOLD_TYPES)]
const statusKeys = ['', ...Object.keys(MOLD_STATUS_LABELS)]

const filtered = computed(() => {
  let list = items.value
  const kw = keyword.value.trim().toLowerCase()
  if (kw) list = list.filter(m => m.name.toLowerCase().includes(kw) || m.code.toLowerCase().includes(kw))
  return list
})

function kvRows(m: MoldOut) {
  return [
    { label: '编码', value: m.code },
    { label: '类型', value: MOLD_TYPES[m.mold_type] || m.mold_type },
    { label: '车间', value: m.workshop },
    { label: '模次', value: String(m.current_shots) },
  ]
}

function statusTone(s: string): string {
  if (s === 'active') return 'tone-success'
  if (s === 'repair') return 'tone-pending'
  return 'tone-draft'
}

function onTypeFilter(e: { detail: { value: number } }) {
  typeIdx.value = e.detail.value
  loadList()
}

function onStatusFilter(e: { detail: { value: number } }) {
  statusIdx.value = e.detail.value
  loadList()
}

async function loadList() {
  if (!requirePermission('equipment.manage')) return
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (typeKeys[typeIdx.value]) params.mold_type = typeKeys[typeIdx.value]
    if (statusKeys[statusIdx.value]) params.status = statusKeys[statusIdx.value]
    const r = await moldApi.list(params)
    items.value = r.items
  } catch { items.value = [] }
  finally { loading.value = false }
}

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  name: '', mold_type: 'injection', workshop: '', model: '',
  expected_lifespan: 0, maintenance_interval_shots: 0,
  purchase_date: '', status: 'active', remark: '',
})

function resetForm() {
  form.name = ''; form.mold_type = 'injection'; form.workshop = ''
  form.model = ''; form.expected_lifespan = 0; form.maintenance_interval_shots = 0
  form.purchase_date = ''; form.status = 'active'; form.remark = ''
}

function openCreate() {
  resetForm(); formMode.value = 'create'; editingId.value = null; formVisible.value = true
}

function openEdit(m: MoldOut) {
  formMode.value = 'edit'; editingId.value = m.id
  form.name = m.name; form.mold_type = m.mold_type; form.workshop = m.workshop || ''
  form.model = m.model || ''; form.expected_lifespan = m.expected_lifespan || 0
  form.maintenance_interval_shots = m.maintenance_interval_shots || 0
  form.purchase_date = m.purchase_date || ''; form.status = m.status; form.remark = m.remark || ''
  formVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) { uni.showToast({ title: '请输入名称', icon: 'none' }); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (formMode.value === 'create') {
      await moldApi.create(payload)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await moldApi.update(editingId.value, payload)
      uni.showToast({ title: '保存成功', icon: 'success' })
    }
    formVisible.value = false; await loadList()
  } catch { /* handled */ }
  finally { saving.value = false }
}

function confirmDelete(m: MoldOut) {
  uni.showModal({
    title: '删除模具', content: `确定删除「${m.name}」？`,
    success: async (res) => {
      if (!res.confirm) return
      try { await moldApi.delete(m.id); uni.showToast({ title: '已删除', icon: 'success' }); await loadList() }
      catch { /* handled */ }
    },
  })
}

function toMaintenance(m: MoldOut) {
  uni.navigateTo({ url: `/pages-admin/equipment/molds/maintenance/index?moldId=${m.id}&name=${encodeURIComponent(m.name)}` })
}

function toBindings(m: MoldOut) {
  uni.navigateTo({ url: `/pages-admin/equipment/molds/bindings/index?moldId=${m.id}&name=${encodeURIComponent(m.name)}` })
}

onShow(loadList)
</script>

<style scoped>
.filter-row { display: flex; gap: 12rpx; margin-bottom: 12rpx; }
.filter-tag { background: #f1f5f9; padding: 8rpx 20rpx; border-radius: 999rpx; font-size: 24rpx; color: #475569; }
</style>
