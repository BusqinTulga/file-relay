import { computed, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { useI18n } from 'vue-i18n'
import { ConfigService } from '@/services'
import { useConfigStore } from '@/stores/configStore'
import { useAdminStore } from '@/stores/adminStore'
import { useAlertStore } from '@/stores/alertStore'
import { DEFAULT_CONFIG_STATE } from '@/utils/config-storage'
import {
  bytesToFileSizeForm,
  fileSizeFormToBytes,
  InvalidFileSizeError,
  type FileSizeUnit
} from '@/utils/config-form'
import { getErrorMessage } from '@/utils/common'
import type { ConfigState } from '@/types'
export function useSystemConfig() {
  const { locale, t } = useI18n()
  const alertStore = useAlertStore()
  const config = ref<ConfigState>({ ...DEFAULT_CONFIG_STATE })
  const fileSize = ref(bytesToFileSizeForm(0)),
    capacity = ref(bytesToFileSizeForm(0))
  const adminSessionDays = ref(30),
    isLoading = ref(false),
    loaded = ref(false),
    error = ref('')
  const snapshot = ref('')
  watch(locale, () => {
    error.value = ''
  })
  const payload = () => {
    const data = { ...config.value }
    delete data.data_root
    return {
      ...data,
      upload_size: fileSizeFormToBytes(fileSize.value.value, fileSize.value.unit),
      storage_limit: fileSizeFormToBytes(capacity.value.value, capacity.value.unit),
      admin_session_expire: adminSessionDays.value * 86400
    }
  }
  let pendingConfig: ReturnType<typeof payload> | undefined
  const isDirty = computed(() => {
    if (!loaded.value) return false
    try {
      return JSON.stringify(payload()) !== snapshot.value
    } catch {
      return true
    }
  })
  function changeSizeUnit(size: typeof fileSize.value, unit: FileSizeUnit) {
    try {
      const bytes = fileSizeFormToBytes(size.value, size.unit)
      Object.assign(size, bytesToFileSizeForm(bytes, unit))
      return true
    } catch {
      return false
    }
  }

  async function refreshConfig() {
    if (isLoading.value) return
    isLoading.value = true
    error.value = ''
    try {
      const result = await ConfigService.getConfig()
      if (!result.detail) throw new Error(t('errors.loadSettings'))
      config.value = { ...result.detail, admin_token: '' }
      fileSize.value = bytesToFileSizeForm(config.value.upload_size)
      capacity.value = bytesToFileSizeForm(config.value.storage_limit)
      adminSessionDays.value = config.value.admin_session_expire / 86400
      loaded.value = true
      snapshot.value = JSON.stringify(payload())
    } catch (e) {
      error.value = getErrorMessage(e, t('errors.loadSettings'))
    } finally {
      isLoading.value = false
    }
  }

  function showSaveError(reason: string) {
    error.value = reason ? t('simple.saveFailedDetail', { reason }) : t('simple.saveFailed')
    alertStore.showAlert(error.value, 'error')
  }

  async function submitConfig() {
    if (!loaded.value) return
    try {
      pendingConfig = payload()
    } catch (e) {
      showSaveError(e instanceof InvalidFileSizeError ? t('errors.sizePrecision') : '')
      return
    }
    if (isLoading.value) return

    isLoading.value = true
    try {
      while (pendingConfig) {
        const data = pendingConfig
        pendingConfig = undefined
        const submitted = JSON.stringify(data)
        if (submitted === snapshot.value) continue

        const requestLocale = locale.value
        error.value = ''
        try {
          await ConfigService.updateConfig(data)
          snapshot.value = submitted
          useConfigStore().updateConfig(data)
          alertStore.showAlert(t('simple.saved'), 'success')
          if (data.admin_token) {
            useAdminStore().logout()
            window.dispatchEvent(new Event('filecodebox:auth:unauthorized'))
            return
          }
        } catch (e) {
          let reason = ''
          if (isAxiosError(e)) {
            const fallback = t(e.response ? 'errors.serverFailed' : 'errors.networkFailed')
            reason = requestLocale === locale.value ? getErrorMessage(e, fallback) : fallback
          }
          showSaveError(reason)
        }
      }
    } finally {
      pendingConfig = undefined
      isLoading.value = false
    }
  }
  return {
    config,
    fileSize,
    capacity,
    adminSessionDays,
    isLoading,
    loaded,
    error,
    isDirty,
    changeSizeUnit,
    refreshConfig,
    showSaveError,
    submitConfig
  }
}
