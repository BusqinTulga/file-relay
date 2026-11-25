<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDashboardStats } from '@/composables'
import { formatFileSize, formatSizeLimit } from '@/utils/common'
const { t } = useI18n()
const { data, error, isLoading, refresh } = useDashboardStats()
const uptime = computed(() =>
  data.value?.sys_start
    ? Math.max(0, Math.floor((Date.now() - data.value.sys_start) / 3_600_000))
    : 0
)
onMounted(refresh)
</script>
<template>
  <div class="admin-content">
    <p v-if="error" role="alert" class="admin-error">{{ error }}</p>
    <p v-if="isLoading && !data">{{ t('simple.loading') }}</p>
    <template v-if="data">
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="admin-panel">
          <p class="theme-text-muted">{{ t('simple.activeFiles') }}</p>
          <strong class="mt-3 block text-3xl">{{ data.active_files }}</strong>
        </div>
        <div class="admin-panel">
          <p class="theme-text-muted">{{ t('simple.pendingFiles') }}</p>
          <strong class="mt-3 block text-3xl">{{ data.pending_files }}</strong>
        </div>
        <div class="admin-panel">
          <p class="theme-text-muted">{{ t('simple.available') }}</p>
          <strong class="mt-3 block text-3xl">{{ formatFileSize(data.available_bytes) }}</strong>
        </div>
        <div class="admin-panel">
          <p class="theme-text-muted">{{ t('simple.diskFree') }}</p>
          <strong class="mt-3 block text-3xl">{{ formatFileSize(data.disk_free_bytes) }}</strong>
        </div>
      </div>
      <section class="admin-panel">
        <h3 class="mb-5 text-lg font-semibold">{{ t('simple.capacity') }}</h3>
        <dl class="grid gap-5 sm:grid-cols-2">
          <div>
            <dt>{{ t('simple.limit') }}</dt>
            <dd>{{ formatSizeLimit(data.storage_limit) }}</dd>
          </div>
          <div>
            <dt>{{ t('simple.occupied') }}</dt>
            <dd>{{ formatFileSize(data.occupied_bytes) }}</dd>
          </div>
          <div>
            <dt>{{ t('simple.published') }}</dt>
            <dd>{{ formatFileSize(data.published_bytes) }}</dd>
          </div>
          <div>
            <dt>{{ t('simple.reserved') }}</dt>
            <dd>{{ formatFileSize(data.reserved_bytes) }}</dd>
          </div>
        </dl>
        <p v-if="data.occupied_bytes > data.storage_limit" class="admin-error mt-4">
          {{ t('simple.overQuota') }}
        </p>
        <p class="theme-text-muted mt-5 text-sm">{{ t('simple.capacityHint') }}</p>
      </section>
      <section class="admin-panel">
        <h3 class="mb-5 text-lg font-semibold">{{ t('simple.rules') }}</h3>
        <dl class="grid gap-5 sm:grid-cols-2">
          <div>
            <dt>{{ t('simple.fileLimit') }}</dt>
            <dd>
              {{ formatSizeLimit(data.upload_size) }}
            </dd>
          </div>
          <div>
            <dt>{{ t('simple.upload') }}</dt>
            <dd>{{ t(data.open_upload ? 'simple.enabled' : 'simple.paused') }}</dd>
          </div>
          <div>
            <dt>{{ t('simple.retention') }}</dt>
            <dd>
              {{
                t('simple.retentionValue', {
                  hours: data.file_ttl / 3600,
                  minutes: data.retry_window / 60
                })
              }}
            </dd>
          </div>
          <div>
            <dt>{{ t('simple.uptime') }}</dt>
            <dd>{{ t('simple.hours', { hours: uptime }) }}</dd>
          </div>
        </dl>
      </section>
    </template>
  </div>
</template>
