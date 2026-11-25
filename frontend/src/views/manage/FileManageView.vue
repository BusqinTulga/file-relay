<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDownIcon } from 'lucide-vue-next'
import { useAdminFiles } from '@/composables'
import BaseModal from '@/components/common/BaseModal.vue'
import { formatFileSize } from '@/utils/common'
const { t, locale } = useI18n()
const {
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
} = useAdminFiles()
const statuses = ['all', 'waiting', 'retry', 'expired', 'pending', 'cleanup_failed']
const time = (value: number | null) =>
  value === null ? '—' : new Date(value * 1000).toLocaleString(locale.value)
function search() {
  params.page = 1
  void refresh()
}
function changePage(delta: number) { params.page += delta; void refresh() }
onMounted(refresh)
</script>
<template>
  <div class="admin-content">
    <form class="admin-panel flex flex-wrap items-end gap-3" @submit.prevent="search">
      <div class="admin-label min-w-40 flex-1">
        <span id="file-search-label">{{ t('simple.filename') }}</span>
        <input
          v-model="params.keyword"
          aria-labelledby="file-search-label"
          maxlength="255"
          class="admin-input h-11"
          type="search"
        />
      </div>
      <div class="admin-label">
        <span id="file-status-label">{{ t('simple.status') }}</span>
        <span class="relative block">
          <select
            v-model="params.status"
            aria-labelledby="file-status-label"
            class="admin-input status-select h-11 appearance-none"
            @change="search"
          >
            <option v-for="status in statuses" :key="status" :value="status">
              {{ t('simple.status_' + status) }}
            </option>
          </select>
          <ChevronDownIcon
            class="theme-text-muted pointer-events-none absolute bottom-3.5 right-3 h-4 w-4"
            aria-hidden="true"
          />
        </span>
      </div>
      <button type="submit" class="admin-button h-11" :disabled="isLoading">
        {{ t('simple.search') }}
      </button>
    </form>
    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
    <p class="theme-text-muted">{{ t('simple.fileCount', { count: total }) }}</p>
    <div class="admin-panel overflow-x-auto p-0">
      <table class="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr>
            <th>{{ t('simple.filename') }}</th>
            <th>{{ t('simple.size') }}</th>
            <th>{{ t('simple.uploadTime') }}</th>
            <th>{{ t('simple.expires') }}</th>
            <th>{{ t('simple.status') }}</th>
            <th>{{ t('simple.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in files" :key="file.id">
            <td class="max-w-56 break-all">{{ file.name }}</td>
            <td class="whitespace-nowrap">{{ formatFileSize(file.size) }}</td>
            <td>{{ time(file.published) }}</td>
            <td>{{ time(file.expires) }}</td>
            <td>{{ t('simple.status_' + file.status) }}</td>
            <td>
              <div class="flex gap-3 whitespace-nowrap">
                <button @click="showDetail(file.id)">{{ t('simple.details') }}</button
                ><button
                  :disabled="actionBusy || !['waiting', 'retry'].includes(file.status)"
                  @click="download(file)"
                >
                  {{ t('simple.download') }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!files.length">
            <td colspan="6" class="py-12 text-center theme-text-muted">
              {{ t(isLoading ? 'simple.loading' : 'simple.empty') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="flex items-center justify-between gap-3">
      <button
        class="admin-button"
        :disabled="params.page <= 1 || isLoading"
        @click="changePage(-1)"
      >
        {{ t('simple.previous') }}
      </button>
      <p>{{ params.page }} / {{ Math.max(1, Math.ceil(total / params.size)) }}</p>
      <button
        class="admin-button"
        :disabled="params.page * params.size >= total || isLoading"
        @click="changePage(1)"
      >
        {{ t('simple.next') }}
      </button>
    </div>
    <BaseModal :show="!!detail" :title="t('simple.details')" @close="detail = null"
      ><dl v-if="detail" class="space-y-4 break-all">
        <div>
          <dt>{{ t('simple.filename') }}</dt>
          <dd>{{ detail.name }}</dd>
        </div>
        <div>
          <dt>{{ t('simple.size') }}</dt>
          <dd>{{ formatFileSize(detail.size) }}</dd>
        </div>
        <div>
          <dt>{{ t('simple.uploadTime') }}</dt>
          <dd>{{ time(detail.published) }}</dd>
        </div>
        <div>
          <dt>{{ t('simple.firstSent') }}</dt>
          <dd>{{ time(detail.first_sent) }}</dd>
        </div>
        <div>
          <dt>{{ t('simple.expires') }}</dt>
          <dd>{{ time(detail.expires) }}</dd>
        </div>
        <div>
          <dt>SHA256</dt>
          <dd class="font-mono text-xs">{{ detail.sha256 }}</dd>
        </div>
        <div v-if="detail.cleanup_error">
          <dt>{{ t('simple.cleanupError') }}</dt>
          <dd class="admin-error">{{ locale === 'zh-CN' ? detail.cleanup_error : t('errors.cleanupFailed') }}</dd>
        </div>
      </dl></BaseModal
    >
  </div>
</template>

<style scoped>
.status-select {
  padding-inline-end: 2.25rem;
}
</style>
