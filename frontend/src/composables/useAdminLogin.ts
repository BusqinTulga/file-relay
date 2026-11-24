import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AuthService } from '@/services'
import { useAdminStore } from '@/stores/adminStore'
import { useAlertStore } from '@/stores/alertStore'
import { getErrorMessage } from '@/utils/common'

export function useAdminLogin() {
  const { t } = useI18n()
  const alertStore = useAlertStore()
  const adminStore = useAdminStore()
  const password = ref('')
  const isLoading = ref(false)

  const validateForm = () => {
    if (!password.value) {
      alertStore.showAlert(t('login.missingPassword'), 'error')
      return false
    }

    if (password.value.length < 6) {
      alertStore.showAlert(t('login.shortPassword'), 'error')
      return false
    }

    return true
  }

  const handleSubmit = async () => {
    if (!validateForm()) return false

    isLoading.value = true
    try {
      const response = await AuthService.login(password.value)
      if (!response.detail?.token || !response.detail.expires_at) {
        alertStore.showAlert(t('login.invalidSession'), 'error')
        return false
      }

      adminStore.login({
        id: response.detail.id || 'admin',
        username: response.detail.username || 'admin',
        token: response.detail.token,
        token_type: response.detail.token_type,
        expires_at: response.detail.expires_at
      })
      return true
    } catch (error: unknown) {
      alertStore.showAlert(getErrorMessage(error, t('login.failed')), 'error')
      return false
    } finally {
      isLoading.value = false
    }
  }

  return {
    password,
    isLoading,
    handleSubmit
  }
}
