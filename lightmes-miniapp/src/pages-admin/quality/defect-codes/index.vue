<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索名称/编码" @confirm="loadList" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新增</button>
    </view>

    <MListLayout :items="filtered" :loading="loading" empty-text="暂无缺陷代码">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name }}</text>
          <view class="adm-list-tags">
            <text class="adm-list-badge" :class="severityTone(item.severity)">
              {{ SEVERITY_LABELS[item.severity] || item.severity }}
            </text>
          </view>
        </view>
        <AdminKvGrid :rows="[
          { label: '编码', value: item.code },
          { label: '描述', value: item.description || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
          <button class="adm-card-btn danger" @tap="confirmDelete(item)">删除</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ formMode === 'create' ? '新增缺陷代码' : '编辑缺陷代码' }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">编码*</text>
            <input v-model="form.code" class="input" placeholder="如：SCR-001" />
          </view>
          <view class="field">
            <text class="label">名称*</text>
            <input v-model="form.name" class="input" placeholder="如：表面划伤" />
          </view>
          <view class="field">
            <text class="label">严重程度</text>
            <picker :range="Object.values(SEVERITY_LABELS)" @change="e => form.severity = Object.keys(SEVERITY_LABELS)[e.detail.value]">
              <view class="input picker">{{ SEVERITY_LABELS[form.severity] }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">描述</text>
            <textarea v-model="form.description" class="textarea" placeholder="可选" />
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
import { qualityApi, SEVERITY_LABELS, type DefectCodeOut } from '@/api/admin/quality'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<DefectCodeOut[]>([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(d => d.name.toLowerCase().includes(kw) || d.code.toLowerCase().includes(kw))
})

function severityTone(s: string): string {
  if (s === 'critical') return 'tone-danger'
  if (s === 'major') return 'tone-pending'
  return 'tone-draft'
}

async function loadList() {
  if (!requirePermission('report.audit')) return
  loading.value = true
  try {
    const r = await qualityApi.listDefectCodes()
    items.value = r.items
  } catch { items.value = [] }
  finally { loading.value = false }
}

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ code: '', name: '', severity: 'minor', description: '' })

function resetForm() { form.code = ''; form.name = ''; form.severity = 'minor'; form.description = '' }

function openCreate() { resetForm(); formMode.value = 'create'; editingId.value = null; formVisible.value = true }

function openEdit(d: DefectCodeOut) {
  formMode.value = 'edit'; editingId.value = d.id
  form.code = d.code; form.name = d.name; form.severity = d.severity; form.description = d.description || ''
  formVisible.value = true
}

async function submitForm() {
  if (!form.code.trim()) { uni.showToast({ title: '请输入编码', icon: 'none' }); return }
  if (!form.name.trim()) { uni.showToast({ title: '请输入名称', icon: 'none' }); return }
  saving.value = true
  try {
    const payload = { code: form.code.trim(), name: form.name.trim(), severity: form.severity, description: form.description.trim() || undefined }
    if (formMode.value === 'create') {
      await qualityApi.createDefectCode(payload)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await qualityApi.updateDefectCode(editingId.value, payload)
      uni.showToast({ title: '保存成功', icon: 'success' })
    }
    formVisible.value = false; await loadList()
  } catch { /* handled */ }
  finally { saving.value = false }
}

function confirmDelete(d: DefectCodeOut) {
  uni.showModal({
    title: '删除缺陷代码', content: `确定删除「${d.name}」？`,
    success: async (res) => {
      if (!res.confirm) return
      try { await qualityApi.deleteDefectCode(d.id); uni.showToast({ title: '已删除', icon: 'success' }); await loadList() }
      catch { /* handled */ }
    },
  })
}

onShow(loadList)
</script>
