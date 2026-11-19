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
      credentials: 'same-origin'
    })
    if (!response.ok) throw new RelayError(response.status, '无法读取上传限制，请重试')
    const data = (await response.json()).detail?.config
    if (
      !data ||
      !Number.isSafeInteger(data.upload_size) ||
      data.upload_size <= 0 ||
      ![0, 1].includes(data.open_upload)
    )
      throw new Error('上传配置无效，请重试')
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
        typeof data?.detail === 'string' ? data.detail : `请求失败（HTTP ${response.status}），请重试`
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
        reject(new DOMException('已取消', 'AbortError'))
        return
      }
      xhr.open(
        'PUT',
        ordinary ? `/api/relay/uploads/${id}/content` : `/api/relay/uploads/${id}/chunks/${index}`
      )
      xhr.setRequestHeader('X-Relay-CSRF', auth.csrf)
      xhr.setRequestHeader('X-Relay-Session', auth.session_id || '')
      xhr.setRequestHeader('X-Chunk-SHA256', hash)
      xhr.setRequestHeader('Content-Type', 'application/octet-stream')
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) progress(e.loaded / e.total)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve()
        else {
          let message = '上传失败，请重试'
          try {
            const data = JSON.parse(xhr.responseText)
            if (typeof data.detail === 'string') message = data.detail
          } catch {
            /* network/proxy response */
          }
          reject(new RelayError(xhr.status, message))
        }
      }
      xhr.onerror = () => reject(new Error('网络中断，请重试'))
      xhr.onabort = () => reject(new DOMException('已取消', 'AbortError'))
      xhr.onloadend = () => signal.removeEventListener('abort', abort)
      signal.addEventListener('abort', abort, { once: true })
      xhr.send(data)
    })
  }
}
