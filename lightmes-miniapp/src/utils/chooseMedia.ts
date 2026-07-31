/**
 * 微信小程序媒体选择工具
 *
 * 核心修复：微信环境下优先使用 uni.chooseImage/uni.chooseMedia，
 * uni-app 会自动处理隐私授权流程（onNeedPrivacyAuthorization），
 * 不需要手动在 App.vue 中处理 resolve/reject。
 */

export type ChooseMediaFile = {
  tempFilePath: string
  size: number
  fileType?: 'image' | 'video'
  thumbTempFilePath?: string
  duration?: number
}

export type ChooseMediaOptions = {
  count?: number
  mediaType?: Array<'image' | 'video'>
  sourceType?: Array<'album' | 'camera'>
  maxDuration?: number
  sizeType?: Array<'original' | 'compressed'>
}

export async function chooseMediaCompat(options: ChooseMediaOptions = {}): Promise<{ tempFiles: ChooseMediaFile[] }> {
  const {
    count = 9,
    mediaType = ['image'],
    sourceType = ['album', 'camera'],
    maxDuration = 30,
    sizeType = ['compressed'],
  } = options

  const safeCount = Math.max(1, Math.min(9, count))

  // #ifdef MP-WEIXIN
  // 微信小程序：使用 uni API，自动处理隐私授权
  console.log('[chooseMedia] uni.chooseMedia (uni-app handles privacy), count:', safeCount, 'mediaType:', mediaType)

  // 如果有视频，优先用 chooseMedia（支持图片+视频）
  if (mediaType.includes('video')) {
    const res: any = await new Promise((resolve, reject) => {
      uni.chooseMedia({
        count: safeCount,
        mediaType: mediaType as any,
        sourceType: sourceType as any,
        maxDuration,
        sizeType: sizeType as any,
        success: (r: any) => resolve(r),
        fail: (e: any) => reject(e),
      })
    })
    const files: ChooseMediaFile[] = (res.tempFiles || []).map((f: any) => ({
      tempFilePath: f.tempFilePath,
      size: f.size || 0,
      fileType: f.fileType,
      thumbTempFilePath: f.thumbTempFilePath,
      duration: f.duration,
    }))
    console.log('[chooseMedia] uni.chooseMedia success, files:', files.length)
    return { tempFiles: files }
  } else {
    // 纯图片：使用 chooseImage
    const res: any = await new Promise((resolve, reject) => {
      uni.chooseImage({
        count: safeCount,
        sizeType: sizeType as any,
        sourceType: sourceType as any,
        success: (r: any) => resolve(r),
        fail: (e: any) => reject(e),
      })
    })
    const files: ChooseMediaFile[] = (res.tempFilePaths || []).map((path: string, idx: number) => ({
      tempFilePath: path,
      size: res.tempFiles?.[idx]?.size || 0,
      fileType: 'image' as const,
    }))
    console.log('[chooseMedia] uni.chooseImage success, files:', files.length)
    return { tempFiles: files }
  }
  // #endif

  // #ifndef MP-WEIXIN
  // 其他平台（H5、App 等）
  const res: any = await new Promise((resolve, reject) => {
    uni.chooseImage({
      count: safeCount,
      sizeType: sizeType as any,
      sourceType: sourceType as any,
      success: (r: any) => resolve(r),
      fail: (e: any) => reject(e),
    })
  })
  const files: ChooseMediaFile[] = (res.tempFilePaths || []).map((path: string, idx: number) => ({
    tempFilePath: path,
    size: res.tempFiles?.[idx]?.size || 0,
    fileType: 'image' as const,
  }))
  return { tempFiles: files }
  // #endif
}
