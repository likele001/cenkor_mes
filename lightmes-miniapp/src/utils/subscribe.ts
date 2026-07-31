import { apiGet } from '@/api/request'

export type WechatTemplate = {
  event_code: string
  template_id: string
  title?: string
  content?: string
  keywords?: string[]
}

type SubscribeResult = {
  accepted: string[]
  rejected: string[]
}

const SUBSCRIBED_KEY = 'cenkormes_subscribed_events'
const DISMISS_KEY = 'cenkormes_subscribe_dismissed'

function getSubscribedSet(): Set<string> {
  try {
    return new Set<string>(JSON.parse(uni.getStorageSync(SUBSCRIBED_KEY) || '[]'))
  } catch {
    return new Set()
  }
}

function markSubscribed(eventCodes: string[]) {
  const s = getSubscribedSet()
  eventCodes.forEach((c) => s.add(c))
  uni.setStorageSync(SUBSCRIBED_KEY, JSON.stringify(Array.from(s)))
}

export async function listAvailableTemplates(): Promise<WechatTemplate[]> {
  try {
    const r = await apiGet<{ items: WechatTemplate[] }>('/miniapp/wechat-mp/templates')
    return r?.items || []
  } catch {
    return []
  }
}

export async function requestSubscribe(
  tmplIds: string[],
  opts?: { showToast?: boolean; recordOnServer?: boolean },
): Promise<SubscribeResult> {
  const result: SubscribeResult = { accepted: [], rejected: [] }
  try {
    const tmplId = tmplIds[0]
    const { errMsg } = await uni.requestSubscribeMessage({ tmplIds: [tmplId] })
    if (errMsg?.includes('ok') || errMsg?.includes('accept')) {
      result.accepted.push(tmplId)
    } else {
      result.rejected.push(tmplId)
    }
    if (opts?.showToast !== false) {
      if (result.accepted.length > 0) {
        uni.showToast({ title: '订阅成功', icon: 'success' })
      } else {
        uni.showToast({ title: '已拒绝订阅', icon: 'none' })
      }
    }
    if (opts?.recordOnServer !== false) {
      const eventCode = tmplIds[0]
      if (eventCode) {
        markSubscribed([eventCode])
      }
    }
  } catch {
    uni.showToast({ title: '订阅失败', icon: 'none' })
  }
  return result
}

const SMART_SUB_PREFIX = 'cenkormes_smart_sub_'

export async function smartAutoSubscribe(contextId: string, eventCodes: string[]) {
  const key = SMART_SUB_PREFIX + contextId
  if (uni.getStorageSync(key)) return
  try {
    const templates = await listAvailableTemplates()
    const wanted = templates.filter(
      (t) => eventCodes.includes(t.event_code) && t.template_id && !t.template_id.startsWith('tpl_'),
    )
    if (wanted.length === 0) return
    const alreadySubscribed = getSubscribedSet()
    const needSub = wanted.filter((t) => !alreadySubscribed.has(t.event_code))
    if (needSub.length === 0) {
      uni.setStorageSync(key, '1')
      return
    }
    for (const tpl of needSub) {
      await requestSubscribe([tpl.template_id], { showToast: true, recordOnServer: true })
    }
    uni.setStorageSync(key, '1')
  } catch {
    /* silent */
  }
}
