// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchLoginCaptcha } from '@/api/captcha'
import { fetchPublicConfig } from '@/api/public'

export function useLoginCaptcha() {
  const enabled = ref(false)
  const loading = ref(false)
  const loadError = ref('')
  const state = reactive({
    captcha_id: '',
    captcha_code: '',
    image_base64: '',
  })

  function clear() {
    state.image_base64 = ''
    state.captcha_id = ''
    state.captcha_code = ''
  }

  async function refresh() {
    if (!enabled.value) return
    loading.value = true
    loadError.value = ''
    try {
      const res = await fetchLoginCaptcha()
      if (!res.enabled) {
        enabled.value = false
        clear()
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
      // 接口挂掉时隐藏整个组件，不留「空图片框 + 502 红字」误导用户
      enabled.value = false
      clear()
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  async function init() {
    try {
      const cfg = await fetchPublicConfig()
      enabled.value = Boolean(cfg.login_captcha_enabled)
    } catch {
      // public-config 都拿不到说明服务不可用，静默隐藏，不把错误渲染成验证码故障
      enabled.value = false
    }
    if (enabled.value) await refresh()
  }

  function payloadFields() {
    if (!enabled.value) return {}
    return { captcha_id: state.captcha_id, captcha_code: state.captcha_code.trim() }
  }

  onMounted(() => {
    void init()
  })

  return { enabled, loading, loadError, state, refresh, init, payloadFields }
}
