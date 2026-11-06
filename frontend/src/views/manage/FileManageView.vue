<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminFiles } from '@/composables'
import BaseModal from '@/components/common/BaseModal.vue'
import { formatFileSize } from '@/utils/common'
const { t } = useI18n()
const {
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
} = useAdminFiles()
const statuses = ['all', 'waiting', 'retry', 'expired', 'pending', 'cleanup_failed']
const time = (value: number | null) =>
  value === null ? '—' : new Date(value * 1000).toLocaleString()
function search() {
  params.page = 1
  void refresh()
}
function confirmRemove(ids: number[]) {
  if (window.confirm(t('simple.deleteConfirm', { count: ids.length }))) void remove(ids)
}
function changePage(delta: number) { params.page += delta; void refresh() }
onMounted(refresh)
</script>
<template>
  <div class="admin-content">
    <form class="admin-panel flex flex-wrap items-end gap-3" @submit.prevent="search">
      <label class="admin-label min-w-40 flex-1"
        >{{ t('simple.filename')
        }}<input v-model="params.keyword" maxlength="255" class="admin-input" type="search"
      /></label>
      <label class="admin-label"
        >{{ t('simple.status')
        }}<select v-model="params.status" class="admin-input" @change="search">
          <option v-for="status in statuses" :key="status" :value="status">
            {{ t('simple.status_' + status) }}
          </option>
        </select></label
      >
      <button class="admin-button" :disabled="isLoading">{{ t('simple.search') }}</button
      ><button type="button" class="admin-button" :disabled="isLoading" @click="refresh">
        {{ t('simple.refresh') }}
      </button>
    </form>
    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="theme-text-muted">{{ t('simple.fileCount', { count: total }) }}</p>
      <button
        class="admin-button text-red-600"
        :disabled="!selected.length || actionBusy || isLoading"
        @click="confirmRemove(selected)"
      >
        {{ t('simple.deleteSelected', { count: selected.length }) }}
      </button>
    </div>
    <div class="admin-panel overflow-x-auto p-0">
      <table class="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                :aria-label="t('simple.selectAll')"
                :checked="files.length > 0 && selected.length === files.length"
                :disabled="isLoading || actionBusy"
                @change="
                  selected = ($event.target as HTMLInputElement).checked
                    ? files.map((f) => f.id)
                    : []
                "
              />
            </th>
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
            <td>
              <input
                v-model="selected"
                type="checkbox"
                :value="file.id"
                :aria-label="file.name"
                :disabled="isLoading || actionBusy"
              />
            </td>
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
                  {{ t('simple.download') }}</button
                ><button
                  :disabled="actionBusy"
                  class="text-red-600"
                  @click="confirmRemove([file.id])"
                >
                  {{ t('simple.delete') }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!files.length">
            <td colspan="7" class="py-12 text-center theme-text-muted">
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
    <p class="theme-text-muted text-xs">{{ t('simple.adminDownloadHint') }}</p>
    <BaseModal :show="!!detail" :title="t('simple.details')" @close="detail = null"
      ><dl v-if="detail" class="space-y-4 break-all">
        <div>
          <dt>{{ t('simple.filename') }}</dt>
          <dd>{{ detail.name }}</dd>
        </div>
        <div>
          <dt>{{ t('simple.size') }}</dt>
          <dd>{{ formatFileSize(detail.size) }} · {{ detail.size }} B</dd>
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
          <dd class="admin-error">{{ detail.cleanup_error }}</dd>
        </div>
      </dl></BaseModal
    >
  </div>
</template>
