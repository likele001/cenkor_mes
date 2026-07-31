/**
 * 语音输入工具 — 基于 Web Speech API（webkitSpeechRecognition）
 *
 * 兼容性：
 *   - iOS Safari 14.5+ / macOS Safari 14.1+：原生支持 `webkitSpeechRecognition`
 *   - Android Chrome / Edge / Samsung：原生支持
 *   - 微信内置浏览器（X5）：部分机型支持
 *   - 桌面 Firefox：不支持，会回退到手动输入提示
 *
 * 使用：
 *   const input = new VoiceInput({ lang: 'zh-CN' })
 *   input.onResult = (text, isFinal) => { ... }
 *   input.start()
 *   input.stop()
 */

export type VoiceInputOptions = {
  lang?: string // BCP-47 语言标签，默认 'zh-CN'
  interim?: boolean // 是否输出临时识别结果，默认 true
  continuous?: boolean // 是否连续识别，默认 false（短句模式）
  maxAlternatives?: number // 最大候选数，默认 1
}

export type VoiceInputCallbacks = {
  onResult?: (text: string, isFinal: boolean) => void
  onError?: (code: string, message: string) => void
  onStart?: () => void
  onEnd?: () => void
}

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((e: any) => void) | null
  onerror: ((e: any) => void) | null
  onend: ((e: any) => void) | null
  onstart: ((e: any) => void) | null
}

function getSRClass(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

/** 当前环境是否支持 Web Speech API（语音识别） */
export function isVoiceInputSupported(): boolean {
  return getSRClass() !== null
}

export class VoiceInput {
  private rec: SpeechRecognitionLike | null = null
  private opts: Required<VoiceInputOptions>
  private cbs: VoiceInputCallbacks = {}
  private running = false

  constructor(opts: VoiceInputOptions = {}) {
    this.opts = {
      lang: opts.lang ?? 'zh-CN',
      interim: opts.interim ?? true,
      continuous: opts.continuous ?? false,
      maxAlternatives: opts.maxAlternatives ?? 1,
    }
  }

  on(event: keyof VoiceInputCallbacks, cb: VoiceInputCallbacks[keyof VoiceInputCallbacks]): void {
    // 简化：只支持单一回调；多次 on() 会覆盖上一个
    (this.cbs as Record<string, unknown>)[event] = cb
  }

  isRunning(): boolean {
    return this.running
  }

  start(): boolean {
    if (this.running) return true
    const SR = getSRClass()
    if (!SR) {
      this.cbs.onError?.('not-supported', '当前浏览器不支持语音识别，请改用键盘输入或系统输入法')
      return false
    }
    try {
      const rec = new SR()
      rec.lang = this.opts.lang
      rec.interimResults = this.opts.interim
      rec.continuous = this.opts.continuous
      rec.maxAlternatives = this.opts.maxAlternatives
      rec.onstart = () => {
        this.running = true
        this.cbs.onStart?.()
      }
      rec.onerror = (e: any) => {
        const code = String(e?.error || 'unknown')
        const messages: Record<string, string> = {
          'not-allowed': '麦克风权限被拒绝，请在浏览器设置中开启',
          'no-speech': '未检测到语音，请重试',
          'audio-capture': '没有可用的麦克风设备',
          network: '网络异常，语音识别依赖联网',
          aborted: '已取消',
          'service-not-allowed': '浏览器禁止语音识别服务',
        }
        this.cbs.onError?.(code, messages[code] || `语音识别错误: ${code}`)
      }
      rec.onresult = (e: any) => {
        let finalText = ''
        let interimText = ''
        for (let i = 0; i < (e.results?.length ?? 0); i++) {
          const r = e.results[i]
          const text = String(r?.[0]?.transcript ?? '')
          if (r?.isFinal) finalText += text
          else interimText += text
        }
        const text = (finalText + interimText).trim()
        if (text) this.cbs.onResult?.(text, Boolean(finalText))
      }
      rec.onend = () => {
        this.running = false
        this.cbs.onEnd?.()
      }
      rec.start()
      this.rec = rec
      return true
    } catch (e: unknown) {
      this.cbs.onError?.('start-failed', e instanceof Error ? e.message : '启动语音识别失败')
      return false
    }
  }

  stop(): void {
    if (!this.rec || !this.running) return
    try {
      this.rec.stop()
    } catch {
      /* ignore */
    }
  }

  abort(): void {
    if (!this.rec) return
    try {
      this.rec.abort()
    } catch {
      /* ignore */
    }
    this.running = false
  }

  destroy(): void {
    this.abort()
    if (this.rec) {
      this.rec.onresult = null
      this.rec.onerror = null
      this.rec.onend = null
      this.rec.onstart = null
    }
    this.rec = null
    this.cbs = {}
  }
}

/** 一次性识别（封装为 Promise），返回最终识别文本。失败/不支持抛错。 */
export function recognizeOnce(opts: VoiceInputOptions = {}, timeoutMs = 15_000): Promise<string> {
  return new Promise((resolve, reject) => {
    const vi = new VoiceInput({ ...opts, continuous: false })
    let resolved = false
    const timer = window.setTimeout(() => {
      if (!resolved) {
        resolved = true
        vi.destroy()
        reject(new Error('语音识别超时'))
      }
    }, timeoutMs)
    vi.on('onResult', (text, isFinal) => {
      if (isFinal && !resolved) {
        resolved = true
        window.clearTimeout(timer)
        const finalText = String(text || '').trim()
        vi.destroy()
        if (finalText) resolve(finalText)
        else reject(new Error('未识别到内容'))
      }
    })
    vi.on('onError', (code, msg) => {
      if (!resolved) {
        resolved = true
        window.clearTimeout(timer)
        vi.destroy()
        reject(new Error(msg || String(code)))
      }
    })
    vi.on('onEnd', () => {
      if (!resolved) {
        resolved = true
        window.clearTimeout(timer)
        vi.destroy()
        reject(new Error('语音识别已结束'))
      }
    })
    if (!vi.start()) {
      window.clearTimeout(timer)
      reject(new Error('当前浏览器不支持语音识别'))
    }
  })
}