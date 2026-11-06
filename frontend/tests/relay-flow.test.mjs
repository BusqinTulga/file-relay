import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'
import ts from 'typescript'
const source = readFileSync(new URL('../src/composables/useRelay.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }
})
const flush = () => new Promise((resolve) => setImmediate(resolve))
async function harness(overrides = {}, hash = async () => 'hash') {
  let mount, unmount
  const timers = []
  const document = Object.assign(new EventTarget(), { hidden: false })
  const window = new EventTarget()
  const auth = { paired: true, csrf: 'csrf-a', session_id: 'a', passcode: '007' }
  const service = {
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
      onMounted: (cb) => {
        mount = cb
      },
      onUnmounted: (cb) => {
        unmount = cb
      }
    },
    '@/services': { RelayService: service, RelayError },
    '@/utils/relay-sha256': { hashRelayFile: hash }
  }
  const context = createContext({
    document,
    window,
    AbortController,
    DOMException,
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
  return { flow, service, auth, document, timers, unmount, RelayError }
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
  assert.match(flow.refreshState.value, /重试/)
  assert.ok(timers.at(-1).delay <= 4000 && timers.at(-1).delay >= 3900)
  unmount()
})
test('hidden page does not poll files', async () => {
  let calls = 0
  const { flow, document, unmount } = await harness({
    list: async () => {
      calls++
      return { session_id: 'a', files: [] }
    }
  })
  const before = calls
  document.hidden = true
  await flow.refresh()
  assert.equal(calls, before)
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
  assert.equal(flow.queue.value[0].state, '已取消')
  unmount()
})
test('changed browser cookie clears old list before new list arrives', async () => {
  const { flow, service, auth, unmount } = await harness({
    list: async () => ({ session_id: 'a', files: [{ id: 1 }] })
  })
  service.session = async () => ({ ...auth, session_id: 'b' })
  let release
  service.list = () =>
    new Promise((resolve) => {
      release = resolve
    })
  const refresh = flow.refresh()
  await flush()
  assert.equal(flow.files.value.length, 0)
  release({ session_id: 'b', files: [{ id: 2 }] })
  await refresh
  assert.equal(flow.files.value[0].id, 2)
  unmount()
})
