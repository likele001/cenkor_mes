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
      reject(new Error('无法读取视频时长'))
    }
    v.src = url
  })
}

export async function validateCapturedVideo(
  file: File,
  maxSeconds: number,
  maxMb: number,
): Promise<string | null> {
  const maxBytes = maxMb * 1024 * 1024
  if (file.size > maxBytes) return `视频超过 ${maxMb}MB，请缩短拍摄`
  if (file.size < 1024) return '视频过短，请重新拍摄'
  try {
    const d = await getVideoDuration(file)
    if (d > maxSeconds + 1.5) {
      return `视频时长 ${Math.ceil(d)} 秒，超过限制的 ${maxSeconds} 秒，请重拍短片段`
    }
  } catch {
    /* ignore */
  }
  return null
}

export function pickVideoFromSystemCamera(): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'video/*'
    input.setAttribute('capture', 'camcorder')
    input.onchange = () => resolve(input.files?.[0] ?? null)
    input.click()
  })
}
