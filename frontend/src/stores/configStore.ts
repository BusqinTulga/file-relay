import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import i18n from '@/i18n'
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

  const siteName = computed(() =>
    config.value.name === DEFAULT_PUBLIC_CONFIG.name ? i18n.global.t('shell.siteName') : config.value.name
  )
  const siteDescription = computed(() =>
    config.value.description === DEFAULT_PUBLIC_CONFIG.description
      ? i18n.global.t('shell.siteDescription')
      : config.value.description
  )
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
    siteName,
    siteDescription,
    uploadSizeLimit,
    applyPublicMeta,
    updateConfig,
    reloadStoredConfig
  }
})
