<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
  isDirty,
  changeSizeUnit,
  refreshConfig,
  showSaveError,
  submitConfig
} = useSystemConfig()
const form = ref<HTMLFormElement | null>(null)
const passwordDraft = ref('')
const hasUnsavedChanges = computed(
  () => (loaded.value && isLoading.value) || isDirty.value || passwordDraft.value !== config.value.admin_token
)

function confirmUnload(event: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) {
    event.preventDefault()
    event.returnValue = true
  }
}

function saveChanges() {
  if ((!isDirty.value && !isLoading.value) || !form.value) return

  const invalidInput = form.value.querySelector<HTMLInputElement>('input:invalid')
  if (invalidInput) {
    if (invalidInput.type === 'number') {
      showSaveError(t(invalidInput.required ? 'errors.sizePrecision' : 'errors.sessionDaysRange'))
    } else {
      showSaveError(t('errors.adminPasswordLength'))
    }
    return
  }
  void submitConfig()
}

function saveOnInputBlur(event: FocusEvent) {
  if (!(event.target instanceof HTMLInputElement)) return
  if (event.target.type === 'password') config.value.admin_token = passwordDraft.value
  saveChanges()
}

function toggleSetting(key: 'show_admin_addr' | 'open_upload') {
  config.value[key] = config.value[key] === 1 ? 0 : 1
  const focused = document.activeElement
  if (focused instanceof HTMLInputElement && form.value?.contains(focused)) return
  saveChanges()
}

function changeUnit(size: typeof fileSize.value, event: Event) {
  const select = event.target as HTMLSelectElement
  if (!changeSizeUnit(size, select.value === 'GB' ? 'GB' : 'MB')) {
    select.value = size.unit
    error.value = t('simple.invalidSize')
  }
}

watch(hasUnsavedChanges, (dirty) => {
  if (dirty) window.addEventListener('beforeunload', confirmUnload)
  else window.removeEventListener('beforeunload', confirmUnload)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', confirmUnload)
})
onMounted(refreshConfig)
</script>
<template>
  <form
    ref="form"
    class="admin-content max-w-5xl"
    @submit.prevent
    @input="error = ''"
    @focusout="saveOnInputBlur"
  >
    <p v-if="hasUnsavedChanges" class="theme-text-muted" role="status">
      {{ t(isLoading ? 'simple.saving' : 'simple.unsaved') }}
    </p>
    <p v-if="error" role="alert" class="admin-error">{{ error }}</p>
    <p v-if="!loaded && isLoading">{{ t('simple.loading') }}</p>
    <fieldset v-if="loaded" class="space-y-6">
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.site') }}</h3>
        <SettingSwitch
          :label="t('simple.adminEntry')"
          :model-value="config.show_admin_addr"
          :enabled-text="t('simple.enabled')"
          :disabled-text="t('simple.hidden')"
          @toggle="toggleSetting('show_admin_addr')"
        />
      </section>
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.uploadCapacity') }}</h3>
        <SettingSwitch
          :label="t('simple.upload')"
          :model-value="config.open_upload"
          :enabled-text="t('simple.enabled')"
          :disabled-text="t('simple.paused')"
          @toggle="toggleSetting('open_upload')"
        />
        <div class="grid gap-5 sm:grid-cols-2">
          <div class="admin-label">
            <span id="file-limit-label">{{ t('simple.fileLimit') }}</span>
            <div class="flex gap-2">
              <input
                v-model.number="fileSize.value"
                aria-labelledby="file-limit-label"
                type="number"
                step="any"
                :min="fileSize.unit === 'MB' ? 0.000001 : 0.000000001"
                required
                class="admin-input"
              />
              <select
                :value="fileSize.unit"
                aria-labelledby="file-limit-label"
                class="admin-input w-24"
                @change="changeUnit(fileSize, $event)"
              >
                <option v-for="unit in ['MB', 'GB']" :key="unit">{{ unit }}</option>
              </select>
            </div>
          </div>
          <div class="admin-label">
            <span id="storage-limit-label">{{ t('simple.limit') }}</span>
            <div class="flex gap-2">
              <input
                v-model.number="capacity.value"
                aria-labelledby="storage-limit-label"
                type="number"
                step="any"
                :min="capacity.unit === 'MB' ? 0.000001 : 0.000000001"
                required
                class="admin-input"
              />
              <select
                :value="capacity.unit"
                aria-labelledby="storage-limit-label"
                class="admin-input w-24"
                @change="changeUnit(capacity, $event)"
              >
                <option v-for="unit in ['MB', 'GB']" :key="unit">{{ unit }}</option>
              </select>
            </div>
          </div>
        </div>
      </section>
      <section class="admin-panel space-y-5">
        <h3 class="text-lg font-semibold">{{ t('simple.administrator') }}</h3>
        <div class="admin-label">
          <span id="admin-password-label">{{ t('simple.password') }}</span>
          <input
            aria-labelledby="admin-password-label"
            type="password"
            autocomplete="new-password"
            minlength="8"
            maxlength="255"
            class="admin-input"
            :placeholder="t('simple.passwordHint')"
            v-model="passwordDraft"
          />
        </div>
        <SettingNumberInput
          v-model="adminSessionDays"
          :min="1"
          :max="365"
          :label="t('simple.sessionDays')"
          :suffix="t('common.day')"
        />
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
