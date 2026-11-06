import type { ApiErrorPayload, ApiResponse } from '@/types'
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const index = Math.max(0, Math.min(4, Math.floor(Math.log(bytes) / Math.log(1000))))
  return `${Number((bytes / 1000 ** index).toFixed(2))} ${['B', 'KB', 'MB', 'GB', 'TB'][index]}`
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
