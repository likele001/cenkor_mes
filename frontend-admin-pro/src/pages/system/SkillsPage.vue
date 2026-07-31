<template>
  <AdminPage :title="t('system.skills.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-button type="primary" @click="openCreateSkill">{{ t('system.skills.createSkill') }}</el-button>
          <el-button @click="reloadSkills(true)">{{ t('system.skills.refresh') }}</el-button>
        </div>
    </template>


      <el-tabs class="mt-4" v-model="active">
        <el-tab-pane :label="t('system.skills.skillDict')" name="skills">
          <div class="flex items-center gap-2 flex-wrap">
            <el-input v-model="skillQuery.keyword" :placeholder="t('system.skills.searchPlaceholder')" style="width: 220px" @keyup.enter="reloadSkills(true)" />
            <el-checkbox v-model="skillQuery.include_inactive" @change="reloadSkills(true)">{{ t('system.skills.includeDisabled') }}</el-checkbox>
          </div>

          <div class="mt-3" v-loading="loadingSkills">
            <el-table class="hidden lg:block w-full" :data="skills" border>
              <el-table-column prop="id" label="ID" width="90" />
              <el-table-column prop="code" :label="t('system.skills.code')" width="220" />
              <el-table-column prop="name" :label="t('system.skills.name')" min-width="220" />
              <el-table-column :label="t('system.skills.status')" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('system.skills.enabled') : t('system.skills.disabled') }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('system.skills.operation')" width="220" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click="openEditSkill(row)">{{ t('system.skills.edit') }}</el-button>
                  <el-popconfirm :title="t('system.skills.confirmDisable')" @confirm="disableSkill(row.id)">
                    <template #reference>
                      <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.skills.disable') }}</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>

            <div class="lg:hidden space-y-3">
              <div v-for="row in skills" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary">{{ row.name }}</div>
                    <div class="text-xs text-el-placeholder">{{ row.code }} · #{{ row.id }}</div>
                  </div>
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('system.skills.enabled') : t('system.skills.disabled') }}</el-tag>
                </div>
                <div class="admin-mobile-actions">
                  <el-button size="small" @click="openEditSkill(row)">{{ t('system.skills.edit') }}</el-button>
                  <el-popconfirm :title="t('system.skills.confirmDisable')" @confirm="disableSkill(row.id)">
                    <template #reference>
                      <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.skills.disable') }}</el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
              <el-empty v-if="!loadingSkills && !skills.length" :description="t('system.skills.noSkills')" />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('system.skills.userSkills')" name="userSkills">
          <p class="text-xs text-zinc-500 mb-2">{{ t('system.skills.userSkillsHint') }}</p>
          <div class="flex items-center gap-2 flex-wrap">
            <el-select
              v-model="userSkill.user_id"
              filterable
              remote
              clearable
              :placeholder="t('system.skills.selectEmployee')"
              style="width: 280px"
              :remote-method="searchUsers"
              :loading="userSkill.loadingUsers"
              @change="loadUserSkills"
            >
              <el-option v-for="u in userSkill.users" :key="u.id" :label="`${u.full_name || u.username} (#${u.id})`" :value="u.id" />
            </el-select>
            <el-button type="primary" :disabled="!userSkill.user_id" :loading="userSkill.saving" @click="saveUserSkills">{{ t('system.skills.save') }}</el-button>
          </div>

          <el-card shadow="never" class="mt-3">
            <template #header>
              <span class="font-medium">{{ t('system.skills.skillMatrix') }}</span>
            </template>
            <el-checkbox-group v-model="userSkill.skill_ids">
              <el-row :gutter="12">
                <el-col v-for="s in activeSkills" :key="s.id" :span="6" class="mb-2">
                  <el-checkbox :label="s.id">{{ s.name }}</el-checkbox>
                </el-col>
              </el-row>
            </el-checkbox-group>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    <template #extra>
    <el-dialog v-model="skillDlg.open" :title="skillDlg.id ? t('system.skills.editSkill') : t('system.skills.createSkillTitle')" width="520px" destroy-on-close>
      <el-form ref="skillFormRef" :model="skillDlg.form" :rules="skillRules" label-width="90px">
        <el-form-item :label="t('system.skills.code')" prop="code">
          <el-input v-model="skillDlg.form.code" :disabled="!!skillDlg.id" :placeholder="t('system.skills.codePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('system.skills.name')" prop="name">
          <el-input v-model="skillDlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('system.skills.isActive')">
          <el-switch v-model="skillDlg.form.is_active" :active-text="t('system.skills.enabled')" :inactive-text="t('system.skills.disabled')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skillDlg.open = false">{{ t('system.skills.cancel') }}</el-button>
        <el-button type="primary" :loading="skillDlg.saving" @click="saveSkill">{{ t('system.skills.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi } from '@/api/system'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

type SkillRow = { id: number; code: string; name: string; is_active: boolean }
type UserRow = { id: number; username: string; full_name: string | null }

const active = ref<'skills' | 'userSkills'>('skills')

const loadingSkills = ref(false)
const skills = ref<SkillRow[]>([])
const skillQuery = reactive({ keyword: '', include_inactive: false })

const activeSkills = computed(() => skills.value.filter((x) => x.is_active))

const skillDlg = reactive({
  open: false,
  saving: false,
  id: 0 as number | 0,
  form: { code: '', name: '', is_active: true },
})
const skillFormRef = ref<FormInstance>()
const skillRules: FormRules = {
  name: [{ required: true, message: () => t('system.skills.pleaseInputName'), trigger: 'blur' }],
}

const userSkill = reactive({
  user_id: undefined as number | undefined,
  users: [] as UserRow[],
  loadingUsers: false,
  skill_ids: [] as number[],
  saving: false,
})

async function reloadSkills(reset = false) {
  loadingSkills.value = true
  try {
    const res = await systemApi.listSkills({ keyword: skillQuery.keyword || undefined, include_inactive: skillQuery.include_inactive, offset: 0, limit: 500 })
    skills.value = res.items ?? []
    if (reset && userSkill.user_id) await loadUserSkills()
  } finally {
    loadingSkills.value = false
  }
}

async function openCreateSkill() {
  skillDlg.id = 0
  skillDlg.form = { code: await previewNextCode('skill'), name: '', is_active: true }
  skillDlg.open = true
}

function openEditSkill(row: SkillRow) {
  skillDlg.id = row.id
  skillDlg.form = { code: row.code, name: row.name, is_active: row.is_active }
  skillDlg.open = true
}

async function saveSkill() {
  const ok = await skillFormRef.value?.validate().catch(() => false)
  if (!ok) return
  skillDlg.saving = true
  try {
    const payload = { ...skillDlg.form, code: skillDlg.id ? skillDlg.form.code : codeForSubmit(skillDlg.form.code) }
    if (skillDlg.id) await systemApi.updateSkill(skillDlg.id, payload)
    else await systemApi.createSkill(payload)
    skillDlg.open = false
    await reloadSkills(true)
  } finally {
    skillDlg.saving = false
  }
}

async function disableSkill(id: number) {
  await systemApi.disableSkill(id)
  await reloadSkills(true)
}

async function searchUsers(keyword: string) {
  userSkill.loadingUsers = true
  try {
    const res = await systemApi.listSkillUsers({ keyword: keyword || undefined, offset: 0, limit: 50 })
    userSkill.users = res.items ?? []
  } finally {
    userSkill.loadingUsers = false
  }
}

async function loadUserSkills() {
  if (!userSkill.user_id) {
    userSkill.skill_ids = []
    return
  }
  const res = await systemApi.getUserSkills(userSkill.user_id)
  userSkill.skill_ids = res.skill_ids ?? []
}

async function saveUserSkills() {
  if (!userSkill.user_id) return
  userSkill.saving = true
  try {
    const ids = userSkill.skill_ids.map((x) => Number(x)).filter((x) => x > 0)
    await systemApi.setUserSkills(userSkill.user_id, ids)
    ElMessage.success(t('system.skills.saved'))
  } finally {
    userSkill.saving = false
  }
}

onMounted(async () => {
  await reloadSkills(true)
  await searchUsers('')
})
</script>
