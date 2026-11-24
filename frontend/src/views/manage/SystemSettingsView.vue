<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSystemConfig } from '@/composables'
import { useAlertStore } from '@/stores/alertStore'
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
  changeSizeUnit,
  refreshConfig,
  submitConfig
} = useSystemConfig()
const alertStore = useAlertStore()
const form = ref<HTMLFormElement | null>(null)
const passwordDraft = ref('')
const hasUnsavedChanges = computed(() => isDirty.value || passwordDraft.value !== config.value.admin_token)
let saveTimer: ReturnType<typeof setTimeout> | undefined

function confirmUnload(event: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) {
    event.preventDefault()
    event.returnValue = true
  }
}

function saveChanges() {
  clearTimeout(saveTimer)
  saveTimer = undefined
  if (isDirty.value && !isLoading.value && form.value?.reportValidity()) {
    void submitConfig()
  }
}

function changeUnit(size: typeof fileSize.value, event: Event) {
  const select = event.target as HTMLSelectElement
  if (!changeSizeUnit(size, select.value === 'GB' ? 'GB' : 'MB')) {
    select.value = size.unit
    error.value = t('simple.invalidSize')
  }
}

watch(
  [config, fileSize, capacity, adminSessionDays],
  () => {
    if (!loaded.value) return
    clearTimeout(saveTimer)
    saveTimer = undefined
    if (!isDirty.value) {
      error.value = ''
      return
    }
    saved.value = false
    error.value = ''
    saveTimer = setTimeout(saveChanges, 700)
  },
  { deep: true }
)
watch(
  saved,
  (value) => {
    if (value) alertStore.showAlert(t('simple.saved'), 'success')
  },
  { flush: 'sync' }
)
watch(hasUnsavedChanges, (dirty) => {
  if (dirty) window.addEventListener('beforeunload', confirmUnload)
  else window.removeEventListener('beforeunload', confirmUnload)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', confirmUnload)
  if (saveTimer === undefined) return
  clearTimeout(saveTimer)
  if (isDirty.value && form.value?.checkValidity()) void submitConfig()
})
onMounted(refreshConfig)
</script>
<template>
  <form ref="form" class="admin-content max-w-5xl" @submit.prevent="saveChanges">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p v-if="hasUnsavedChanges" class="theme-text-muted" role="status">
        {{ t(isLoading ? 'simple.saving' : 'simple.unsaved') }}
      </p>
      <button v-if="error && isDirty" type="submit" class="admin-button" :disabled="isLoading">
        {{ t('simple.retrySave') }}
      </button>
      <button
        type="button"
        class="admin-button"
        :disabled="isLoading || hasUnsavedChanges"
        @click="refreshConfig"
      >
        {{ t('simple.refresh') }}
      </button>
    </div>
    <p v-if="error" role="alert" class="admin-error">{{ error }}</p>
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
                :min="fileSize.unit === 'MB' ? 0.000001 : 0.000000001"
                required
                class="admin-input"
              /><select
                :value="fileSize.unit"
                class="admin-input w-24"
                @change="changeUnit(fileSize, $event)"
              >
                <option v-for="unit in ['MB', 'GB']" :key="unit">{{ unit }}</option>
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
                :min="capacity.unit === 'MB' ? 0.000001 : 0.000000001"
                required
                class="admin-input"
              /><select
                :value="capacity.unit"
                class="admin-input w-24"
                @change="changeUnit(capacity, $event)"
              >
                <option v-for="unit in ['MB', 'GB']" :key="unit">{{ unit }}</option>
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
            type="password"
            autocomplete="new-password"
            minlength="8"
            maxlength="255"
            class="admin-input"
            :placeholder="t('simple.passwordHint')"
            v-model="passwordDraft"
            @change="config.admin_token = passwordDraft"
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
