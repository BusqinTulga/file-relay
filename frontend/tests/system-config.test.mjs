import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'
import ts from 'typescript'
import { computed, ref, watch } from 'vue'

const transpile = (path) => ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }
}).outputText

const source = transpile('../src/composables/useSystemConfig.ts')
const publicConfigSource = transpile('../src/composables/usePublicConfigBootstrap.ts')
const form = await import(
  'data:text/javascript;base64,' + Buffer.from(transpile('../src/utils/config-form.ts')).toString('base64')
)

async function harness() {
  const saved = {
    show_admin_addr: 0,
    open_upload: 1,
    upload_size: 10_485_760,
    storage_limit: 500_000_000_000,
    admin_token: '',
    admin_session_expire: 30 * 86400,
    data_root: '/data'
  }
  const requests = []
  const publicConfig = () => {
    const { admin_token, admin_session_expire, data_root, ...config } = saved
    return config
  }
  const cachedConfig = publicConfig()
  const service = {
    getConfig: async () => ({ detail: { ...saved } }),
    getUserConfig: async () => ({ code: 200, detail: { config: publicConfig() } }),
    updateConfig: async (changes) => {
      requests.push({ ...changes })
      Object.assign(saved, changes)
    }
  }
  const dependencies = {
    vue: { computed, ref, watch },
    axios: { isAxiosError: () => false },
    'vue-i18n': { useI18n: () => ({ locale: ref('zh-CN'), t: (key) => key }) },
    '@/services': { ConfigService: service },
    '@/stores/configStore': { useConfigStore: () => ({
      applyPublicMeta: () => {},
      updateConfig: (changes) => Object.assign(cachedConfig, changes)
    }) },
    '@/stores/adminStore': { useAdminStore: () => ({ logout: () => {} }) },
    '@/stores/alertStore': { useAlertStore: () => ({ showAlert: () => {} }) },
    '@/utils/config-storage': { DEFAULT_CONFIG_STATE: { ...saved } },
    '@/utils/config-form': form,
    '@/utils/common': { getErrorMessage: (_error, fallback) => fallback }
  }
  const context = createContext({})
  const module = new SourceTextModule(source, { context })
  await module.link((name) => {
    if (name === './usePublicConfigBootstrap') {
      return new SourceTextModule(publicConfigSource, { context })
    }
    const values = dependencies[name]
    return new SyntheticModule(Object.keys(values), function () {
      for (const [key, value] of Object.entries(values)) this.setExport(key, value)
    }, { context })
  })
  await module.evaluate()
  return { useSystemConfig: module.namespace.useSystemConfig, service, saved, requests, cachedConfig }
}

test('saving storage capacity in a stale tab preserves another tab’s upload settings', async () => {
  const { useSystemConfig, saved, requests } = await harness()
  const first = useSystemConfig()
  const second = useSystemConfig()
  await Promise.all([first.refreshConfig(), second.refreshConfig()])

  first.config.value.open_upload = 0
  first.fileSize.value.value = 5
  await first.submitConfig()
  second.capacity.value.value = 400
  await second.submitConfig()

  assert.deepEqual(requests, [{ open_upload: 0, upload_size: 5_000_000 }, { storage_limit: 400_000_000_000 }])
  assert.equal(saved.open_upload, 0)
  assert.equal(saved.upload_size, 5_000_000)
  assert.equal(saved.storage_limit, 400_000_000_000)
  assert.equal(second.isDirty.value, false)
})

test('saving storage capacity refreshes the public cache with another tab’s changes', async () => {
  const { useSystemConfig, saved, requests, cachedConfig } = await harness()
  const settings = useSystemConfig()
  await settings.refreshConfig()

  // Another tab updates the server while this tab still has the old value cached.
  saved.show_admin_addr = 1
  assert.equal(cachedConfig.show_admin_addr, 0)
  settings.capacity.value.value = 400
  await settings.submitConfig()

  assert.deepEqual(requests, [{ storage_limit: 400_000_000_000 }])
  assert.equal(cachedConfig.show_admin_addr, 1)
  assert.equal(cachedConfig.storage_limit, 400_000_000_000)
  assert.equal(settings.isDirty.value, false)
})

test('queued autosave compares with the last successful patch, including reverted edits', async () => {
  const { useSystemConfig, service, saved, requests } = await harness()
  const settings = useSystemConfig()
  await settings.refreshConfig()

  let finishFirst
  const firstResponse = new Promise((resolve) => { finishFirst = resolve })
  const update = service.updateConfig
  service.updateConfig = async (changes) => {
    if (!requests.length) await firstResponse
    await update(changes)
  }

  settings.capacity.value.value = 400
  const firstSave = settings.submitConfig()
  settings.capacity.value.value = 500
  settings.config.value.show_admin_addr = 1
  await settings.submitConfig()
  finishFirst()
  await firstSave

  assert.deepEqual(requests, [
    { storage_limit: 400_000_000_000 },
    { storage_limit: 500_000_000_000, show_admin_addr: 1 }
  ])
  assert.equal(saved.storage_limit, 500_000_000_000)
  assert.equal(saved.show_admin_addr, 1)
  assert.equal(settings.isDirty.value, false)
})
