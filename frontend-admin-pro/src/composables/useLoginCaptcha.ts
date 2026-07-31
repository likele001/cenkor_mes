import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchLoginCaptcha } from '@/api/captcha'

export function useLoginCaptcha() {
  const enabled = ref(false)
  const loading = ref(false)
  const loadError = ref('')
  const state = reactive({
    captcha_id: '',
    captcha_code: '',
    image_base64: '',
  })

  async function refresh() {
    if (!enabled.value) return
    loading.value = true
    loadError.value = ''
    try {
      const res = await fetchLoginCaptcha()
      if (!res.enabled) {
        enabled.value = false
        state.image_base64 = ''
        state.captcha_id = ''
        return
      }
      if (!res.image_base64 || !res.captcha_id) {
        loadError.value = '验证码图片未返回，请点右侧区域重试'
        return
      }
      state.captcha_id = res.captcha_id
      state.image_base64 = res.image_base64
      state.captcha_code = ''
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '验证码加载失败'
      loadError.value = msg
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  onMounted(async () => {
    enabled.value = true
    await refresh()
  })

  function payloadFields() {
    if (!enabled.value) return {}
    return { captcha_id: state.captcha_id, captcha_code: state.captcha_code.trim() }
  }

  return { enabled, loading, loadError, state, refresh, init: refresh, payloadFields }
}
