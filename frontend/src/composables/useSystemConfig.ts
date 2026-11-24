import { computed, ref } from 'vue'
import { ConfigService } from '@/services'
import { useConfigStore } from '@/stores/configStore'
import { useAdminStore } from '@/stores/adminStore'
import { DEFAULT_CONFIG_STATE } from '@/utils/config-storage'
import { bytesToFileSizeForm, fileSizeFormToBytes, type FileSizeUnit } from '@/utils/config-form'
import { getErrorMessage } from '@/utils/common'
import type { ConfigState } from '@/types'
export function useSystemConfig() {
  const config = ref<ConfigState>({ ...DEFAULT_CONFIG_STATE })
  const fileSize = ref(bytesToFileSizeForm(0)),
    capacity = ref(bytesToFileSizeForm(0))
  const adminSessionDays = ref(30),
    isLoading = ref(false),
    loaded = ref(false),
    error = ref(''),
    saved = ref(false)
  const snapshot = ref('')
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
    saved.value = false
    try {
      const result = await ConfigService.getConfig()
      if (!result.detail) throw new Error('无法读取设置')
      config.value = { ...result.detail, admin_token: '' }
      fileSize.value = bytesToFileSizeForm(config.value.upload_size)
      capacity.value = bytesToFileSizeForm(config.value.storage_limit)
      adminSessionDays.value = config.value.admin_session_expire / 86400
      loaded.value = true
      snapshot.value = JSON.stringify(payload())
    } catch (e) {
      error.value = getErrorMessage(e, '读取设置失败')
    } finally {
      isLoading.value = false
    }
  }
  async function submitConfig() {
    if (!loaded.value || isLoading.value) return
    isLoading.value = true
    error.value = ''
    saved.value = false
    try {
      const data = payload()
      await ConfigService.updateConfig(data)
      useConfigStore().updateConfig(data)
      if (data.admin_token) {
        saved.value = true
        useAdminStore().logout()
        window.dispatchEvent(new Event('filecodebox:auth:unauthorized'))
        return
      }
      config.value.admin_token = ''
      snapshot.value = JSON.stringify(payload())
      saved.value = true
    } catch (e) {
      error.value = getErrorMessage(e, '保存失败')
    } finally {
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
    saved,
    isDirty,
    changeSizeUnit,
    refreshConfig,
    submitConfig
  }
}
