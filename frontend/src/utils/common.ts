import type { ApiErrorPayload, ApiResponse } from '@/types'
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB'
  const units = ['MB', 'GB', 'TB', 'PB']
  let value = bytes / 1_000_000
  let index = 0
  const precision = bytes < 1_000_000 ? 6 : 2
  while (index < units.length - 1 && Number(value.toFixed(precision)) >= 1000) {
    value /= 1000
    index += 1
  }
  return `${Number(value.toFixed(precision))} ${units[index]}`
}

export function formatSizeLimit(bytes: number): string {
  const decimals = bytes >= 1_000_000_000 ? 9 : 6
  const value = Number((bytes / 10 ** decimals).toFixed(decimals))
  return `${value} ${decimals === 9 ? 'GB' : 'MB'}`
}

type ErrorWithResponse = {
  response?: {
    data?: ApiErrorPayload
  }
  message?: string
}

const getReadableMessage = (value: unknown): string => {
  if (typeof value === 'string') {
    return value
  }

  if (!value || typeof value !== 'object') {
    return ''
  }

  const payload = value as Record<string, unknown>
  for (const key of ['message', 'msg', 'detail', 'error']) {
    const fieldValue = payload[key]
    if (typeof fieldValue === 'string' && fieldValue.trim()) {
      return fieldValue
    }
  }

  return ''
}

export function getResponseMessage(response: ApiResponse, fallback: string): string {
  return getReadableMessage(response.detail) || getReadableMessage(response.message) || fallback
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (!error || typeof error !== 'object') {
    return fallback
  }

  const errorWithResponse = error as ErrorWithResponse
  const responseData = errorWithResponse.response?.data
  return (
    getReadableMessage(responseData?.detail) ||
    getReadableMessage(responseData?.message) ||
    errorWithResponse.message ||
    fallback
  )
}
