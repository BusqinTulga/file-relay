import { ref, reactive } from 'vue'
import { FileService } from '@/services'
import type { AdminFile } from '@/types'
import { getErrorMessage } from '@/utils/common'
import { saveDownload } from '@/utils/download-action'
export function useAdminFiles() {
  const files = ref<AdminFile[]>([]),
    total = ref(0),
    selected = ref<number[]>([])
  const detail = ref<AdminFile | null>(null),
    error = ref(''),
    isLoading = ref(false),
    actionBusy = ref(false)
  const params = reactive({ page: 1, size: 20, keyword: '', status: 'all' })
  let generation = 0
  async function refresh() {
    const epoch = ++generation
    isLoading.value = true
    error.value = ''
    try {
      const result = await FileService.list({ ...params })
      if (epoch !== generation) return
      if (!result.detail) throw new Error('无法读取文件')
      files.value = result.detail.files
      total.value = result.detail.total
      selected.value = []
      if (!files.value.length && total.value && params.page > 1) {
        params.page--
        await refresh()
      }
    } catch (e) {
      if (epoch === generation) error.value = getErrorMessage(e, '读取文件失败')
    } finally {
      if (epoch === generation) isLoading.value = false
    }
  }
  async function showDetail(id: number) {
    error.value = ''
    try {
      detail.value = (await FileService.detail(id)).detail || null
    } catch (e) {
      error.value = getErrorMessage(e, '读取详情失败')
    }
  }
  async function remove(ids: number[]) {
    if (!ids.length || actionBusy.value) return
    actionBusy.value = true
    error.value = ''
    try {
      const result = await FileService.batchRemove(ids)
      const failed =
        result.detail?.failed.map((item) => `${item.id}: ${item.reason}`).join('；') || ''
      detail.value = null
      await refresh()
      error.value = failed
    } catch (e) {
      error.value = getErrorMessage(e, '删除失败')
    } finally {
      actionBusy.value = false
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
      error.value = getErrorMessage(e, '下载失败')
    } finally {
      actionBusy.value = false
    }
  }
  return {
    files,
    total,
    selected,
    detail,
    params,
    error,
    isLoading,
    actionBusy,
    refresh,
    showDetail,
    remove,
    download
  }
}
