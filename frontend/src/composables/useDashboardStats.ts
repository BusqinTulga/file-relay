import { ref } from 'vue'
import { StatsService } from '@/services'
import type { DashboardData } from '@/types'
import { getErrorMessage } from '@/utils/common'
export function useDashboardStats() {
  const data = ref<DashboardData | null>(null),
    isLoading = ref(false),
    error = ref('')
  async function refresh() {
    if (isLoading.value) return
    isLoading.value = true
    error.value = ''
    try {
      const result = await StatsService.getDashboard()
      if (!result.detail) throw new Error('无法读取概览')
      data.value = result.detail
    } catch (e) {
      error.value = getErrorMessage(e, '读取概览失败')
    } finally {
      isLoading.value = false
    }
  }
  return { data, isLoading, error, refresh }
}
