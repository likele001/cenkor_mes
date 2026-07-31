<template>
  <AdminPage :title="t('production.customers.title')">
    <template #actions>
      <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
      <el-button type="primary" @click="openCreate">{{ t('production.customers.createCustomer') }}</el-button>
    </template>

    <el-form :model="query" inline>
        <el-form-item :label="t('production.customers.keywordLabel')">
          <el-input v-model="query.keyword" :placeholder="t('production.customers.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="query.include_inactive" active-text="含停用" @change="reload(true)" />
        </el-form-item>
        <el-form-item v-if="canFilterOwner" label="负责人">
          <el-select v-model="query.owner_user_id" clearable filterable placeholder="全部" style="width: 180px" @change="reload(true)">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="reload(true)">{{ t('production.common.search') }}</el-button>
        </el-form-item>
      </el-form>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border @row-click="goDetail" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="code" label="编码" width="150" show-overflow-tooltip />
          <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="owner_name" label="负责人" width="120" show-overflow-tooltip />
          <el-table-column label="H5登录" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.login_username" type="success" size="small">{{ row.login_username }}</el-tag>
              <el-tag v-else type="info" size="small">{{ t('production.customers.notEnabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="可下单产品" width="110">
            <template #default="{ row }">{{ row.product_count ?? 0 }} 个</template>
          </el-table-column>
          <el-table-column prop="contact_phone" label="电话" width="140" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click.stop="openEdit(row)">{{ t('production.customers.edit') }}</el-button>
              <el-button size="small" @click.stop="goDetail(row)">{{ t('production.customers.detail') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>

    <template #extra>
      <el-dialog v-model="dlg.open" :title="dlg.id ? t('production.customers.editTitle') : t('production.customers.createTitle')" width="560px" destroy-on-close>
            <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
              <el-form-item label="编码" prop="code">
                <el-input v-model="dlg.form.code" :placeholder="t('production.customers.codePlaceholder')" :disabled="!!dlg.id" clearable />
              </el-form-item>
              <el-form-item label="名称" prop="name">
                <el-input v-model="dlg.form.name" :placeholder="t('production.customers.namePlaceholder')" />
              </el-form-item>
              <el-form-item label="联系人">
                <el-input v-model="dlg.form.contact_name" :placeholder="t('production.customers.contactNamePlaceholder')" />
              </el-form-item>
              <el-form-item label="电话">
                <el-input v-model="dlg.form.contact_phone" :placeholder="t('production.customers.phonePlaceholder')" />
              </el-form-item>
              <el-form-item label="地址">
                <el-input v-model="dlg.form.address" :placeholder="t('production.customers.addressPlaceholder')" />
              </el-form-item>
              <el-divider content-position="left">H5 登录（客户下单）</el-divider>
              <el-form-item label="登录账号">
                <el-input v-model="dlg.form.login_username" placeholder="客户在 H5 登录的用户名" />
              </el-form-item>
              <el-form-item :label="dlg.id ? '重置密码' : '登录密码'">
                <el-input v-model="dlg.form.login_password" type="password" show-password :placeholder="dlg.id ? '留空不修改' : '至少 6 位'" />
              </el-form-item>
              <el-form-item v-if="canFilterOwner" label="负责人">
                <el-select v-model="dlg.form.owner_user_id" clearable filterable placeholder="选择负责人" style="width: 100%">
                  <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="dlg.form.remark" type="textarea" :rows="2" :placeholder="t('production.customers.remarkPlaceholder')" />
              </el-form-item>
              <el-alert type="info" :closable="false" class="mb-0">
                保存后客户可用 H5 地址登录；请在「客户详情 → 可下单产品」中配置可见产品。
              </el-alert>
            </el-form>
            <template #footer>
              <el-button @click="dlg.open = false">{{ t('production.common.cancel') }}</el-button>
              <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('production.common.save') }}</el-button>
            </template>
          </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { productionApi, type CustomerOut } from '@/api/production'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const canFilterOwner = computed(() => auth.hasAnyPermission('customer.manage'))
const loading = ref(false)
const exporting = ref(false)
const items = ref<CustomerOut[]>([])
const users = ref<{ id: number; full_name: string | null; username: string }[]>([])
const query = reactive({ keyword: '', owner_user_id: null as number | null, offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: t('production.customers.pleaseInputName'), trigger: 'blur' }],
}

const dlg = reactive({
  open: false,
  saving: false,
  id: 0,
  form: {
    code: '',
    name: '',
    contact_name: '',
    contact_phone: '',
    address: '',
    remark: '',
    login_username: '',
    login_password: '',
    owner_user_id: null as number | null,
  },
})

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await productionApi.listCustomers({
      ...query,
      owner_user_id: query.owner_user_id || undefined,
    })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function goDetail(row: CustomerOut) {
  router.push(`/production/customers/${row.id}`)
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function openCreate() {
  dlg.id = 0
  dlg.form = {
    code: await previewNextCode('customer'),
    name: '',
    contact_name: '',
    contact_phone: '',
    address: '',
    remark: '',
    login_username: '',
    login_password: '',
    owner_user_id: null,
  }
  dlg.open = true
}

function openEdit(row: CustomerOut) {
  dlg.id = row.id
  dlg.form = {
    code: row.code,
    name: row.name,
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    address: row.address || '',
    remark: row.remark || '',
    login_username: row.login_username || '',
    login_password: '',
    owner_user_id: row.owner_user_id ?? null,
  }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!dlg.id && dlg.form.login_username && (!dlg.form.login_password || dlg.form.login_password.length < 6)) {
    ElMessage.warning(t('production.customers.passwordMinLength'))
    return
  }
  dlg.saving = true
  try {
    const payload = {
      code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code),
      name: dlg.form.name,
      contact_name: dlg.form.contact_name || undefined,
      contact_phone: dlg.form.contact_phone || undefined,
      address: dlg.form.address || undefined,
      remark: dlg.form.remark || undefined,
      login_username: dlg.form.login_username || undefined,
      login_password: dlg.form.login_password || undefined,
      owner_user_id: canFilterOwner.value ? (dlg.form.owner_user_id || null) : undefined,
    }
    if (dlg.id) {
      await productionApi.updateCustomer(dlg.id, payload)
    } else {
      await productionApi.createCustomer(payload)
    }
    dlg.open = false
    ElMessage.success(dlg.id ? t('production.customers.editSuccess') : t('production.customers.createdSuccess'))
    await reload(true)
  } finally {
    dlg.saving = false
  }
}

async function loadUsers() {
  if (!canFilterOwner.value) return
  const res = await productionApi.listUsers({ offset: 0, limit: 200, include_inactive: false })
  users.value = res.items ?? []
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await productionApi.exportCustomers({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `customers_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await loadUsers()
  await reload(true)
})
</script>
