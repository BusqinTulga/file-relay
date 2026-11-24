import { onMounted, onUnmounted, ref } from 'vue'
import { RelayService, RelayError } from '@/services'
import type { RelayFile, RelaySession, RelayPending, RelayPolicy } from '@/services'
import { hashRelayFile } from '@/utils/relay-sha256'
import { formatSizeLimit } from '@/utils/common'

interface QueueItem {
  key: number
  file: File
  progress: number
  state: string
  error: string
  generation: number
  uploadID?: string
  controller?: AbortController
  cancelling?: boolean
}
export function useRelay() {
  const mode = ref<'loading' | 'pair' | 'waiting' | 'relay'>('loading')
  const session = ref<RelaySession | null>(null)
  const passcode = ref('')
  const files = ref<RelayFile[]>([])
  const requests = ref<{ id: string; expires: number }[]>([])
  const pendingRequest = ref<RelayPending | null>(null)
  const queue = ref<QueueItem[]>([])
  const error = ref('')
  const policy = ref<RelayPolicy | null>(null)
  const busy = ref(false)
  const queueRunning = ref(false)
  let generation = 0,
    serial = 0,
    stopped = false,
    polling = false,
    failures = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const stopQueue = () => {
    for (const item of queue.value) {
      if (['等待上传', '校验文件', '上传中', '发布中'].includes(item.state)) {
        item.controller?.abort()
        item.state = '已取消'
        item.error = '配对发生变化，请在当前列表重新选择文件'
      }
    }
  }
  const resetContext = () => {
    generation++
    stopQueue()
    files.value = []
    requests.value = []
    pendingRequest.value = null
  }
  const handleError = (e: unknown) => {
    error.value = e instanceof Error ? e.message : '请求失败，请重试'
  }
  async function sync(restorePending = true) {
    if (stopped || polling || busy.value || document.hidden || mode.value === 'pair') return
    polling = true
    let epoch = generation
    try {
      const current = await RelayService.session()
      if (epoch !== generation) return
      if (mode.value === 'waiting' || (mode.value === 'loading' && restorePending && current.pending)) {
        if (current.pending) pendingRequest.value = current.pending
        mode.value = 'waiting'
        if (!current.pending && current.session_id !== session.value?.session_id) {
          resetContext()
          session.value = current
          mode.value = current.paired ? 'relay' : 'pair'
          failures = 0
          return
        }
        session.value = current
        const pending = await RelayService.pending(current)
        if (epoch !== generation) return
        if ('csrf' in pending) {
          resetContext()
          session.value = pending
          mode.value = 'relay'
          error.value = ''
        } else if (pending.status !== 'pending' && pending.status !== 'approved') {
          pendingRequest.value = null
          error.value =
            pending.status === 'rejected'
              ? '加入申请已被拒绝，可重新输入口令'
              : '加入申请已过期，请重新申请'
          mode.value = 'pair'
        }
        failures = 0
        return
      }
      if (!current.paired) {
        resetContext()
        session.value = current
        mode.value = 'pair'
        failures = 0
        return
      }
      if (session.value?.session_id !== current.session_id) {
        resetContext()
        epoch = generation
      }
      session.value = current
      mode.value = 'relay'
      const [listing, pending, limits] = await Promise.all([
        RelayService.list(current),
        RelayService.approvals(current),
        RelayService.policy().catch(() => null)
      ])
      if (epoch !== generation || listing.session_id !== current.session_id) return
      policy.value = limits
      files.value = listing.files
      requests.value = pending
      if (failures) error.value = ''
      failures = 0
    } catch (e) {
      if (epoch !== generation) return
      failures++
      handleError(e)
    } finally {
      polling = false
    }
  }
  function schedule(elapsed = 0) {
    if (stopped) return
    clearTimeout(timer)
    timer = setTimeout(
      async () => {
        const started = Date.now()
        await sync()
        schedule(Date.now() - started)
      },
      Math.max(0, Math.min(30000, 2000 * 2 ** Math.min(failures, 4)) - elapsed)
    )
  }
  const wake = () => {
    clearTimeout(timer)
    if (!document.hidden) {
      void sync()
      schedule()
    }
  }
  async function initialize(restorePending = true) {
    await sync(restorePending)
    schedule()
  }
  async function pair() {
    if (busy.value) return
    if (!/^[0-9]{1,4}$/.test(passcode.value)) {
      error.value = '请输入 1 至 4 位数字，保留前导零'
      return
    }
    busy.value = true
    error.value = ''
    resetContext()
    const epoch = generation
    try {
      // Bootstrap again in case another tab replaced the cookie.
      const current = await RelayService.session()
      if (epoch !== generation) return
      const result = await RelayService.pair(passcode.value, current)
      if (epoch !== generation) return
      if ('csrf' in result) {
        session.value = result
        mode.value = 'relay'
      } else {
        session.value = current
        pendingRequest.value = result
        mode.value = 'waiting'
      }
    } catch (e) {
      if (epoch === generation) handleError(e)
    } finally {
      busy.value = false
    }
    if (epoch === generation) await sync()
  }
  function repair() {
    resetContext()
    passcode.value = ''
    error.value = ''
    mode.value = 'pair'
  }
  async function resume() {
    if (busy.value) return
    mode.value = 'loading'
    await initialize(false)
  }
  async function decide(id: string, approve: boolean) {
    const auth = session.value
    if (!auth?.paired) return
    const epoch = generation
    try {
      await RelayService.decide(id, approve, auth)
      await sync()
    } catch (e) {
      if (epoch === generation) handleError(e)
    }
  }
  async function remove(id: number) {
    const auth = session.value
    if (!auth?.paired) return
    const epoch = generation
    try {
      await RelayService.remove(id, auth)
      await sync()
    } catch (e) {
      if (epoch === generation) handleError(e)
    }
  }
  async function runQueue() {
    if (queueRunning.value) return
    queueRunning.value = true
    try {
      while (mode.value === 'relay') {
        const item = queue.value.find((q) => q.state === '等待上传')
        if (!item) break
        const epoch = generation
        const auth = session.value
        if (!auth?.paired) break
        const controller = new AbortController()
        item.controller = controller
        const check = () => {
          controller.signal.throwIfAborted()
          if (epoch !== generation) throw new DOMException('配对已改变', 'AbortError')
        }
        try {
          policy.value = null
          policy.value = await RelayService.policy()
          check()
          if (!policy.value.open_upload) throw new Error('上传已暂停，请稍后重试')
          if (item.file.size > policy.value.upload_size)
            throw new Error(
              `文件大小超过单文件上限（${formatSizeLimit(policy.value.upload_size)}）`
            )
          item.state = '校验文件'
          item.error = ''
          const sha = await hashRelayFile(item.file, controller.signal, (p) => {
            item.progress = Math.round(p * 20)
          })
          check()
          const upload = await RelayService.start(
            item.file.name,
            item.file.size,
            sha,
            controller.signal,
            auth
          )
          item.uploadID = upload.id
          check()
          item.state = '上传中'
          const count = Math.max(1, Math.ceil(item.file.size / upload.chunk_size))
          for (let index = 0; index < count && upload.state === 'uploading'; index++) {
            check()
            if (upload.chunks.includes(index)) {
              item.progress = 20 + Math.round(((index + 1) / count) * 75)
              continue
            }
            const block = item.file.slice(
              index * upload.chunk_size,
              (index + 1) * upload.chunk_size
            )
            const hash = await hashRelayFile(block, controller.signal)
            check()
            await RelayService.put(
              upload.id,
              index,
              block,
              hash,
              controller.signal,
              (p) => {
                item.progress = 20 + Math.round(((index + p) / count) * 75)
              },
              auth,
              item.file.size <= 4 * 1024 * 1024
            )
          }
          check()
          item.state = '发布中'
          item.progress = 95
          await RelayService.complete(upload.id, controller.signal, auth)
          check()
          item.state = '已完成'
          item.progress = 100
          await sync()
        } catch (e) {
          item.state = controller.signal.aborted || epoch !== generation ? '已取消' : '失败'
          item.error = e instanceof Error ? e.message : '上传失败'
          if (e instanceof RelayError && (e.status === 413 || e.status === 403)) {
            policy.value = null
            try {
              policy.value = await RelayService.policy()
            } catch {
              /* explicit unknown policy */
            }
          }
          if (epoch === generation && e instanceof RelayError && (e.status === 401 || e.status === 409))
            await sync()
        } finally {
          item.controller = undefined
        }
      }
    } finally {
      queueRunning.value = false
    }
  }
  function addFiles(selected: FileList | File[]) {
    if (mode.value !== 'relay') return
    for (const file of Array.from(selected))
      queue.value.push({
        key: ++serial,
        file,
        progress: 0,
        state: '等待上传',
        error: '',
        generation
      })
    void runQueue()
  }
  function canRetry(item: QueueItem) {
    return item.generation === generation && !item.controller && !item.cancelling &&
      ['失败', '已取消'].includes(item.state)
  }
  function retry(item: QueueItem) {
    if (mode.value !== 'relay' || !canRetry(item)) return
    item.state = '等待上传'
    item.progress = 0
    item.error = ''
    void runQueue()
  }
  async function cancel(item: QueueItem) {
    item.controller?.abort()
    item.state = '已取消'
    const auth = session.value
    if (!item.uploadID || item.generation !== generation || !auth?.paired) return
    item.cancelling = true
    try {
      await RelayService.cancel(item.uploadID, auth)
      item.uploadID = undefined
    } catch {
      // The next upload checks whether the server still has a resumable session.
    } finally {
      item.cancelling = false
    }
  }
  const paste = (event: ClipboardEvent) => {
    if (event.clipboardData?.files.length) addFiles(event.clipboardData.files)
  }
  const dragover = (event: DragEvent) => {
    if (event.dataTransfer?.types.includes('Files')) {
      event.preventDefault()
      event.dataTransfer.dropEffect = mode.value === 'relay' ? 'copy' : 'none'
    }
  }
  const drop = (event: DragEvent) => {
    if (!event.dataTransfer?.files.length) return
    event.preventDefault()
    addFiles(event.dataTransfer.files)
  }
  onMounted(() => {
    document.addEventListener('visibilitychange', wake)
    window.addEventListener('focus', wake)
    window.addEventListener('paste', paste)
    window.addEventListener('dragover', dragover)
    window.addEventListener('drop', drop)
    void initialize()
  })
  onUnmounted(() => {
    stopped = true
    resetContext()
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', wake)
    window.removeEventListener('focus', wake)
    window.removeEventListener('paste', paste)
    window.removeEventListener('dragover', dragover)
    window.removeEventListener('drop', drop)
  })
  return {
    mode,
    session,
    passcode,
    files,
    requests,
    pendingRequest,
    queue,
    error,
    busy,
    policy,
    pair,
    repair,
    resume,
    decide,
    remove,
    addFiles,
    retry,
    canRetry,
    cancel
  }
}
