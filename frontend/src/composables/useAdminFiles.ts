import { ref, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileService } from '@/services'
import type { AdminFile } from '@/types'
import { getErrorMessage } from '@/utils/common'
import { saveDownload } from '@/utils/download-action'
export function useAdminFiles() {
  const { locale, t } = useI18n()
  const files = ref<AdminFile[]>([]),
    total = ref(0)
  const detail = ref<AdminFile | null>(null),
    error = ref(''),
    isLoading = ref(false),
    actionBusy = ref(false)
  const params = reactive({ page: 1, size: 20, keyword: '', status: 'all' })
  let generation = 0
  watch(locale, () => {
    error.value = ''
  })
  async function refresh() {
    const epoch = ++generation
    isLoading.value = true
    error.value = ''
    try {
      const result = await FileService.list({ ...params })
      if (epoch !== generation) return
      if (!result.detail) throw new Error(t('errors.loadFiles'))
      files.value = result.detail.files
      total.value = result.detail.total
      if (!files.value.length && total.value && params.page > 1) {
        params.page--
        await refresh()
      }
    } catch (e) {
      if (epoch === generation) error.value = getErrorMessage(e, t('errors.loadFiles'))
    } finally {
      if (epoch === generation) isLoading.value = false
    }
  }
  async function showDetail(id: number) {
    error.value = ''
    try {
      detail.value = (await FileService.detail(id)).detail || null
    } catch (e) {
      error.value = getErrorMessage(e, t('errors.loadDetails'))
    }
  }
  async function download(file: AdminFile) {
    if (actionBusy.value) return
    actionBusy.value = true
    error.value = ''
    try {
      saveDownload(await FileService.download(file.id), file.name)
      await refresh()
    } catch (e) {
      error.value = getErrorMessage(e, t('errors.download'))
    } finally {
      actionBusy.value = false
    }
  }
  return {
    files,
    total,
    detail,
    params,
    error,
    isLoading,
    actionBusy,
    refresh,
    showDetail,
    download
  }
}
