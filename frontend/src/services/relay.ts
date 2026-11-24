import i18n, { getCurrentLocale } from '@/i18n'
export interface RelayPolicy {
  upload_size: number
  storage_limit: number
  open_upload: number
}
// Deliberately independent of the administrator's Bearer client and 401 events.
export interface RelaySession {
  paired: boolean
  csrf: string
  passcode?: string
  device_id?: string
  session_id?: string
  pending?: RelayPending
}
export interface RelayPending {
  request_id: string
  status: string
  expires: number
}
export interface RelayFile {
  id: number
  name: string
  size: number
  sha256: string
  published: number
  expires: number
  first_sent: number | null
}
export interface RelayUpload {
  id: string
  state: string
  chunk_size: number
  chunks: number[]
  file?: RelayFile
}
export class RelayError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
  }
}
export const RelayService = {
  async policy(): Promise<RelayPolicy> {
    const response = await fetch('/api/v1/config', {
      cache: 'no-store',
      headers: { 'Accept-Language': getCurrentLocale() },
      credentials: 'same-origin'
    })
    if (!response.ok) throw new RelayError(response.status, i18n.global.t('relay.policyFailed'))
    const data = (await response.json()).detail?.config
    if (
      !data ||
      !Number.isSafeInteger(data.upload_size) ||
      data.upload_size <= 0 ||
      ![0, 1].includes(data.open_upload)
    )
      throw new Error(i18n.global.t('relay.invalidPolicy'))
    return data
  },
  async request<T>(
    path: string,
    method = 'GET',
    body?: unknown,
    signal?: AbortSignal,
    auth?: RelaySession
  ): Promise<T> {
    const response = await fetch('/api/relay' + path, {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
      headers: {
        'Accept-Language': getCurrentLocale(),
        'Content-Type': 'application/json',
        'X-Relay-CSRF': auth?.csrf ?? '',
        'X-Relay-Session': auth?.session_id ?? ''
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    })
    if (!response.ok) {
      const data = await response.json().catch(() => null)
      throw new RelayError(
        response.status,
        typeof data?.detail === 'string' ? data.detail : i18n.global.t('relay.httpError', { status: response.status })
      )
    }
    return (await response.json()) as T
  },
  async session(): Promise<RelaySession> {
    return this.request<RelaySession>('/session')
  },
  async pair(passcode: string, auth: RelaySession) {
    return this.request<RelaySession | RelayPending>('/pair', 'POST', { passcode }, undefined, auth)
  },
  async pending(auth: RelaySession) {
    return this.request<RelaySession | { status: string }>('/pairing/status', 'POST', undefined, undefined, auth)
  },
  async list(auth: RelaySession) {
    return this.request<{ session_id: string; files: RelayFile[] }>('/files', 'GET', undefined, undefined, auth)
  },
  async approvals(auth: RelaySession) {
    return this.request<{ id: string; expires: number }[]>('/pairing/requests', 'GET', undefined, undefined, auth)
  },
  async decide(id: string, approve: boolean, auth: RelaySession) {
    return this.request('/pairing/requests/' + id, 'POST', { approve }, undefined, auth)
  },
  async remove(id: number, auth: RelaySession) {
    return this.request('/files/' + id, 'DELETE', undefined, undefined, auth)
  },
  async start(name: string, size: number, sha256: string, signal: AbortSignal, auth: RelaySession) {
    return this.request<RelayUpload>(
      '/uploads',
      'POST',
      { name, size, sha256, chunked: size > 4 * 1024 * 1024 },
      signal,
      auth
    )
  },
  async complete(id: string, signal: AbortSignal, auth: RelaySession) {
    return this.request<RelayUpload>(
      '/uploads/' + id + '/complete',
      'POST',
      undefined,
      signal,
      auth
    )
  },
  async cancel(id: string, auth: RelaySession) {
    return this.request('/uploads/' + id, 'DELETE', undefined, undefined, auth)
  },
  put(
    id: string,
    index: number,
    data: Blob,
    hash: string,
    signal: AbortSignal,
    progress: (value: number) => void,
    auth: RelaySession,
    ordinary = false
  ) {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const abort = () => xhr.abort()
      if (signal.aborted) {
        reject(new DOMException(i18n.global.t('relay.cancelled'), 'AbortError'))
        return
      }
      xhr.open(
        'PUT',
        ordinary ? `/api/relay/uploads/${id}/content` : `/api/relay/uploads/${id}/chunks/${index}`
      )
      xhr.setRequestHeader('X-Relay-CSRF', auth.csrf)
      xhr.setRequestHeader('Accept-Language', getCurrentLocale())
      xhr.setRequestHeader('X-Relay-Session', auth.session_id || '')
      xhr.setRequestHeader('X-Chunk-SHA256', hash)
      xhr.setRequestHeader('Content-Type', 'application/octet-stream')
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) progress(e.loaded / e.total)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve()
        else {
          let message = i18n.global.t('relay.uploadFailed')
          try {
            const data = JSON.parse(xhr.responseText)
            if (typeof data.detail === 'string') message = data.detail
          } catch {
            /* network/proxy response */
          }
          reject(new RelayError(xhr.status, message))
        }
      }
      xhr.onerror = () => reject(new Error(i18n.global.t('relay.networkError')))
      xhr.onabort = () => reject(new DOMException(i18n.global.t('relay.cancelled'), 'AbortError'))
      xhr.onloadend = () => signal.removeEventListener('abort', abort)
      signal.addEventListener('abort', abort, { once: true })
      xhr.send(data)
    })
  }
}
