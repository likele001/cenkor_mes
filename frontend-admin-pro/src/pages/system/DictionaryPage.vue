<template>
  <AdminPage :title="t('system.dictionary.title')" class="h-full flex flex-col">
    <el-card shadow="never" class="flex-1 flex flex-col overflow-hidden" body-class="flex-1 overflow-hidden !p-0">
<div class="flex flex-col lg:flex-row lg:h-full min-h-0">
        <!-- 左侧：字典类型列表 -->
        <div class="w-full lg:w-[360px] lg:border-r border-b lg:border-b-0 border-[var(--el-border-color-light)] flex flex-col shrink-0 max-h-[40vh] lg:max-h-none">
          <div class="p-3 flex items-center gap-2 border-b border-[var(--el-border-color-light)]">
            <el-input v-model="typeQuery" :placeholder="t('system.dictionary.searchPlaceholder')" clearable style="flex:1" @input="filterTypes">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" @click="openCreateType">{{ t('system.dictionary.create') }}</el-button>
          </div>
          <div class="flex-1 overflow-auto">
            <div
              v-for="t in filteredTypes"
              :key="t.id"
              class="px-3 py-2.5 cursor-pointer hover:bg-[var(--el-fill-color-light)] border-b border-[var(--el-border-color-extra-light)]"
              :class="{ '!bg-[var(--el-color-primary-light-9)] !text-[var(--el-color-primary)]': selectedTypeId === t.id }"
              @click="selectType(t)"
            >
              <div class="font-medium text-[14px]">{{ t.name }}</div>
              <div class="text-[12px] text-[var(--el-text-color-secondary)] mt-0.5">{{ t.code }}</div>
            </div>
            <el-empty v-if="!loadingTypes && filteredTypes.length === 0" :description="t('system.dictionary.noDictTypes')" />
          </div>
        </div>

        <!-- 右侧：字典项列表 -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <div class="p-3 flex items-center justify-between border-b border-[var(--el-border-color-light)]">
            <span class="font-medium">
              {{ selectedType ? `${selectedType.name} - ${t('system.dictionary.dictItem')}` : t('system.dictionary.selectDictType') }}
            </span>
            <el-button type="primary" :disabled="!selectedTypeId" @click="openCreateItem">{{ t('system.dictionary.createDictItem') }}</el-button>
          </div>
          <div class="flex-1 overflow-auto p-3 min-h-0">
            <div v-if="selectedTypeId" v-loading="loadingItems">
              <el-table class="hidden lg:block w-full" :data="items" border height="100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="label" :label="t('system.dictionary.displayText')" min-width="150" />
                <el-table-column prop="value" :label="t('system.dictionary.value')" min-width="150" />
                <el-table-column prop="sort_order" :label="t('system.dictionary.sort')" width="100" />
                <el-table-column :label="t('system.dictionary.status')" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('system.dictionary.enabled') : t('system.dictionary.disabled') }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="t('system.dictionary.operation')" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-popconfirm :title="t('system.dictionary.confirmDeleteItem')" @confirm="deleteItem(row)">
                      <template #reference>
                        <el-button size="small" type="danger">{{ t('system.dictionary.delete') }}</el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                </el-table-column>
              </el-table>
              <div class="lg:hidden space-y-3">
                <div v-for="row in items" :key="row.id" class="admin-mobile-row">
                  <div class="admin-mobile-row__head">
                    <div class="min-w-0">
                      <div class="font-semibold text-el-primary">{{ row.label }}</div>
                      <div class="text-xs text-el-placeholder">{{ row.value }} · #{{ row.id }}</div>
                    </div>
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('system.dictionary.enabled') : t('system.dictionary.disabled') }}</el-tag>
                  </div>
                  <dl class="admin-mobile-kv">
                    <dt>{{ t('system.dictionary.sort') }}</dt>
                    <dd>{{ row.sort_order }}</dd>
                  </dl>
                  <div class="admin-mobile-actions">
                    <el-popconfirm :title="t('system.dictionary.confirmDeleteItem')" @confirm="deleteItem(row)">
                      <template #reference>
                        <el-button size="small" type="danger">{{ t('system.dictionary.delete') }}</el-button>
                      </template>
                    </el-popconfirm>
                  </div>
                </div>
                <el-empty v-if="!loadingItems && !items.length" :description="t('system.dictionary.noDictItems')" />
              </div>
            </div>
            <el-empty v-else-if="!loadingItems" :description="t('system.dictionary.selectDictTypeHint')" />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新增字典类型弹窗 -->
    <el-dialog v-model="typeDlg.open" :title="t('system.dictionary.dictType')" width="480px" destroy-on-close>
      <el-form ref="typeFormRef" :model="typeDlg.form" :rules="typeRules" label-width="80px">
        <el-form-item :label="t('system.dictionary.code')" prop="code">
          <el-input v-model="typeDlg.form.code" :placeholder="t('system.dictionary.codePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('system.dictionary.name')" prop="name">
          <el-input v-model="typeDlg.form.name" :placeholder="t('system.dictionary.namePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDlg.open = false">{{ t('system.dictionary.cancel') }}</el-button>
        <el-button type="primary" :loading="typeDlg.saving" @click="saveType">{{ t('system.dictionary.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 新增字典项弹窗 -->
    <el-dialog v-model="itemDlg.open" :title="t('system.dictionary.createDictItem')" width="480px" destroy-on-close>
      <el-form ref="itemFormRef" :model="itemDlg.form" :rules="itemRules" label-width="80px">
        <el-form-item :label="t('system.dictionary.displayText')" prop="label">
          <el-input v-model="itemDlg.form.label" :placeholder="t('system.dictionary.displayTextPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('system.dictionary.value')" prop="value">
          <el-input v-model="itemDlg.form.value" :placeholder="t('system.dictionary.valuePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('system.dictionary.sort')" prop="sort_order">
          <el-input-number v-model="itemDlg.form.sort_order" :min="0" :max="9999" controls-position="right" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDlg.open = false">{{ t('system.dictionary.cancel') }}</el-button>
        <el-button type="primary" :loading="itemDlg.saving" @click="saveItem">{{ t('system.dictionary.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { dictionaryApi, type DictTypeOut, type DictItemOut } from '@/api/dictionary'

const { t } = useI18n()

/* ---- 字典类型 ---- */
const loadingTypes = ref(false)
const types = ref<DictTypeOut[]>([])
const typeQuery = ref('')

const filteredTypes = computed(() => {
  const kw = typeQuery.value.trim().toLowerCase()
  if (!kw) return types.value
  return types.value.filter((t) => t.code.toLowerCase().includes(kw) || t.name.toLowerCase().includes(kw))
})

function filterTypes() {
  // computed 自动响应
}

async function loadTypes() {
  loadingTypes.value = true
  try {
    const res = await dictionaryApi.listTypes({ offset: 0, limit: 500 })
    types.value = res.items ?? []
  } finally {
    loadingTypes.value = false
  }
}

const selectedTypeId = ref<number | null>(null)
const selectedType = ref<DictTypeOut | null>(null)

function selectType(row: DictTypeOut) {
  selectedTypeId.value = row.id
  selectedType.value = row
  loadItems(row.id)
}

/* ---- 字典类型弹窗 ---- */
const typeDlg = reactive({
  open: false,
  saving: false,
  form: { code: '', name: '' },
})
const typeFormRef = ref<FormInstance>()
const typeRules: FormRules = {
  code: [{ required: true, message: () => t('system.dictionary.pleaseInputCode'), trigger: 'blur' }],
  name: [{ required: true, message: () => t('system.dictionary.pleaseInputName'), trigger: 'blur' }],
}

function openCreateType() {
  typeDlg.form = { code: '', name: '' }
  typeDlg.open = true
}

async function saveType() {
  const ok = await typeFormRef.value?.validate().catch(() => false)
  if (!ok) return
  typeDlg.saving = true
  try {
    await dictionaryApi.createType(typeDlg.form)
    typeDlg.open = false
    ElMessage.success(t('system.dictionary.typeCreated'))
    await loadTypes()
  } finally {
    typeDlg.saving = false
  }
}

/* ---- 字典项 ---- */
const loadingItems = ref(false)
const items = ref<DictItemOut[]>([])

async function loadItems(dictTypeId: number) {
  loadingItems.value = true
  items.value = []
  try {
    const res = await dictionaryApi.listItems(dictTypeId, { offset: 0, limit: 500 })
    items.value = res.items ?? []
  } finally {
    loadingItems.value = false
  }
}

/* ---- 字典项弹窗 ---- */
const itemDlg = reactive({
  open: false,
  saving: false,
  form: { label: '', value: '', sort_order: 0 },
})
const itemFormRef = ref<FormInstance>()
const itemRules: FormRules = {
  label: [{ required: true, message: () => t('system.dictionary.pleaseInputDisplayText'), trigger: 'blur' }],
  value: [{ required: true, message: () => t('system.dictionary.pleaseInputValue'), trigger: 'blur' }],
}

function openCreateItem() {
  itemDlg.form = { label: '', value: '', sort_order: 0 }
  itemDlg.open = true
}

async function saveItem() {
  const ok = await itemFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!selectedTypeId.value) return
  itemDlg.saving = true
  try {
    await dictionaryApi.createItem(selectedTypeId.value, itemDlg.form)
    itemDlg.open = false
    ElMessage.success(t('system.dictionary.itemCreated'))
    await loadItems(selectedTypeId.value)
  } finally {
    itemDlg.saving = false
  }
}

async function deleteItem(row: DictItemOut) {
  if (!selectedTypeId.value) return
  try {
    await dictionaryApi.deleteItem(selectedTypeId.value, row.id)
    ElMessage.success(t('system.dictionary.deleted'))
    await loadItems(selectedTypeId.value)
  } catch {
    // error already shown by http client
  }
}

onMounted(async () => {
  await loadTypes()
})
</script>
