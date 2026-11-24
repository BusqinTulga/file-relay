export type FileSizeUnit = 'MB' | 'GB'
export class InvalidFileSizeError extends Error {}
const powers = { MB: 6, GB: 9 }
export function bytesToFileSizeForm(
  bytes: number,
  unit: FileSizeUnit = bytes >= 1e9 ? 'GB' : 'MB'
): { value: number; unit: FileSizeUnit } {
  return { value: bytes / 10 ** powers[unit], unit }
}
export function fileSizeFormToBytes(value: number, unit: FileSizeUnit): number {
  // Work with decimal digits so untouched legacy byte values survive a round trip.
  const match = String(value).match(/^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i)
  const fail = () => {
    throw new InvalidFileSizeError()
  }
  if (!match) return fail()
  const fraction = match[2] || ''
  const exponent = Number(match[3] || 0) + powers[unit] - fraction.length
  if (Math.abs(exponent) > 30) return fail()
  let bytes = BigInt(match[1] + fraction)
  if (exponent < 0) {
    const divisor = 10n ** BigInt(-exponent)
    if (bytes % divisor !== 0n) return fail()
    bytes /= divisor
  } else bytes *= 10n ** BigInt(exponent)
  if (bytes <= 0n || bytes > BigInt(Number.MAX_SAFE_INTEGER)) return fail()
  return Number(bytes)
}
