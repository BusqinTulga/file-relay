<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSystemConfig } from '@/composables'
import SettingSwitch from '@/components/common/SettingSwitch.vue'
import SettingNumberInput from '@/components/common/SettingNumberInput.vue'
const { t } = useI18n()
const {
  config,
  fileSize,
  capacity,
  adminSessionDays,
  isLoading,
  loaded,
  error,
  saved,
  isDirty,
  refreshConfig,
  submitConfig
} = useSystemConfig()
onMounted(refreshConfig)
</script>
<template>
  <form class="admin-content max-w-5xl" @submit.prevent="submitConfig">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="theme-text-muted">{{ t(isDirty ? 'simple.unsaved' : 'simple.settingsHint') }}</p>
      <div class="flex gap-3">
        <button
          type="button"
          class="admin-button"
          :disabled="isLoading || isDirty"
          @click="refreshConfig"
        >
          {{ t('simple.refresh') }}</button
        ><button class="admin-button admin-primary" :disabled="isLoading || !loaded || !isDirty">
          {{ t('simple.save') }}
        </button>
      </div>
    </div>
    <p v-if="error" role="alert" class="admin-error">{{ error }}</p>
    <p v-if="saved" role="status">{{ t('simple.saved') }}</p>
    <p v-if="!loaded && isLoading">{{ t('simple.loading') }}</p>
    <fieldset v-if="loaded" :disabled="isLoading" class="space-y-6">
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.site') }}</h3>
        <label class="admin-label"
          >{{ t('simple.siteName')
          }}<input v-model="config.name" required maxlength="80" class="admin-input"
        /></label>
        <label class="admin-label"
          >{{ t('simple.description')
          }}<input v-model="config.description" maxlength="255" class="admin-input"
        /></label>
        <label class="admin-label"
          >{{ t('simple.noticeTitle')
          }}<input v-model="config.notify_title" maxlength="255" class="admin-input"
        /></label>
        <label class="admin-label"
          >{{ t('simple.noticeContent')
          }}<textarea
            v-model="config.notify_content"
            maxlength="5000"
            rows="3"
            class="admin-input"
          />
        </label>
        <SettingSwitch
          :label="t('simple.adminEntry')"
          :model-value="config.show_admin_addr"
          :enabled-text="t('simple.enabled')"
          :disabled-text="t('simple.hidden')"
          @toggle="config.show_admin_addr = config.show_admin_addr === 1 ? 0 : 1"
        />
      </section>
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.uploadCapacity') }}</h3>
        <SettingSwitch
          :label="t('simple.upload')"
          :model-value="config.open_upload"
          :enabled-text="t('simple.enabled')"
          :disabled-text="t('simple.paused')"
          @toggle="config.open_upload = config.open_upload === 1 ? 0 : 1"
        />
        <div class="grid gap-5 sm:grid-cols-2">
          <label class="admin-label"
            >{{ t('simple.fileLimit') }}
            <div class="flex gap-2">
              <input
                v-model.number="fileSize.value"
                type="number"
                step="any"
                min="0.000000001"
                required
                class="admin-input"
              /><select v-model="fileSize.unit" class="admin-input w-24">
                <option v-for="unit in ['B', 'KB', 'MB', 'GB']" :key="unit">{{ unit }}</option>
              </select>
            </div></label
          >
          <label class="admin-label"
            >{{ t('simple.limit') }}
            <div class="flex gap-2">
              <input
                v-model.number="capacity.value"
                type="number"
                step="any"
                min="0.000000001"
                required
                class="admin-input"
              /><select v-model="capacity.unit" class="admin-input w-24">
                <option v-for="unit in ['B', 'KB', 'MB', 'GB']" :key="unit">{{ unit }}</option>
              </select>
            </div></label
          >
        </div>
        <p class="theme-text-muted text-sm">{{ t('simple.unitsHint') }}</p>
        <p class="theme-text-muted text-sm">{{ t('simple.changeHint') }}</p>
      </section>
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.administrator') }}</h3>
        <label class="admin-label"
          >{{ t('simple.password')
          }}<input
            v-model="config.admin_token"
            type="password"
            autocomplete="new-password"
            minlength="8"
            maxlength="255"
            class="admin-input"
            :placeholder="t('simple.passwordHint')"
        /></label>
        <SettingNumberInput
          v-model="adminSessionDays"
          :min="1"
          :max="365"
          :label="t('simple.sessionDays')"
          :suffix="t('common.day')"
        />
        <p class="theme-text-muted text-sm">{{ t('simple.passwordEffect') }}</p>
      </section>
      <section class="admin-panel space-y-3">
        <h3 class="text-lg font-semibold">{{ t('simple.storageRules') }}</h3>
        <p>{{ t('simple.localDisk') }}</p>
        <p class="break-all text-sm">{{ config.data_root }}</p>
        <p class="theme-text-muted text-sm">{{ t('simple.fixedRules') }}</p>
      </section>
    </fieldset>
  </form>
</template>
