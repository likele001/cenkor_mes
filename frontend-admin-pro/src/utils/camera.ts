import { i18n } from '@/locales'

/** 摄像头 / 现场录像（兼容 HTTP、Edge 手机、无 MediaRecorder 环境） */

export function isSecureCameraContext(): boolean {
  if (typeof window === 'undefined') return false
  return Boolean(window.isSecureContext)
}

export function getUserMediaFn(): ((c: MediaStreamConstraints) => Promise<MediaStream>) | null {
  if (typeof navigator === 'undefined') return null
  if (navigator.mediaDevices?.getUserMedia) {
    return (c) => navigator.mediaDevices.getUserMedia(c)
  }
  const nav = navigator as Navigator & {
    getUserMedia?: typeof navigator.mediaDevices.getUserMedia
    webkitGetUserMedia?: typeof navigator.mediaDevices.getUserMedia
  }
  const legacy = nav.getUserMedia || nav.webkitGetUserMedia
  if (legacy) {
    return (c) =>
      new Promise((resolve, reject) => {
        legacy.call(navigator, c, resolve, reject)
      })
  }
  return null
}

export function pickRecorderMime(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  for (const t of ['video/webm;codecs=vp8', 'video/webm', 'video/mp4']) {
    if (MediaRecorder.isTypeSupported(t)) return t
  }
  return ''
}

export function canUseInPageRecorder(): boolean {
  return isSecureCameraContext() && !!getUserMediaFn() && !!pickRecorderMime()
}

export function getVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video')
    v.preload = 'metadata'
    v.playsInline = true
    const url = URL.createObjectURL(file)
    v.onloadedmetadata = () => {
      const d = Number(v.duration)
      URL.revokeObjectURL(url)
      resolve(Number.isFinite(d) ? d : 0)
    }
    v.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error(i18n.global.t('utils.camera.cannotReadDuration')))
    }
    v.src = url
  })
}

/** 校验拍摄结果；通过返回 null，否则返回错误文案 */
export async function validateCapturedVideo(
  file: File,
  maxSeconds: number,
  maxMb: number,
): Promise<string | null> {
  const maxBytes = maxMb * 1024 * 1024
  if (file.size > maxBytes) {
    return i18n.global.t('utils.camera.videoTooLarge', { maxMb })
  }
  if (file.size < 1024) return i18n.global.t('utils.camera.videoTooShort')
  try {
    const d = await getVideoDuration(file)
    if (d > maxSeconds + 1.5) {
      return i18n.global.t('utils.camera.videoExceedsLimit', { duration: Math.ceil(d), maxSeconds })
    }
  } catch {
    /* 部分机型读不出时长，仅按大小限制 */
  }
  return null
}

/** 调起系统相机录像（HTTP / Edge 等无 getUserMedia 时可用） */
export function pickVideoFromSystemCamera(): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'video/*'
    input.setAttribute('capture', 'camcorder')
    input.onchange = () => {
      resolve(input.files?.[0] ?? null)
    }
    input.click()
  })
}
