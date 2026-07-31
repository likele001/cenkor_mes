<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索用户" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无用户" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.full_name || item.username }}</text>
          <text class="adm-list-badge tone-active">{{ (item.roles || []).length ? '已授权' : '无角色' }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '用户名', value: item.username || '—' },
          { label: '角色', value: (item.roles || []).map((r) => r.name).join('、') || '无' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ formMode === 'create' ? '新建用户' : '编辑用户' }}</text></view>
        <scroll-view scroll-y class="body">
          <view v-if="formMode === 'create'" class="field">
            <text class="label">用户名*</text><input v-model="form.username" class="input" />
          </view>
          <view class="field">
            <text class="label">{{ formMode === 'create' ? '密码*' : '新密码(可选)' }}</text>
            <input v-model="form.password" class="input" password />
          </view>
          <view class="field"><text class="label">姓名</text><input v-model="form.full_name" class="input" /></view>
          <view class="field">
            <text class="label">部门</text>
            <picker :range="deptLabels" @change="onDeptPick">
              <view class="input picker">{{ deptLabels[deptIndex] || '无' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">角色*</text></view>
          <view v-for="role in roles" :key="role.id" class="role-row" @tap="toggleRole(role.id)">
            <text :class="['check', selectedRoles.has(role.id) ? 'on' : '']">{{ selectedRoles.has(role.id) ? '✓' : '' }}</text>
            <text>{{ role.name }}({{ role.code }})</text>
          </view>
        </scroll-view>
        <view class="foot"><button class="btn primary" :loading="saving" @tap="submit">保存</button></view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { systemAdminApi, type UserRow } from '@/api/admin/system'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<UserRow[]>([])
const roles = ref<{ id: number; code: string; name: string }[]>([])
const departments = ref<{ id: number; name: string; code?: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const deptIndex = ref(0)
const selectedRoles = ref(new Set<number>())
const form = reactive({ username: '', password: '', full_name: '' })

const deptLabels = computed(() => ['无部门', ...departments.value.map((d) => d.name)])

onShow(async () => {
  if (!requirePermission('user.manage')) return
  const [r, d] = await Promise.all([systemAdminApi.listRoles(), systemAdminApi.listDepartments()])
  roles.value = r.items || []
  departments.value = d.items || []
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await systemAdminApi.listUsers({ limit: 50, keyword: keyword.value.trim() || undefined, include_inactive: true })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function toggleRole(id: number) {
  const s = new Set(selectedRoles.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedRoles.value = s
}
function onDeptPick(e: { detail: { value: number } }) { deptIndex.value = Number(e.detail.value) }

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  form.username = ''
  form.password = ''
  form.full_name = ''
  deptIndex.value = 0
  selectedRoles.value = new Set()
  formVisible.value = true
}

async function openEdit(row: UserRow) {
  formMode.value = 'edit'
  editingId.value = row.id
  try {
    const u = await systemAdminApi.getUser(row.id)
    form.username = u.username
    form.password = ''
    form.full_name = u.full_name || ''
    deptIndex.value = u.department_id ? departments.value.findIndex((d) => d.id === u.department_id) + 1 : 0
    selectedRoles.value = new Set((u.roles || []).map((r) => r.id))
    formVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function submit() {
  if (!selectedRoles.value.size) {
    uni.showToast({ title: '请选择角色', icon: 'none' })
    return
  }
  saving.value = true
  try {
    const deptId = deptIndex.value > 0 ? departments.value[deptIndex.value - 1]?.id : null
    const payload: Record<string, unknown> = {
      full_name: form.full_name.trim() || null,
      department_id: deptId,
      role_ids: [...selectedRoles.value],
    }
    if (formMode.value === 'create') {
      if (!form.username.trim() || !form.password) throw new Error('用户名和密码必填')
      payload.username = form.username.trim()
      payload.password = form.password
      await systemAdminApi.createUser(payload)
    } else if (editingId.value) {
      if (form.password) payload.password = form.password
      await systemAdminApi.updateUser(editingId.value, payload)
    }
    uni.showToast({ title: '保存成功', icon: 'success' })
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.picker { color: #334155; }
.role-row { display: flex; align-items: center; gap: 12rpx; padding: 12rpx 0; font-size: 28rpx; }
.check { width: 36rpx; height: 36rpx; border: 2rpx solid #cbd5e1; border-radius: 8rpx; text-align: center; line-height: 32rpx; font-size: 22rpx; }
.check.on { background: #4338ca; color: #fff; border-color: #4338ca; }
.foot { padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { border-radius: 12rpx; font-size: 28rpx; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
</style>
