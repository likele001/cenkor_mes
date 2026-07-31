/** 深度合并 locale 对象，后者覆盖前者 */
export function deepMerge<T extends Record<string, unknown>>(
  base: T,
  patch: Record<string, unknown>,
): T {
  const out = { ...base } as T
  for (const key of Object.keys(patch)) {
    const b = base[key]
    const p = patch[key]
    if (
      p !== null &&
      typeof p === 'object' &&
      !Array.isArray(p) &&
      b !== null &&
      typeof b === 'object' &&
      !Array.isArray(b)
    ) {
      out[key as keyof T] = deepMerge(
        b as Record<string, unknown>,
        p as Record<string, unknown>,
      ) as T[keyof T]
    } else if (p !== undefined) {
      out[key as keyof T] = p as T[keyof T]
    }
  }
  return out
}
