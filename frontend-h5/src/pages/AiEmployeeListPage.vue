<template>
  <div class="min-h-screen bg-gray-50">
    <van-nav-bar :title="t('aiEmployee.title')" left-arrow @click-left="$router.back()" />
    <div class="p-4">
      <van-loading v-if="loading" class="flex justify-center mt-20" />
      <van-empty v-else-if="!employees.length" :description="t('aiEmployee.empty')" />
      <div v-else class="grid grid-cols-2 gap-3">
        <div
          v-for="emp in employees"
          :key="emp.id"
          class="bg-white rounded-xl p-4 shadow-sm cursor-pointer active:bg-gray-50"
          @click="goChat(emp.id)"
        >
          <div class="flex flex-col items-center">
            <van-image
              v-if="emp.avatar_url"
              :src="emp.avatar_url"
              round
              width="56"
              height="56"
              class="mb-2"
            />
            <div v-else class="w-14 h-14 rounded-full bg-blue-500 flex items-center justify-center text-white text-xl mb-2">
              {{ emp.name.charAt(0) }}
            </div>
            <div class="font-medium text-sm text-gray-800 text-center">{{ emp.name }}</div>
            <div class="text-xs text-gray-500 mt-1 text-center line-clamp-2">{{ emp.role_desc }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listAiEmployees, type AiEmployeeItem } from '@/api/aiEmployee'

const { t } = useI18n()
const router = useRouter()
const loading = ref(true)
const employees = ref<AiEmployeeItem[]>([])

onMounted(async () => {
  try {
    const res = await listAiEmployees()
    employees.value = (res as any)?.items || res || []
  } catch {
    employees.value = []
  } finally {
    loading.value = false
  }
})

function goChat(id: number) {
  router.push({ name: 'aiEmployeeChat', params: { id: String(id) } })
}
</script>
