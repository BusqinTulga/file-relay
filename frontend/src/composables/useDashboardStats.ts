import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { StatsService } from '@/services'
import type { DashboardData } from '@/types'
import { getErrorMessage } from '@/utils/common'
export function useDashboardStats() {
  const { locale, t } = useI18n()
  const data = ref<DashboardData | null>(null),
    isLoading = ref(false),
    error = ref('')
  watch(locale, () => {
    error.value = ''
  })
  async function refresh() {
    if (isLoading.value) return
    isLoading.value = true
    error.value = ''
    try {
      const result = await StatsService.getDashboard()
      if (!result.detail) throw new Error(t('errors.loadOverview'))
      data.value = result.detail
    } catch (e) {
      error.value = getErrorMessage(e, t('errors.loadOverview'))
    } finally {
      isLoading.value = false
    }
  }
  return { data, isLoading, error, refresh }
}
