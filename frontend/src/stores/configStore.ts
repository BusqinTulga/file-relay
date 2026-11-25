import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { ConfigState, PublicConfigMeta } from '@/types'
import {
  DEFAULT_PUBLIC_CONFIG,
  readStoredConfig,
  toPublicConfig,
  writeStoredConfig,
  type PublicConfig
} from '@/utils/config-storage'

export const useConfigStore = defineStore('config', () => {
  const config = ref<PublicConfig>({
    ...DEFAULT_PUBLIC_CONFIG,
    ...toPublicConfig(readStoredConfig<Partial<ConfigState>>())
  })
  const publicMeta = ref<PublicConfigMeta>({})

  const uploadSizeLimit = computed(() => config.value.upload_size)

  const updateConfig = (nextConfig: Partial<ConfigState>) => {
    config.value = {
      ...DEFAULT_PUBLIC_CONFIG,
      ...config.value,
      ...toPublicConfig(nextConfig)
    }
    writeStoredConfig(config.value)
  }

  const applyPublicMeta = (nextMeta: PublicConfigMeta | undefined) => {
    if (!nextMeta) return

    publicMeta.value = {
      ...publicMeta.value,
      ...nextMeta
    }
  }

  const reloadStoredConfig = () => {
    config.value = {
      ...DEFAULT_PUBLIC_CONFIG,
      ...toPublicConfig(readStoredConfig<Partial<ConfigState>>())
    }
  }

  return {
    config,
    publicMeta,
    uploadSizeLimit,
    applyPublicMeta,
    updateConfig,
    reloadStoredConfig
  }
})
