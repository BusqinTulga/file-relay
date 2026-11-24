import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'
import ts from 'typescript'
const transpile = (path) => ts.transpileModule(
  readFileSync(new URL(path, import.meta.url), 'utf8'),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }
).outputText
const outputText = transpile('../src/composables/useRelay.ts')
const { default: zhCN } = await import(
  'data:text/javascript;base64,' + Buffer.from(transpile('../src/i18n/locales/zh-CN.ts')).toString('base64')
)
const { formatSizeLimit } = await import(
  'data:text/javascript;base64,' + Buffer.from(transpile('../src/utils/common.ts')).toString('base64')
)
const flush = () => new Promise((resolve) => setImmediate(resolve))
async function harness(overrides = {}, hash = async () => 'hash') {
  let mount, unmount
  const timers = []
  const document = Object.assign(new EventTarget(), { hidden: false })
  const window = new EventTarget()
  const auth = { paired: true, csrf: 'csrf-a', session_id: 'a', passcode: '007' }
  const service = {
    policy: async () => ({ upload_size: 1_000_000_000, storage_limit: 500_000_000_000, open_upload: 1 }),
    session: async () => auth,
    list: async () => ({ session_id: 'a', files: [] }),
    approvals: async () => [],
    ...overrides
  }
  class RelayError extends Error {
    constructor(status, message) {
      super(message)
      this.status = status
    }
  }
  const dependencies = {
    vue: {
      ref: (value) => ({ value }),
      watch: () => {},
      onMounted: (cb) => {
        mount = cb
      },
      onUnmounted: (cb) => {
        unmount = cb
      }
    },
    'vue-i18n': {
      useI18n: () => ({
        t: (path, values = {}) => {
          const message = path.split('.').reduce((group, key) => group[key], zhCN)
          return message.replace(/\{(\w+)\}/g, (_, key) => values[key])
        }
      })
    },
    '@/services': { RelayService: service, RelayError },
    '@/utils/relay-sha256': { hashRelayFile: hash },
    '@/utils/common': { formatSizeLimit }
  }
  const context = createContext({
    document,
    window,
    AbortController,
    DOMException,
    Error,
    console,
    setTimeout: (cb, delay) => {
      timers.push({ cb, delay })
      return timers.length
    },
    clearTimeout: () => {}
  })
  const module = new SourceTextModule(outputText, { context })
  await module.link(async (name) => {
    const values = dependencies[name]
    const synthetic = new SyntheticModule(
      Object.keys(values),
      function () {
        for (const [k, v] of Object.entries(values)) this.setExport(k, v)
      },
      { context }
    )
    await synthetic.link(() => {})
    await synthetic.evaluate()
    return synthetic
  })
  await module.evaluate()
  const flow = module.namespace.useRelay()
  mount()
  await flush()
  return { flow, service, auth, document, window, timers, unmount, RelayError }
}
test('late list response is ignored after selecting re-pair', async () => {
  let release
  const list = new Promise((resolve) => {
    release = resolve
  })
  const { flow, unmount } = await harness({ list: () => list })
  flow.repair()
  release({ session_id: 'a', files: [{ id: 1, name: 'old-group' }] })
  await flush()
  assert.equal(flow.mode.value, 'pair')
  assert.equal(flow.files.value.length, 0)
  unmount()
})
test('failed refresh keeps the current list and schedules backoff', async () => {
  const { flow, service, timers, unmount } = await harness({
    list: async () => ({ session_id: 'a', files: [{ id: 1 }] })
  })
  assert.equal(flow.files.value.length, 1)
  service.list = async () => {
    throw new Error('offline')
  }
  await timers.at(-1).cb()
  assert.equal(flow.files.value.length, 1)
  assert.equal(flow.error.value, 'offline')
  assert.ok(timers.at(-1).delay <= 4000 && timers.at(-1).delay >= 3900)
  unmount()
})
test('hidden page does not poll files', async () => {
  let calls = 0
  const { document, timers, unmount } = await harness({
    list: async () => {
      calls++
      return { session_id: 'a', files: [] }
    }
  })
  const before = calls
  document.hidden = true
  await timers.at(-1).cb()
  assert.equal(calls, before)
  unmount()
})

test('reload restores a pending application and claims approval', async () => {
  const pending = { request_id: 'example', status: 'pending', expires: 100 }
  const unpaired = { paired: false, csrf: 'bootstrap', pending }
  const { flow, service, auth, timers, unmount } = await harness({
    session: async () => unpaired,
    pending: async (session) => {
      assert.equal(session, unpaired)
      return { status: 'pending' }
    }
  })
  assert.equal(flow.mode.value, 'waiting')
  assert.equal(flow.pendingRequest.value, pending)
  service.pending = async () => auth
  await timers.at(-1).cb()
  assert.equal(flow.mode.value, 'relay')
  assert.equal(flow.session.value, auth)
  assert.equal(flow.pendingRequest.value, null)
  unmount()
})

test('failed upload policy does not hide files available to download', async () => {
  const { flow, unmount } = await harness({
    policy: async () => { throw new Error('offline') },
    list: async () => ({ session_id: 'a', files: [{ id: 1 }] })
  })
  assert.equal(flow.mode.value, 'relay')
  assert.equal(flow.files.value[0].id, 1)
  assert.equal(flow.policy.value, null)
  unmount()
})
test('re-pair during hashing stops old queue before creating an upload', async () => {
  let release,
    starts = 0
  const hash = new Promise((resolve) => {
    release = resolve
  })
  const { flow, unmount } = await harness(
    {
      start: async () => {
        starts++
      }
    },
    () => hash
  )
  flow.addFiles([{ name: 'old.txt', size: 5 }])
  flow.repair()
  release('fullhash')
  await flush()
  assert.equal(starts, 0)
  assert.equal(flow.queue.value[0].state, 'cancelled')
  unmount()
})
test('changed browser cookie clears old list before new list arrives', async () => {
  const { flow, service, auth, timers, unmount } = await harness({
    list: async () => ({ session_id: 'a', files: [{ id: 1 }] })
  })
  service.session = async () => ({ ...auth, session_id: 'b' })
  let release
  service.list = () =>
    new Promise((resolve) => {
      release = resolve
    })
  const refresh = timers.at(-1).cb()
  await flush()
  assert.equal(flow.files.value.length, 0)
  release({ session_id: 'b', files: [{ id: 2 }] })
  await refresh
  assert.equal(flow.files.value[0].id, 2)
  unmount()
})

test('retry waits until server-side cancellation settles', async () => {
  let finishCancel, starts = 0
  const { flow, unmount } = await harness({
    start: async () => {
      starts++
      return { id: 'upload', state: 'uploading', chunk_size: 1, chunks: [] }
    },
    put: (_id, _index, _block, _hash, signal) => new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason), { once: true })
    }),
    cancel: () => new Promise((resolve) => { finishCancel = resolve })
  })
  flow.addFiles([{ name: 'one.txt', size: 1, slice: () => ({}) }])
  await flush()
  const item = flow.queue.value[0]
  const cancellation = flow.cancel(item)
  await flush()
  flow.retry(item)
  assert.equal(starts, 1)
  finishCancel()
  await cancellation
  flow.retry(item)
  await flush()
  assert.equal(starts, 2)
  unmount()
})

test('page-wide file drop queues each file once and removes listeners on unmount', async () => {
  const { flow, window, unmount } = await harness({}, () => new Promise(() => {}))
  const files = [
    { name: 'page-drop.txt', size: 5 },
    { name: 'second.txt', size: 8 }
  ]
  const drop = () =>
    Object.assign(new Event('drop', { cancelable: true }), {
      dataTransfer: { files }
    })
  const event = drop()
  window.dispatchEvent(event)
  assert.equal(event.defaultPrevented, true)
  assert.equal(flow.queue.value.length, 2)
  assert.deepEqual(
    Array.from(flow.queue.value, (item) => item.file.name),
    files.map((file) => file.name)
  )
  unmount()
  const after = drop()
  window.dispatchEvent(after)
  assert.equal(after.defaultPrevented, false)
  assert.equal(flow.queue.value.length, 2)
})
test('page-wide dragover accepts files and preserves ordinary text dragging', async () => {
  const { flow, window, unmount } = await harness()
  const drag = (types) =>
    Object.assign(new Event('dragover', { cancelable: true }), {
      dataTransfer: { types, dropEffect: 'none' }
    })
  const file = drag(['Files'])
  window.dispatchEvent(file)
  assert.equal(file.defaultPrevented, true)
  assert.equal(file.dataTransfer.dropEffect, 'copy')
  const text = drag(['text/plain'])
  window.dispatchEvent(text)
  assert.equal(text.defaultPrevented, false)
  flow.repair()
  const unpaired = drag(['Files'])
  window.dispatchEvent(unpaired)
  assert.equal(unpaired.dataTransfer.dropEffect, 'none')
  unmount()
})

test('remote file limit rejects before hashing and retry uses the raised limit', async () => {
  let hashes = 0, starts = 0, limit = 10_485_760
  const { flow, unmount } = await harness({
    policy: async () => ({ upload_size: limit, storage_limit: 500_000_000_000, open_upload: 1 }),
    start: async () => { starts++; throw new Error('upload reached') }
  }, async () => { hashes++; return 'hash' })
  flow.addFiles([{ name: 'too-large', size: 10_490_000 }])
  await flush()
  assert.equal(flow.queue.value[0].state, 'failed')
  assert.match(flow.queue.value[0].error, /10\.48576 MB/)
  assert.equal(hashes, 0)
  assert.equal(starts, 0)
  limit = 11_000_000
  flow.retry(flow.queue.value[0])
  await flush()
  assert.equal(hashes, 1)
  assert.equal(starts, 1)
  unmount()
})

test('failed or paused policy stops before hashing without using a fallback', async () => {
  let hashes = 0
  const { flow, service, unmount } = await harness({}, async () => { hashes++; return 'hash' })
  service.policy = async () => { throw new Error('configuration offline') }
  flow.addFiles([{ name: 'small', size: 1 }])
  await flush()
  assert.equal(flow.queue.value[0].state, 'failed')
  assert.equal(flow.policy.value, null)
  assert.equal(hashes, 0)
  service.policy = async () => ({ upload_size: 100, storage_limit: 1000, open_upload: 0 })
  flow.retry(flow.queue.value[0])
  await flush()
  assert.match(flow.queue.value[0].error, /暂停/)
  assert.equal(hashes, 0)
  unmount()
})
