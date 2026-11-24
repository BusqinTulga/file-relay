import { ConfigService } from '@/services'
import { useConfigStore } from '@/stores/configStore'

export function usePublicConfigBootstrap() {
  const configStore = useConfigStore()

  const syncPublicConfig = async () => {
    const res = await ConfigService.getUserConfig().catch(() => null)
    if (!res) return

    if (res.code !== 200 || !res.detail) {
      return
    }

    configStore.applyPublicMeta(res.detail.meta)
    configStore.updateConfig(res.detail.config)
  }

  return {
    syncPublicConfig
  }
}
